"""
Vector Search - Semantic similarity search using LanceDB

Uses nomic-embed-text embeddings (768-dim) for semantic matching.
Leverages LanceDB's vector search with cosine similarity.
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

from rag.indexing.embedder import Embedder


class VectorSearch:
    """Semantic vector search using LanceDB"""

    def __init__(self, table, embedder: Optional[Embedder] = None):
        """
        Initialize vector search

        Args:
            table: LanceDB table instance
            embedder: Optional Embedder instance (default: creates new one)
        """
        self.table = table
        self.embedder = embedder or Embedder(model="nomic-embed-text")

    def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Search using vector similarity

        Args:
            query: Search query text
            limit: Maximum number of results
            filters: Optional filters (e.g., {"source_project": "PAI"})

        Returns:
            List of matching chunks with metadata and scores
        """
        if not self.table:
            logger.error(f"No table initialized")
            return []

        # Generate query embedding
        query_embedding = self.embedder.embed(query)
        if query_embedding is None:
            logger.error(f"Failed to generate query embedding")
            return []

        try:
            # Execute vector search
            search_query = self.table.search(query_embedding).limit(limit)

            # Apply filters if provided
            if filters:
                for key, value in filters.items():
                    search_query = search_query.where(f"{key} = '{value}'")

            results = search_query.to_list()

            # Add search metadata
            for idx, result in enumerate(results):
                result['search_rank'] = idx + 1
                result['search_type'] = 'vector'

            return results

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def search_by_project(self, query: str, project: str, limit: int = 10) -> List[Dict]:
        """
        Search within a specific project

        Args:
            query: Search query text
            project: Project name (PAI, IR-Platform, etc.)
            limit: Maximum number of results

        Returns:
            List of matching chunks from the specified project
        """
        return self.search(query, limit=limit, filters={"source_project": project})

    def search_by_file_type(
        self,
        query: str,
        file_type: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        Search within specific file types

        Args:
            query: Search query text
            file_type: File extension (.md, .py, .pdf, etc.)
            limit: Maximum number of results

        Returns:
            List of matching chunks from files of the specified type
        """
        return self.search(query, limit=limit, filters={"file_type": file_type})

    def get_stats(self) -> Dict:
        """Get vector search statistics"""
        return {
            'embedder_model': self.embedder.model,
            'embedding_dimensions': self.embedder.expected_dimensions,
            'total_embeddings_generated': self.embedder.embedding_count
        }
