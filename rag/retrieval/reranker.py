"""
Local Reranker - BGE-reranker-large for final ranking

Uses BAAI/bge-reranker-large model via sentence-transformers CrossEncoder.
This is a state-of-the-art reranking model that's 100% local (no cloud APIs).

Performance:
- Better than Cohere rerank-v3 on many benchmarks
- Runs locally on CPU or GPU
- Zero cost (vs $2/million tokens for Cohere)
- Zero data exfiltration risk

Model: https://huggingface.co/BAAI/bge-reranker-large
"""

from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class LocalReranker:
    """Local reranking using BGE-reranker-large"""

    def __init__(self, model_name: str = "BAAI/bge-reranker-large", device: Optional[str] = None):
        """
        Initialize local reranker

        Args:
            model_name: HuggingFace model identifier
            device: Device to run on ('cpu', 'cuda', or None for auto-detect)
        """
        self.model_name = model_name
        self.device = device
        self.model = None
        self.model_loaded = False

    def load_model(self):
        """Lazy-load the CrossEncoder model"""
        if self.model_loaded:
            return True

        try:
            from sentence_transformers import CrossEncoder

            logger.info(f"📥 Loading reranker model: {self.model_name}...")
            logger.info(f"(First load will download ~1.3GB, subsequent loads are fast)")

            self.model = CrossEncoder(self.model_name, device=self.device)
            self.model_loaded = True

            logger.info(f"Reranker model loaded on {self.model.device}")
            return True

        except ImportError:
            logger.error(f"sentence-transformers not installed")
            logger.info(f"Install with: pip install sentence-transformers")
            return False
        except Exception as e:
            logger.error(f"Failed to load reranker model: {e}")
            return False

    def rerank(
        self,
        query: str,
        chunks: List[Dict],
        top_k: int = 5,
        return_scores: bool = True
    ) -> List[Dict]:
        """
        Rerank chunks using BGE-reranker-large

        Args:
            query: Search query
            chunks: List of chunks to rerank (from RRF or other retrieval)
            top_k: Number of top results to return after reranking
            return_scores: Include rerank scores in results

        Returns:
            Reranked list of chunks with scores
        """
        if not chunks:
            return []

        # Lazy-load model on first use
        if not self.model_loaded:
            if not self.load_model():
                logger.warning(f"Reranker unavailable, returning original ranking")
                return chunks[:top_k]

        try:
            # Prepare query-document pairs
            # Use contextual_chunk for reranking (includes context + original chunk)
            pairs = [
                [query, chunk.get('contextual_chunk', chunk.get('original_chunk', ''))]
                for chunk in chunks
            ]

            # Get reranking scores
            scores = self.model.predict(pairs)

            # Combine chunks with scores
            scored_chunks = []
            for chunk, score in zip(chunks, scores):
                chunk_copy = chunk.copy()
                chunk_copy['rerank_score'] = float(score)
                scored_chunks.append(chunk_copy)

            # Sort by rerank score (higher is better)
            reranked = sorted(
                scored_chunks,
                key=lambda x: x['rerank_score'],
                reverse=True
            )

            # Add final rank
            for idx, chunk in enumerate(reranked[:top_k]):
                chunk['final_rank'] = idx + 1

            return reranked[:top_k]

        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            logger.warning(f"Returning original ranking")
            return chunks[:top_k]

    def rerank_batch(
        self,
        queries: List[str],
        chunks_lists: List[List[Dict]],
        top_k: int = 5
    ) -> List[List[Dict]]:
        """
        Rerank multiple queries in batch

        Args:
            queries: List of search queries
            chunks_lists: List of chunk lists (one per query)
            top_k: Number of top results per query

        Returns:
            List of reranked chunk lists
        """
        if not self.model_loaded:
            if not self.load_model():
                return [chunks[:top_k] for chunks in chunks_lists]

        reranked_lists = []
        for query, chunks in zip(queries, chunks_lists):
            reranked = self.rerank(query, chunks, top_k=top_k)
            reranked_lists.append(reranked)

        return reranked_lists

    def get_stats(self) -> Dict:
        """Get reranker statistics"""
        return {
            'model': self.model_name,
            'loaded': self.model_loaded,
            'device': str(self.model.device) if self.model else 'not loaded',
            'type': 'local (100% private)'
        }
