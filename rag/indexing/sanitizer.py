"""
Sanitizer - Multi-layer PII/sensitive data sanitization

Implements defense-in-depth sanitization for client data:
- Layer 1: Regex patterns (emails, IPs, phones, SSNs, etc.)
- Layer 2: NER (Named Entity Recognition) for contextual PII
- Layer 3: Manual review workflow

Security Purpose (100% Local Architecture):
- Data at rest protection (disk theft, malware, backups)
- Compliance with client NDAs (PII removal requirements)
- Defense against accidental exposure (sharing, screenshots)
- Future-proofing (safe to migrate if cloud components added)

From security analysis: output/research/vex-rag-security-analysis.md
"""

import re
import spacy
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class SanitizationResult:
    """Result of sanitization process"""
    sanitized_text: str
    detected_patterns: List[str]
    redaction_count: int
    requires_review: bool


class Sanitizer:
    """Multi-layer PII and sensitive data sanitizer"""

    # Regex patterns for automatic detection
    SANITIZATION_PATTERNS = {
        # Contact information
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone": r'\b(?:\+?1[-.]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
        "url": r'https?://[^\s]+',

        # Network identifiers
        "ipv4": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        "ipv6": r'\b(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}\b',
        "mac_address": r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b',
        "domain": r'\b[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}\b',

        # Personal identifiers
        "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
        "credit_card": r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b',

        # Cloud/Server IDs
        "aws_key": r'AKIA[0-9A-Z]{16}',
        "azure_key": r'[a-zA-Z0-9+/]{88}==',

        # API keys (common patterns)
        "api_key": r'["\']?api[_-]?key["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{32,})["\']?',
    }

    # Client-specific patterns (can be customized)
    CLIENT_PATTERNS = {
        "hospital_bella_vista": r'(?i)hospital\s+bella\s+vista',
        "uaa": r'(?i)university\s+of\s+alaska\s+anchorage',
    }

    def __init__(self, enable_ner: bool = True):
        """
        Initialize sanitizer

        Args:
            enable_ner: Enable Named Entity Recognition (spaCy)
        """
        self.enable_ner = enable_ner
        self.nlp = None

        if enable_ner:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except Exception as e:
                logger.warning(f"NER disabled: Could not load spaCy model: {e}")
                self.enable_ner = False

    def is_client_data(self, file_path: str, content: str = None) -> bool:
        """
        Detect if file/content contains client data

        Args:
            file_path: Path to file
            content: Optional file content

        Returns:
            True if client data detected
        """
        client_indicators = [
            '/client-work/',
            '/Cooperton/',
            'TTX',
            'Hospital',
            'UAA',
            'client',
            'engagement',
        ]

        # Check file path
        for indicator in client_indicators:
            if indicator.lower() in file_path.lower():
                return True

        # Check content if provided
        if content:
            for indicator in client_indicators:
                if indicator.lower() in content.lower():
                    return True

        return False

    def sanitize_regex(self, text: str) -> Tuple[str, List[str]]:
        """
        Layer 1: Regex-based sanitization

        Args:
            text: Text to sanitize

        Returns:
            (sanitized_text, detected_patterns)
        """
        sanitized = text
        detected = []

        # Apply standard patterns
        for pattern_name, pattern in self.SANITIZATION_PATTERNS.items():
            matches = re.findall(pattern, text)
            if matches:
                detected.append(f"{pattern_name}: {len(matches)} occurrences")
                replacement = f"[REDACTED_{pattern_name.upper()}]"
                sanitized = re.sub(pattern, replacement, sanitized)

        # Apply client-specific patterns
        for pattern_name, pattern in self.CLIENT_PATTERNS.items():
            matches = re.findall(pattern, text)
            if matches:
                detected.append(f"{pattern_name}: {len(matches)} occurrences")
                replacement = f"[REDACTED_CLIENT]"
                sanitized = re.sub(pattern, replacement, sanitized)

        return sanitized, detected

    def sanitize_ner(self, text: str) -> Tuple[str, List[str]]:
        """
        Layer 2: Named Entity Recognition sanitization

        Args:
            text: Text to sanitize

        Returns:
            (sanitized_text, detected_entities)
        """
        if not self.enable_ner or not self.nlp:
            return text, []

        try:
            doc = self.nlp(text)
            sanitized = text
            detected = []

            # Redact PERSON, ORG, GPE (locations)
            entities_to_redact = {}

            for ent in doc.ents:
                if ent.label_ in ["PERSON", "ORG", "GPE"]:
                    entities_to_redact[ent.text] = f"[REDACTED_{ent.label_}]"
                    detected.append(f"{ent.label_}: {ent.text}")

            # Replace entities (longest first to avoid partial replacements)
            for entity, replacement in sorted(entities_to_redact.items(), key=lambda x: len(x[0]), reverse=True):
                sanitized = sanitized.replace(entity, replacement)

            return sanitized, detected

        except Exception as e:
            logger.error(f"NER sanitization failed: {e}")
            return text, []

    def sanitize(self, text: str, file_path: str = "") -> SanitizationResult:
        """
        Complete multi-layer sanitization

        Args:
            text: Text to sanitize
            file_path: Source file path (for context)

        Returns:
            SanitizationResult object
        """
        # Layer 1: Regex
        sanitized, regex_detected = self.sanitize_regex(text)

        # Layer 2: NER
        sanitized, ner_detected = self.sanitize_ner(sanitized)

        # Combine detections
        all_detected = regex_detected + ner_detected
        redaction_count = len(all_detected)

        # Determine if manual review required
        requires_review = self._requires_manual_review(file_path, text, all_detected)

        return SanitizationResult(
            sanitized_text=sanitized,
            detected_patterns=all_detected,
            redaction_count=redaction_count,
            requires_review=requires_review
        )

    def _requires_manual_review(self, file_path: str, original_text: str, detected: List[str]) -> bool:
        """
        Determine if manual review is required

        Args:
            file_path: Source file path
            original_text: Original text
            detected: List of detected patterns

        Returns:
            True if manual review needed
        """
        # Always review client data
        if self.is_client_data(file_path, original_text):
            return True

        # Review if high number of redactions
        if len(detected) > 10:
            return True

        # Review if specific high-risk patterns found
        high_risk_patterns = ["hospital", "university", "client", "engagement", "ssn", "credit_card"]
        for pattern in high_risk_patterns:
            if any(pattern in d.lower() for d in detected):
                return True

        return False

    def validate_sanitization(self, sanitized_text: str) -> Tuple[bool, List[str]]:
        """
        Validate that no PII remains after sanitization

        Args:
            sanitized_text: Sanitized text to validate

        Returns:
            (is_valid, list_of_failures)
        """
        failures = []

        # Check for common PII patterns
        pii_tests = [
            (r'@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', "Email addresses"),
            (r'\d{3}-\d{2}-\d{4}', "SSN"),
            (r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', "Phone"),
            (r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', "IP address"),
        ]

        for pattern, description in pii_tests:
            if re.search(pattern, sanitized_text):
                failures.append(description)

        return (len(failures) == 0, failures)

    def get_stats(self) -> Dict:
        """Get sanitizer statistics"""
        return {
            'regex_patterns': len(self.SANITIZATION_PATTERNS),
            'client_patterns': len(self.CLIENT_PATTERNS),
            'ner_enabled': self.enable_ner
        }
