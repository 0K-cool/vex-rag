"""
Vex RAG - 100% Local RAG System with Hybrid Search

A production-ready Retrieval-Augmented Generation (RAG) system with:
- Contextual chunking (Llama 3.1 8B)
- Vector search (nomic-embed-text)
- BM25 keyword search
- Reciprocal Rank Fusion (RRF)
- BGE reranking (Apple Silicon GPU)
- PII sanitization
- Multi-project support

Author: Kelvin Lomboy
License: MIT
Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "Kelvin Lomboy"
__license__ = "MIT"

from rag.indexing.indexer import KnowledgeBaseIndexer
from rag.retrieval.pipeline import RetrievalPipeline

__all__ = [
    "KnowledgeBaseIndexer",
    "RetrievalPipeline",
]
