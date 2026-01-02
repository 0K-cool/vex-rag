"""
Embedder - Generate embeddings using nomic-embed-text (local)

Uses Ollama's nomic-embed-text model:
- 100% local (no cloud APIs)
- 768-dimension embeddings
- MTEB score: 62.39 (matches OpenAI text-embedding-3-small)
- Fast: ~12K tokens/second
- Cost: $0 (vs $0.02/1M tokens for OpenAI)

Security: All embeddings generated locally, zero data exfiltration risk
"""

import ollama
from typing import List, Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)


class Embedder:
    """Generate embeddings using nomic-embed-text via Ollama"""

    def __init__(self, model: str = "nomic-embed-text"):
        """
        Initialize embedder

        Args:
            model: Ollama embedding model (default: nomic-embed-text)
        """
        self.model = model
        self.embedding_count = 0
        self.expected_dimensions = 768  # nomic-embed-text dimension

        # Verify model is available
        try:
            models = ollama.list()
            model_list = models.get('models', [])
            # Handle both 'name' and 'model' keys (Ollama API variations)
            available = []
            for m in model_list:
                if isinstance(m, dict):
                    # Try 'name' first, fallback to 'model'
                    model_name = m.get('name') or m.get('model', '')
                    if model_name:
                        available.append(model_name)

            if available and not any(self.model in name for name in available):
                raise ValueError(f"Model {self.model} not found. Run: ollama pull {self.model}")
        except ValueError:
            # Re-raise ValueError (model not found)
            raise
        except Exception as e:
            # Only log warning for other exceptions (connection issues, etc.)
            logger.warning(f"Could not verify Ollama model availability: {e}")

    def embed(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for text

        Args:
            text: Text to embed

        Returns:
            768-dimensional embedding vector or None if embedding fails
        """
        try:
            response = ollama.embeddings(
                model=self.model,
                prompt=text
            )

            embedding = response['embedding']

            # Validate embedding
            if len(embedding) != self.expected_dimensions:
                logger.warning(f"Warning: Unexpected embedding dimensions: {len(embedding)} (expected {self.expected_dimensions})")

            self.embedding_count += 1
            return embedding

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None

    def embed_batch(self, texts: List[str], show_progress: bool = True) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts

        Args:
            texts: List of texts to embed
            show_progress: Show progress updates

        Returns:
            List of embedding vectors
        """
        embeddings = []

        for i, text in enumerate(texts):
            if show_progress and i % 10 == 0:
                logger.info(f"Embedding {i+1}/{len(texts)}...")

            embedding = self.embed(text)
            embeddings.append(embedding)

        if show_progress:
            successful = sum(1 for e in embeddings if e is not None)
            logger.info(f"Generated {successful}/{len(texts)} embeddings")

        return embeddings

    def cosine_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score (-1 to 1, higher = more similar)
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def get_stats(self):
        """Get embedding statistics"""
        return {
            'total_embeddings': self.embedding_count,
            'model': self.model,
            'dimensions': self.expected_dimensions
        }
