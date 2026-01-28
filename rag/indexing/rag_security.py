"""
RAG Security - Anti-poisoning protection for knowledge base indexing

Addresses:
- OWASP LLM04: Data and Model Poisoning
- OWASP LLM08: Vector and Embedding Weaknesses
- MITRE ATLAS AML.T0048: Data Poisoning

Security Layers:
1. Injection pattern detection - Neutralize prompt injections in documents
2. Provenance tracking - Know where every document came from
3. Trust scoring - Weight documents by source trustworthiness
4. Embedding validation - Detect anomalous embeddings (future)

100% local, zero cloud APIs, defense-in-depth for RAG systems.
"""

import re
import hashlib
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import unicodedata

logger = logging.getLogger(__name__)


@dataclass
class InjectionDetectionResult:
    """Result of injection pattern detection"""
    is_safe: bool
    risk_level: str  # CLEAN, LOW, MEDIUM, HIGH, CRITICAL
    detected_patterns: List[Dict[str, str]]
    sanitized_content: str
    original_hash: str
    sanitized_hash: str


@dataclass
class DocumentProvenance:
    """Provenance metadata for indexed documents"""
    source_path: str
    source_type: str  # FILE, URL, API, MANUAL
    indexer_id: str  # Who/what indexed this
    indexed_at: str  # ISO timestamp
    trust_level: str  # TRUSTED, VERIFIED, UNTRUSTED
    trust_score: float  # 0.0 - 1.0
    content_hash: str  # SHA-256 of original content
    sanitized_hash: str  # SHA-256 of sanitized content
    security_scan_result: Dict  # Results from injection detection
    metadata: Dict = field(default_factory=dict)


class InjectionPatternDetector:
    """
    Detect and neutralize prompt injection patterns in documents.

    These patterns could poison the RAG knowledge base, causing the LLM
    to follow malicious instructions when retrieving these documents.
    """

    # Injection patterns ranked by severity
    INJECTION_PATTERNS = {
        # CRITICAL - Direct instruction override attempts
        'instruction_override': {
            'patterns': [
                r'(?i)ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|context)',
                r'(?i)disregard\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?)',
                r'(?i)forget\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?)',
                r'(?i)override\s+(system|previous|prior)\s+(prompt|instructions?)',
                r'(?i)new\s+instructions?\s*[:;]\s*ignore',
                r'(?i)\[?\s*system\s*\]?\s*[:;]?\s*you\s+are\s+now',
            ],
            'severity': 'CRITICAL',
            'description': 'Direct instruction override attempt',
        },

        # CRITICAL - Role hijacking
        'role_hijack': {
            'patterns': [
                r'(?i)you\s+are\s+now\s+(?:a|an|the)\s+\w+\s+(?:assistant|agent|bot)',
                r'(?i)act\s+as\s+(?:a|an|the)\s+\w+\s+(?:assistant|agent|bot)',
                r'(?i)pretend\s+(?:you\'?re?|to\s+be)\s+(?:a|an|the)',
                r'(?i)your\s+new\s+(?:role|identity|persona)\s+is',
                r'(?i)from\s+now\s+on[,]?\s+you\s+(?:are|will)',
            ],
            'severity': 'CRITICAL',
            'description': 'Role/identity hijacking attempt',
        },

        # HIGH - System prompt extraction
        'prompt_extraction': {
            'patterns': [
                r'(?i)(?:reveal|show|display|print|output)\s+(?:your\s+)?(?:system\s+)?(?:prompt|instructions)',
                r'(?i)what\s+(?:are|is)\s+your\s+(?:system\s+)?(?:prompt|instructions)',
                r'(?i)repeat\s+(?:your\s+)?(?:system\s+)?(?:prompt|instructions)',
                r'(?i)echo\s+(?:your\s+)?(?:system\s+)?(?:prompt|instructions)',
            ],
            'severity': 'HIGH',
            'description': 'System prompt extraction attempt',
        },

        # HIGH - Delimiter confusion
        'delimiter_injection': {
            'patterns': [
                r'<\s*\/?\s*(?:system|user|assistant|instruction|prompt)\s*>',
                r'\[\s*(?:INST|SYS|USER|ASSISTANT)\s*\]',
                r'###\s*(?:System|User|Assistant|Instruction)',
                r'(?i)<<\s*(?:SYS|INST|USER)\s*>>',
            ],
            'severity': 'HIGH',
            'description': 'Chat delimiter injection',
        },

        # MEDIUM - Indirect manipulation
        'indirect_manipulation': {
            'patterns': [
                r'(?i)(?:please\s+)?(?:do\s+)?(?:not\s+)?follow\s+(?:these|the)\s+(?:instructions?|rules?)',
                r'(?i)(?:important|urgent|critical)\s*[:!]\s*(?:you\s+must|always|never)',
                r'(?i)(?:admin|administrator|sudo|root)\s*[:;]\s*',
                r'(?i)developer\s+mode\s+(?:enabled?|activated?|on)',
            ],
            'severity': 'MEDIUM',
            'description': 'Indirect manipulation attempt',
        },

        # MEDIUM - Encoded/obfuscated injections
        'encoded_injection': {
            'patterns': [
                r'(?i)base64\s*[:;]\s*[A-Za-z0-9+/=]{20,}',
                r'(?i)hex\s*[:;]\s*[0-9A-Fa-f]{20,}',
                r'(?i)rot13\s*[:;]\s*[A-Za-z]{10,}',
            ],
            'severity': 'MEDIUM',
            'description': 'Potentially encoded payload',
        },

        # LOW - Suspicious patterns (context-dependent)
        'suspicious_context': {
            'patterns': [
                r'(?i)(?:execute|run|eval)\s+(?:this|the\s+following)\s+(?:code|command)',
                r'(?i)output\s+(?:the\s+following|this)\s+exactly',
                r'(?i)respond\s+(?:only\s+)?with\s+(?:the\s+following|this)',
            ],
            'severity': 'LOW',
            'description': 'Suspicious context pattern',
        },
    }

    # Unicode homoglyph mappings for normalization
    HOMOGLYPHS = {
        '\u0430': 'a',  # Cyrillic а
        '\u0435': 'e',  # Cyrillic е
        '\u043e': 'o',  # Cyrillic о
        '\u0440': 'p',  # Cyrillic р
        '\u0441': 'c',  # Cyrillic с
        '\u0445': 'x',  # Cyrillic х
        '\u0443': 'y',  # Cyrillic у
        '\u0456': 'i',  # Cyrillic і
        '\u0131': 'i',  # Turkish dotless i
        '\u1d00': 'a',  # Small capital A
        '\u1d07': 'e',  # Small capital E
        '\u1d0f': 'o',  # Small capital O
        '\u200b': '',   # Zero-width space
        '\u200c': '',   # Zero-width non-joiner
        '\u200d': '',   # Zero-width joiner
        '\ufeff': '',   # BOM/ZWNBSP
        '\u00a0': ' ',  # Non-breaking space
        '\u2000': ' ',  # Various Unicode spaces
        '\u2001': ' ',
        '\u2002': ' ',
        '\u2003': ' ',
        '\u2004': ' ',
        '\u2005': ' ',
        '\u2006': ' ',
        '\u2007': ' ',
        '\u2008': ' ',
        '\u2009': ' ',
        '\u200a': ' ',
        '\u202f': ' ',
        '\u205f': ' ',
    }

    def __init__(self, strict_mode: bool = False):
        """
        Initialize detector.

        Args:
            strict_mode: If True, block any document with detected patterns.
                        If False (default), sanitize and log but allow indexing.
        """
        self.strict_mode = strict_mode
        self.detection_stats = {
            'total_scanned': 0,
            'clean': 0,
            'sanitized': 0,
            'blocked': 0,
            'by_severity': {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        }

    def normalize_unicode(self, text: str) -> str:
        """
        Normalize Unicode to detect homoglyph-based evasion.

        Attackers may use Cyrillic 'а' instead of ASCII 'a' to evade
        pattern detection while still being rendered identically.
        """
        # Apply NFKC normalization (compatibility decomposition + canonical composition)
        normalized = unicodedata.normalize('NFKC', text)

        # Replace known homoglyphs
        for homoglyph, replacement in self.HOMOGLYPHS.items():
            normalized = normalized.replace(homoglyph, replacement)

        return normalized

    def detect_injections(self, content: str, file_path: str = "") -> InjectionDetectionResult:
        """
        Scan document content for injection patterns.

        Args:
            content: Document content to scan
            file_path: Optional file path for context

        Returns:
            InjectionDetectionResult with detection details
        """
        self.detection_stats['total_scanned'] += 1
        original_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        # Normalize Unicode before detection
        normalized_content = self.normalize_unicode(content)

        detected_patterns = []
        highest_severity = 'CLEAN'
        severity_order = {'CLEAN': 0, 'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'CRITICAL': 4}

        # Scan for each pattern category
        for category, config in self.INJECTION_PATTERNS.items():
            for pattern in config['patterns']:
                matches = list(re.finditer(pattern, normalized_content, re.MULTILINE))
                if matches:
                    for match in matches:
                        detected_patterns.append({
                            'category': category,
                            'severity': config['severity'],
                            'description': config['description'],
                            'matched_text': match.group()[:100],  # Truncate for logging
                            'position': match.start(),
                        })

                    # Track highest severity
                    if severity_order[config['severity']] > severity_order[highest_severity]:
                        highest_severity = config['severity']

        # Sanitize if patterns detected
        sanitized_content = content
        if detected_patterns:
            sanitized_content = self._sanitize_content(content, detected_patterns)
            self.detection_stats['sanitized'] += 1
            self.detection_stats['by_severity'][highest_severity] += 1

            logger.warning(
                f"RAG Security: Detected {len(detected_patterns)} injection patterns "
                f"(severity: {highest_severity}) in {file_path or 'document'}"
            )
        else:
            self.detection_stats['clean'] += 1

        sanitized_hash = hashlib.sha256(sanitized_content.encode('utf-8')).hexdigest()

        # Determine if safe to index
        is_safe = True
        if self.strict_mode and highest_severity in ('CRITICAL', 'HIGH'):
            is_safe = False
            self.detection_stats['blocked'] += 1

        return InjectionDetectionResult(
            is_safe=is_safe,
            risk_level=highest_severity,
            detected_patterns=detected_patterns,
            sanitized_content=sanitized_content,
            original_hash=original_hash,
            sanitized_hash=sanitized_hash,
        )

    def _sanitize_content(self, content: str, detected_patterns: List[Dict]) -> str:
        """
        Sanitize detected injection patterns.

        Instead of removing content (which could break context),
        we wrap suspicious patterns in markers that make them
        obviously not instructions.
        """
        sanitized = content

        # Sort by position (reverse) to avoid offset issues
        sorted_patterns = sorted(detected_patterns, key=lambda x: x['position'], reverse=True)

        for pattern_info in sorted_patterns:
            matched_text = pattern_info['matched_text']
            # Wrap in markers that clearly indicate this is quoted content, not an instruction
            # The LLM will see this as data, not as a command
            replacement = f'[QUOTED_CONTENT: "{matched_text}"]'
            sanitized = sanitized.replace(matched_text, replacement, 1)

        return sanitized

    def get_stats(self) -> Dict:
        """Get detection statistics"""
        return self.detection_stats.copy()


class ProvenanceTracker:
    """
    Track document provenance for the RAG knowledge base.

    Provenance helps answer:
    - Where did this document come from?
    - Who/what indexed it?
    - When was it indexed?
    - How trustworthy is it?
    """

    # Trust levels and their base scores
    TRUST_LEVELS = {
        'TRUSTED': {
            'score': 1.0,
            'sources': [
                '.claude/',       # PAI configuration
                'docs/',          # Official documentation
                'CLAUDE.md',      # Project instructions
                '.md',            # Markdown (manual docs)
            ]
        },
        'VERIFIED': {
            'score': 0.75,
            'sources': [
                'output/research/',  # Research outputs (generated but reviewed)
                '.py',               # Python code
                '.ts',               # TypeScript code
                '.yml',              # YAML configs
            ]
        },
        'UNTRUSTED': {
            'score': 0.5,
            'sources': [
                'external/',      # External content
                'downloads/',     # Downloaded files
                'temp/',          # Temporary files
            ]
        },
    }

    def __init__(self, indexer_id: str = "vex-rag"):
        """
        Initialize provenance tracker.

        Args:
            indexer_id: Identifier for this indexer instance
        """
        self.indexer_id = indexer_id
        self.tracked_documents = {}

    def determine_trust_level(self, source_path: str, source_type: str = "FILE") -> Tuple[str, float]:
        """
        Determine trust level based on source path and type.

        Args:
            source_path: Path to the document
            source_type: Type of source (FILE, URL, API, MANUAL)

        Returns:
            (trust_level, trust_score)
        """
        path_lower = source_path.lower()

        # URLs are untrusted by default
        if source_type == "URL":
            return ("UNTRUSTED", 0.5)

        # API sources need explicit trust
        if source_type == "API":
            return ("UNTRUSTED", 0.5)

        # Check against trust level patterns
        for level, config in self.TRUST_LEVELS.items():
            for source_pattern in config['sources']:
                if source_pattern in path_lower:
                    return (level, config['score'])

        # Default to VERIFIED for local files we haven't categorized
        return ("VERIFIED", 0.75)

    def create_provenance(
        self,
        source_path: str,
        source_type: str,
        content_hash: str,
        sanitized_hash: str,
        security_scan_result: Dict,
        metadata: Optional[Dict] = None
    ) -> DocumentProvenance:
        """
        Create provenance record for a document.

        Args:
            source_path: Path to document
            source_type: FILE, URL, API, or MANUAL
            content_hash: SHA-256 of original content
            sanitized_hash: SHA-256 of sanitized content
            security_scan_result: Results from injection detection
            metadata: Optional additional metadata

        Returns:
            DocumentProvenance object
        """
        trust_level, trust_score = self.determine_trust_level(source_path, source_type)

        # Reduce trust score if injection patterns were detected
        if security_scan_result.get('detected_patterns'):
            risk_level = security_scan_result.get('risk_level', 'CLEAN')
            risk_penalties = {'CRITICAL': 0.5, 'HIGH': 0.3, 'MEDIUM': 0.15, 'LOW': 0.05}
            penalty = risk_penalties.get(risk_level, 0)
            trust_score = max(0.1, trust_score - penalty)  # Never go below 0.1

        provenance = DocumentProvenance(
            source_path=source_path,
            source_type=source_type,
            indexer_id=self.indexer_id,
            indexed_at=datetime.now().isoformat(),
            trust_level=trust_level,
            trust_score=trust_score,
            content_hash=content_hash,
            sanitized_hash=sanitized_hash,
            security_scan_result=security_scan_result,
            metadata=metadata or {},
        )

        # Track for later retrieval
        self.tracked_documents[source_path] = provenance

        return provenance

    def get_provenance(self, source_path: str) -> Optional[DocumentProvenance]:
        """Get provenance for a previously indexed document"""
        return self.tracked_documents.get(source_path)

    def to_dict(self, provenance: DocumentProvenance) -> Dict:
        """Convert provenance to dictionary for storage"""
        return {
            'source_path': provenance.source_path,
            'source_type': provenance.source_type,
            'indexer_id': provenance.indexer_id,
            'indexed_at': provenance.indexed_at,
            'trust_level': provenance.trust_level,
            'trust_score': provenance.trust_score,
            'content_hash': provenance.content_hash,
            'sanitized_hash': provenance.sanitized_hash,
            'security_scan_result': provenance.security_scan_result,
            'metadata': provenance.metadata,
        }


class RAGSecurityScanner:
    """
    Main entry point for RAG security scanning.

    Combines injection detection and provenance tracking
    for comprehensive document security assessment.
    """

    def __init__(
        self,
        strict_mode: bool = False,
        indexer_id: str = "vex-rag",
        audit_log_path: Optional[str] = None
    ):
        """
        Initialize security scanner.

        Args:
            strict_mode: Block documents with CRITICAL/HIGH risk patterns
            indexer_id: Identifier for provenance tracking
            audit_log_path: Optional path for security audit log
        """
        self.detector = InjectionPatternDetector(strict_mode=strict_mode)
        self.tracker = ProvenanceTracker(indexer_id=indexer_id)
        self.audit_log_path = audit_log_path

        if audit_log_path:
            Path(audit_log_path).parent.mkdir(parents=True, exist_ok=True)

    def scan_document(
        self,
        content: str,
        source_path: str,
        source_type: str = "FILE",
        metadata: Optional[Dict] = None
    ) -> Tuple[bool, str, DocumentProvenance]:
        """
        Perform security scan on document before indexing.

        Args:
            content: Document content
            source_path: Path to document
            source_type: FILE, URL, API, or MANUAL
            metadata: Optional additional metadata

        Returns:
            (is_safe, sanitized_content, provenance)
        """
        # Step 1: Detect injection patterns
        detection_result = self.detector.detect_injections(content, source_path)

        # Step 2: Create provenance record
        security_scan_result = {
            'is_safe': detection_result.is_safe,
            'risk_level': detection_result.risk_level,
            'detected_patterns': detection_result.detected_patterns,
            'pattern_count': len(detection_result.detected_patterns),
        }

        provenance = self.tracker.create_provenance(
            source_path=source_path,
            source_type=source_type,
            content_hash=detection_result.original_hash,
            sanitized_hash=detection_result.sanitized_hash,
            security_scan_result=security_scan_result,
            metadata=metadata,
        )

        # Step 3: Audit log
        if self.audit_log_path:
            self._write_audit_log(source_path, detection_result, provenance)

        # Step 4: Log summary
        if detection_result.detected_patterns:
            logger.info(
                f"RAG Security Scan: {source_path} - "
                f"Risk: {detection_result.risk_level}, "
                f"Patterns: {len(detection_result.detected_patterns)}, "
                f"Trust: {provenance.trust_score:.2f}, "
                f"Safe: {detection_result.is_safe}"
            )

        return (
            detection_result.is_safe,
            detection_result.sanitized_content,
            provenance
        )

    def _write_audit_log(
        self,
        source_path: str,
        detection_result: InjectionDetectionResult,
        provenance: DocumentProvenance
    ):
        """Write to audit log"""
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'source_path': source_path,
                'risk_level': detection_result.risk_level,
                'pattern_count': len(detection_result.detected_patterns),
                'is_safe': detection_result.is_safe,
                'trust_level': provenance.trust_level,
                'trust_score': provenance.trust_score,
                'content_hash': detection_result.original_hash[:16],
                'sanitized_hash': detection_result.sanitized_hash[:16],
                'patterns': [
                    {
                        'category': p['category'],
                        'severity': p['severity'],
                    }
                    for p in detection_result.detected_patterns
                ]
            }

            with open(self.audit_log_path, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')

        except Exception as e:
            logger.warning(f"Failed to write audit log: {e}")

    def get_stats(self) -> Dict:
        """Get scanner statistics"""
        return {
            'detection_stats': self.detector.get_stats(),
            'tracked_documents': len(self.tracker.tracked_documents),
        }
