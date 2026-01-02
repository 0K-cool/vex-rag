"""
Vex RAG Retrieval Module

Implements hybrid search with vector search, BM25, RRF fusion, and BGE reranking.
"""

from rag.retrieval.pipeline import RetrievalPipeline
from rag.retrieval.vector_search import VectorSearch
from rag.retrieval.bm25_search import BM25Search
from rag.retrieval.fusion import reciprocal_rank_fusion, get_fusion_stats
from rag.retrieval.reranker import LocalReranker

__all__ = [
    "RetrievalPipeline",
    "VectorSearch",
    "BM25Search",
    "reciprocal_rank_fusion",
    "get_fusion_stats",
    "LocalReranker",
]
