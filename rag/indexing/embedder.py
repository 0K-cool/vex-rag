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
from typing import List, Optional, TYPE_CHECKING
import numpy as np
import logging

if TYPE_CHECKING:
    from rag.notifications import NotifierInterface

logger = logging.getLogger(__name__)


class Embedder:
    """Generate embeddings using nomic-embed-text via Ollama"""

    def __init__(self, model: str = "nomic-embed-text"):
        self.model = model
        self.embedding_count = 0
        self.expected_dimensions = 768

        try:
            models = ollama.list()
            model_list = models.get('models', [])
            available = []
            for m in model_list:
                if isinstance(m, dict):
                    model_name = m.get('name') or m.get('model', '')
                    if model_name:
                        available.append(model_name)

            if available and not any(self.model in name for name in available):
                raise ValueError(f"Model {self.model} not found. Run: ollama pull {self.model}")
        except ValueError:
            raise
        except Exception as e:
            logger.warning(f"Could not verify Ollama model availability: {e}")

    def embed(self, text: str) -> Optional[List[float]]:
        try:
            response = ollama.embeddings(model=self.model, prompt=text)
            embedding = response['embedding']
            if len(embedding) != self.expected_dimensions:
                logger.warning(f"Unexpected embedding dimensions: {len(embedding)}")
            self.embedding_count += 1
            return embedding
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None

    def embed_batch(
        self,
        texts: List[str],
        show_progress: bool = True,
        notifier: Optional["NotifierInterface"] = None
    ) -> List[Optional[List[float]]]:
        from rag.notifications import ProgressEvent, IndexingStage, NullNotifier

        if notifier is None:
            notifier = NullNotifier()

        embeddings = []
        total = len(texts)

        notifier.notify(ProgressEvent(
            stage=IndexingStage.EMBEDDING,
            message=f"Generating {total} embeddings",
            current=0,
            total=total
        ))

        for i, text in enumerate(texts):
            if show_progress and i % 10 == 0:
                logger.info(f"Embedding {i+1}/{total}...")

            embedding = self.embed(text)
            embeddings.append(embedding)

            if (i + 1) % 10 == 0 or (i + 1) == total:
                notifier.notify(ProgressEvent(
                    stage=IndexingStage.EMBEDDING,
                    message="Generating embeddings",
                    current=i + 1,
                    total=total
                ))

        if show_progress:
            successful = sum(1 for e in embeddings if e is not None)
            logger.info(f"Generated {successful}/{total} embeddings")

        return embeddings

    def cosine_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    def get_stats(self):
        return {
            'total_embeddings': self.embedding_count,
            'model': self.model,
            'dimensions': self.expected_dimensions
        }
