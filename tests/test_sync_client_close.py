"""
Unit tests for the Embedder + ContextGenerator sync client close() (issue #16).

Verifies the close() helpers tear down the underlying httpx client so that
ResourceWarnings don't fire at process exit.
"""

import pytest
from unittest.mock import patch, MagicMock

from rag.indexing.embedder import Embedder
from rag.indexing.context_generator import ContextGenerator


def _make_pydantic_list_response(model_names):
    """Match ollama 0.6.x ListResponse shape: .get('models', []) returns Pydantic Models."""
    response = MagicMock()
    items = []
    for n in model_names:
        m = MagicMock(spec=['model'])
        m.model = n
        items.append(m)
    response.get.side_effect = lambda key, default=None: items if key == 'models' else default
    return response


class TestEmbedderClose:
    def test_close_calls_underlying_httpx_client(self):
        """close() must reach httpx.Client.close() via the AttributeError fallback."""
        with patch("rag.indexing.embedder.ollama.Client") as mock_cls:
            instance = MagicMock()
            instance.list.return_value = _make_pydantic_list_response(['nomic-embed-text'])
            del instance.close  # match real ollama 0.6.x: no public close()
            instance._client = MagicMock()
            instance._client.close = MagicMock()
            mock_cls.return_value = instance

            e = Embedder(model='nomic-embed-text')
            e.close()
            instance._client.close.assert_called_once()

    def test_close_uses_public_when_available(self):
        """If ollama-python adds public close(), prefer it over the httpx fallback."""
        with patch("rag.indexing.embedder.ollama.Client") as mock_cls:
            instance = MagicMock()
            instance.list.return_value = _make_pydantic_list_response(['nomic-embed-text'])
            instance.close = MagicMock()  # future ollama-python
            instance._client = MagicMock()
            instance._client.close = MagicMock()
            mock_cls.return_value = instance

            e = Embedder(model='nomic-embed-text')
            e.close()
            instance.close.assert_called_once()
            instance._client.close.assert_not_called()


class TestContextGeneratorClose:
    def test_close_calls_underlying_httpx_client(self):
        with patch("rag.indexing.context_generator.ollama.Client") as mock_cls:
            instance = MagicMock()
            instance.list.return_value = _make_pydantic_list_response(['llama3.1:8b'])
            del instance.close
            instance._client = MagicMock()
            instance._client.close = MagicMock()
            mock_cls.return_value = instance

            gen = ContextGenerator(model='llama3.1:8b')
            gen.close()
            instance._client.close.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
