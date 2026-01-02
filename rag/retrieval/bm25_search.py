"""
BM25 Search - Keyword-based search using LanceDB Full-Text Search

BM25 (Best Matching 25) is a probabilistic ranking function for keyword search.
Uses LanceDB's built-in FTS capabilities for efficient keyword matching.
"""

from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class BM25Search:
    """Keyword search using BM25 algorithm via LanceDB FTS"""

    def __init__(self, table):
        """
        Initialize BM25 search

        Args:
            table: LanceDB table instance with FTS index
        """
        self.table = table
        self.fts_enabled = False

    def create_index(self, column: str = "contextual_chunk"):
        """
        Create full-text search index on specified column

        Args:
            column: Column to index (default: contextual_chunk)

        Returns:
            True if index created successfully
        """
        if not self.table:
            logger.error(f"No table initialized")
            return False

        try:
            self.table.create_fts_index(column)
            self.fts_enabled = True
            logger.info(f"Created FTS index on '{column}' column")
            return True

        except Exception as e:
            # Check if index already exists
            if "already exists" in str(e).lower():
                self.fts_enabled = True
                logger.info(f"FTS index already exists on '{column}'")
                return True
            else:
                logger.error(f"Failed to create FTS index: {e}")
                return False

    def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Search using BM25 keyword matching

        Args:
            query: Search query text
            limit: Maximum number of results
            filters: Optional filters (e.g., {"source_project": "PAI"})

        Returns:
            List of matching chunks with metadata and BM25 scores
        """
        if not self.table:
            logger.error(f"No table initialized")
            return []

        if not self.fts_enabled:
            logger.warning(f"FTS index not enabled, attempting to create...")
            if not self.create_index():
                logger.error(f"Cannot perform BM25 search without FTS index")
                return []

        try:
            # Execute FTS search
            # LanceDB FTS returns results ordered by relevance score
            search_query = self.table.search(query, query_type="fts").limit(limit)

            # Apply filters if provided
            if filters:
                for key, value in filters.items():
                    search_query = search_query.where(f"{key} = '{value}'")

            results = search_query.to_list()

            # Add search metadata
            for idx, result in enumerate(results):
                result['search_rank'] = idx + 1
                result['search_type'] = 'bm25'
                # Note: LanceDB FTS returns '_score' field automatically

            return results

        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []

    def search_by_project(self, query: str, project: str, limit: int = 10) -> List[Dict]:
        """
        Search within a specific project using BM25

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
        Search within specific file types using BM25

        Args:
            query: Search query text
            file_type: File extension (.md, .py, .pdf, etc.)
            limit: Maximum number of results

        Returns:
            List of matching chunks from files of the specified type
        """
        return self.search(query, limit=limit, filters={"file_type": file_type})

    def get_stats(self) -> Dict:
        """Get BM25 search statistics"""
        return {
            'fts_enabled': self.fts_enabled,
            'search_algorithm': 'BM25'
        }
