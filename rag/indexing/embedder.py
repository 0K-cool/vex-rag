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

import time
import ollama
from typing import List, Optional, TYPE_CHECKING
import numpy as np
import logging

if TYPE_CHECKING:
    from rag.notifications import NotifierInterface

logger = logging.getLogger(__name__)


class Embedder:
    """Generate embeddings using nomic-embed-text via Ollama"""

    def __init__(
        self,
        model: str = "nomic-embed-text",
        ollama_timeout: float = 30.0,
        slow_embed_warn_secs: float = 5.0
    ):
        self.model = model
        self.embedding_count = 0
        self.expected_dimensions = 768
        self._client = ollama.Client(timeout=ollama_timeout)
        self._slow_embed_warn_secs = slow_embed_warn_secs

        try:
            models = self._client.list()
            model_list = models.get('models', [])
            available = []
            # ollama-python returns Pydantic Model objects (0.5+) or plain dicts
            # (older releases). The original `isinstance(m, dict)` check was a
            # silent no-op against modern Pydantic responses — see issue #15.
            for m in model_list:
                if isinstance(m, dict):
                    model_name = m.get('model') or m.get('name', '')
                else:
                    model_name = getattr(m, 'model', None) or getattr(m, 'name', None)
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
            _t0 = time.perf_counter()
            response = self._client.embeddings(model=self.model, prompt=text)
            _elapsed = time.perf_counter() - _t0
            if _elapsed > self._slow_embed_warn_secs:
                logger.warning(
                    f"Slow embedding: {_elapsed:.2f}s (threshold {self._slow_embed_warn_secs}s). "
                    f"Ollama may be under backpressure from concurrent clients."
                )
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
