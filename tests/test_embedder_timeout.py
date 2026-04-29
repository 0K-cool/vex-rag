"""
Unit tests for Embedder timeout configuration (issue #12 fix).

Verifies:
- Embedder constructs ollama.Client with the supplied timeout
- Default timeout is 30.0 seconds
- Slow embed calls log a WARNING with elapsed time and backpressure hint
"""

import time
import logging
import pytest
from unittest.mock import patch, MagicMock

from rag.indexing.embedder import Embedder


class TestEmbedderTimeout:
    """Tests for ollama.Client timeout plumbing in Embedder"""

    def test_embedder_constructs_client_with_timeout(self):
        """Embedder(ollama_timeout=15.0) must pass timeout=15.0 to ollama.Client"""
        with patch("rag.indexing.embedder.ollama.Client") as mock_client_cls:
            # Make list() return a valid models response so __init__ doesn't raise
            mock_instance = MagicMock()
            mock_instance.list.return_value = {"models": [{"name": "nomic-embed-text"}]}
            mock_client_cls.return_value = mock_instance

            Embedder(ollama_timeout=15.0)

            mock_client_cls.assert_called_once_with(timeout=15.0)

    def test_embedder_default_timeout_is_30(self):
        """Embedder() with no arguments must use timeout=30.0"""
        with patch("rag.indexing.embedder.ollama.Client") as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.list.return_value = {"models": [{"name": "nomic-embed-text"}]}
            mock_client_cls.return_value = mock_instance

            Embedder()

            mock_client_cls.assert_called_once_with(timeout=30.0)

    def test_slow_embed_logs_warning(self, caplog):
        """Embed calls that exceed slow_embed_warn_secs must emit a WARNING"""
        valid_embedding = [0.1] * 768

        with patch("rag.indexing.embedder.ollama.Client") as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.list.return_value = {"models": [{"name": "nomic-embed-text"}]}

            def slow_embeddings(**kwargs):
                time.sleep(0.1)
                return {"embedding": valid_embedding}

            mock_instance.embeddings.side_effect = slow_embeddings
            mock_client_cls.return_value = mock_instance

            embedder = Embedder(slow_embed_warn_secs=0.05)

            with caplog.at_level(logging.WARNING, logger="rag.indexing.embedder"):
                result = embedder.embed("test text")

        assert result == valid_embedding
        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("backpressure" in msg for msg in warning_messages), (
            f"Expected a backpressure WARNING but got: {warning_messages}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
