"""
Vex RAG Indexing Module

Handles document loading, chunking, context generation, sanitization, and indexing.
"""

from rag.indexing.indexer import KnowledgeBaseIndexer
from rag.indexing.chunker import SmartChunker, Chunk
from rag.indexing.context_generator import ContextGenerator
from rag.indexing.document_loader import DocumentLoader
from rag.indexing.embedder import Embedder
from rag.indexing.sanitizer import Sanitizer

__all__ = [
    "KnowledgeBaseIndexer",
    "SmartChunker",
    "Chunk",
    "ContextGenerator",
    "DocumentLoader",
    "Embedder",
    "Sanitizer",
]
