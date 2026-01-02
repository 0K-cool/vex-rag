"""
Knowledge Base Indexer - Store contextual chunks in LanceDB

Creates and manages the LanceDB vector database for Vex's knowledge base.
Stores contextual chunks with embeddings for hybrid semantic + keyword search.

Database Location: ~/Personal_AI_Infrastructure/lance_vex_kb/
Security: 100% local storage, encrypted at rest via FileVault
"""

import lancedb
import pyarrow as pa
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import uuid
import hashlib

logger = logging.getLogger(__name__)


class KnowledgeBaseIndexer:
    """Manage LanceDB knowledge base"""

    def __init__(self, db_path: str = "lance_vex_kb"):
        """
        Initialize indexer

        Args:
            db_path: Path to LanceDB database (relative or absolute)
        """
        self.db_path = Path(db_path).expanduser()
        self.db = None
        self.table = None
        self.table_name = "knowledge_base"
        self.indexed_count = 0

        # Create database directory if needed
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def initialize(self):
        """Initialize or connect to LanceDB database"""
        try:
            # Connect to database
            self.db = lancedb.connect(str(self.db_path))
            logger.info(f"Connected to LanceDB at {self.db_path}")

            # Check if table exists
            table_names = self.db.table_names()

            if self.table_name in table_names:
                self.table = self.db.open_table(self.table_name)
                count = len(self.table)
                logger.info(f"Opened existing table '{self.table_name}' ({count} chunks)")
            else:
                logger.info(f"Table '{self.table_name}' will be created on first index")

        except Exception as e:
            logger.error(f"Failed to initialize LanceDB: {e}")
            raise

    def _create_schema(self) -> pa.Schema:
        """
        Create PyArrow schema for knowledge base

        Schema matches Anthropic's contextual retrieval requirements
        """
        return pa.schema([
            # Identifiers
            pa.field("chunk_id", pa.string()),
            pa.field("chunk_index", pa.int32()),

            # Content
            pa.field("original_chunk", pa.string()),
            pa.field("contextual_chunk", pa.string()),
            pa.field("generated_context", pa.string()),

            # Embedding
            pa.field("vector", pa.list_(pa.float32(), 768)),  # nomic-embed-text dimensions

            # Metadata
            pa.field("source_file", pa.string()),
            pa.field("source_project", pa.string()),
            pa.field("file_path", pa.string()),
            pa.field("file_type", pa.string()),
            pa.field("content_hash", pa.string()),  # SHA-256 hash for content-based deduplication

            # Timestamps
            pa.field("indexed_at", pa.string()),
            pa.field("last_updated", pa.string()),

            # Token counts
            pa.field("token_count", pa.int32()),
        ])

    def index_chunks(
        self,
        contextual_chunks: List,
        embeddings: List,
        document_path: str,
        project: str,
        file_type: str,
        content_hash: str
    ) -> int:
        """
        Index contextual chunks with embeddings into LanceDB

        Args:
            contextual_chunks: List of ContextualChunk objects
            embeddings: List of embedding vectors (768-dim each)
            document_path: Path to source document
            project: Project name (PAI, IR-Platform, etc.)
            file_type: File extension (.md, .py, etc.)

        Returns:
            Number of chunks successfully indexed
        """
        if len(contextual_chunks) != len(embeddings):
            logger.error(f"Mismatch: {len(contextual_chunks)} chunks vs {len(embeddings)} embeddings")
            return 0

        # Prepare data for insertion
        data = []
        now = datetime.now().isoformat()

        for ctx_chunk, embedding in zip(contextual_chunks, embeddings):
            if embedding is None:
                logger.warning(f"Skipping chunk {ctx_chunk.chunk_index} (no embedding)")
                continue

            # Create chunk record
            record = {
                "chunk_id": str(uuid.uuid4()),
                "chunk_index": ctx_chunk.chunk_index,
                "original_chunk": ctx_chunk.original_chunk,
                "contextual_chunk": ctx_chunk.contextual_chunk,
                "generated_context": ctx_chunk.generated_context,
                "vector": embedding,
                "source_file": Path(document_path).name,
                "source_project": project,
                "file_path": document_path,
                "file_type": file_type,
                "content_hash": content_hash,  # SHA-256 for content-based deduplication
                "indexed_at": now,
                "last_updated": now,
                "token_count": len(ctx_chunk.original_chunk) // 4,  # Estimate
            }
            data.append(record)

        if not data:
            logger.error(f"No valid chunks to index")
            return 0

        try:
            # Create or append to table
            if self.table is None:
                # Create new table
                self.table = self.db.create_table(
                    self.table_name,
                    data=data,
                    schema=self._create_schema()
                )
                logger.info(f"Created table '{self.table_name}' with {len(data)} chunks")
            else:
                # Append to existing table
                self.table.add(data)
                logger.info(f"Added {len(data)} chunks to '{self.table_name}'")

            self.indexed_count += len(data)
            return len(data)

        except Exception as e:
            logger.error(f"Failed to index chunks: {e}")
            return 0

    def index_document(self, document) -> int:
        """
        Index a complete document through the full RAG pipeline

        This is the high-level method that orchestrates:
        1. Chunking the document
        2. Generating context for each chunk
        3. Embedding contextual chunks
        4. Indexing into LanceDB

        Args:
            document: Document object with content, file_path, and project

        Returns:
            Number of chunks successfully indexed
        """
        from .chunker import SmartChunker
        from .context_generator import ContextGenerator
        from .embedder import Embedder

        logger.info(f"Indexing document: {document.file_path}")

        try:
            # Step 0: Compute content hash for deduplication
            content_hash = hashlib.sha256(document.content.encode('utf-8')).hexdigest()
            logger.info(f"Document content hash: {content_hash[:16]}...")

            # Check for existing chunks from this document (content-based deduplication)
            if self.table is not None:
                try:
                    # Check if document already indexed
                    existing = self.table.search().where(f"file_path = '{document.file_path}'").limit(1).to_list()
                    if existing:
                        existing_hash = existing[0].get('content_hash', None)

                        if existing_hash == content_hash:
                            # Content unchanged - skip re-indexing
                            count_result = self.table.count_rows(f"file_path = '{document.file_path}'")
                            logger.info(f"Document unchanged (hash match) - skipping re-indexing of {count_result} chunks")
                            return count_result
                        else:
                            # Content changed - delete old chunks and re-index
                            count_result = self.table.count_rows(f"file_path = '{document.file_path}'")
                            logger.info(f"Document content changed - removing {count_result} existing chunks before re-indexing")
                            self.table.delete(f"file_path = '{document.file_path}'")
                            logger.info(f"Deleted {count_result} existing chunks for {document.file_path}")
                except Exception as e:
                    logger.warning(f"Could not check for existing chunks: {e}")

            # Step 1: Chunk the document
            chunker = SmartChunker(chunk_size=384, overlap_percentage=0.15)
            chunks = chunker.chunk_document(document.content, Path(document.file_path).suffix)
            logger.info(f"Chunked into {len(chunks)} chunks")

            if not chunks:
                logger.warning(f"No chunks generated from document")
                return 0

            # Step 2: Generate context for each chunk (PARALLEL + SELECTIVE + FASTER MODEL)
            # Using llama3.2:1b for 3-5x speedup vs llama3.1:8b (smaller, faster model)
            context_gen = ContextGenerator(model="llama3.2:1b")
            contextual_chunks = context_gen.generate_contexts_parallel(
                chunks=chunks,
                full_document=document.content,
                file_path=document.file_path,
                project=document.project,
                max_workers=4  # Safe limit for 16GB+ RAM (adjust based on system)
            )

            # Step 3: Embed contextual chunks
            embedder = Embedder(model="nomic-embed-text")
            contextual_texts = [cc.contextual_chunk for cc in contextual_chunks]
            embeddings = embedder.embed_batch(contextual_texts)
            logger.info(f"Generated {len(embeddings)} embeddings")

            # Step 4: Index into LanceDB
            chunk_count = self.index_chunks(
                contextual_chunks,
                embeddings,
                document.file_path,
                document.project,
                Path(document.file_path).suffix,
                content_hash
            )

            logger.info(f"Successfully indexed {chunk_count} chunks from {document.file_path}")
            return chunk_count

        except Exception as e:
            logger.error(f"Document indexing failed: {e}")
            raise

    def search(self, query_embedding: List[float], limit: int = 5) -> List[Dict]:
        """
        Search knowledge base using vector similarity

        Args:
            query_embedding: Query embedding vector (768-dim)
            limit: Number of results to return

        Returns:
            List of matching chunks with metadata
        """
        if self.table is None:
            logger.error(f"No table initialized")
            return []

        try:
            results = (
                self.table
                .search(query_embedding)
                .limit(limit)
                .to_list()
            )
            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def delete_by_file(self, file_path: str) -> int:
        """
        Delete all chunks from a specific file

        Args:
            file_path: Path to file

        Returns:
            Number of chunks deleted
        """
        if self.table is None:
            return 0

        try:
            # LanceDB delete syntax
            self.table.delete(f"file_path = '{file_path}'")
            logger.info(f"Deleted chunks from {file_path}")
            return 1  # LanceDB doesn't return count

        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return 0

    def delete_by_project(self, project: str) -> int:
        """
        Delete all chunks from a specific project

        Args:
            project: Project name

        Returns:
            Number of chunks deleted
        """
        if self.table is None:
            return 0

        try:
            self.table.delete(f"source_project = '{project}'")
            logger.info(f"Deleted chunks from project {project}")
            return 1

        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return 0

    def get_stats(self) -> Dict:
        """Get indexer statistics"""
        stats = {
            'db_path': str(self.db_path),
            'total_indexed': self.indexed_count
        }

        if self.table:
            try:
                stats['total_chunks'] = len(self.table)
            except:
                stats['total_chunks'] = 'unknown'

        return stats

    def create_fts_index(self):
        """
        Create full-text search index for BM25 (Phase 2)
        This will be implemented in Phase 2
        """
        if self.table is None:
            logger.error(f"No table to index")
            return

        try:
            self.table.create_fts_index("contextual_chunk")
            logger.info(f"Created full-text search index")
        except Exception as e:
            logger.error(f"FTS index creation failed: {e}")
