"""
Vex RAG Indexing Module

Handles document loading, chunking, context generation, sanitization, and indexing.

Security Layers:
- Sanitizer: PII/sensitive data redaction (existing)
- RAGSecurityScanner: Anti-poisoning protection (new - OWASP LLM04, LLM08)
"""

from rag.indexing.indexer import KnowledgeBaseIndexer
from rag.indexing.chunker import SmartChunker, Chunk
from rag.indexing.context_generator import ContextGenerator
from rag.indexing.document_loader import DocumentLoader
from rag.indexing.embedder import Embedder
from rag.indexing.sanitizer import Sanitizer
from rag.indexing.rag_security import (
    RAGSecurityScanner,
    InjectionPatternDetector,
    ProvenanceTracker,
    InjectionDetectionResult,
    DocumentProvenance,
)

__all__ = [
    "KnowledgeBaseIndexer",
    "SmartChunker",
    "Chunk",
    "ContextGenerator",
    "DocumentLoader",
    "Embedder",
    "Sanitizer",
    # Security - Anti-poisoning (OWASP LLM04, LLM08)
    "RAGSecurityScanner",
    "InjectionPatternDetector",
    "ProvenanceTracker",
    "InjectionDetectionResult",
    "DocumentProvenance",
]
