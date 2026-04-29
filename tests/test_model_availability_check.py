"""
Unit tests for the Embedder + ContextGenerator model-availability check (issue #15).

Verifies the check works against both:
- Pydantic Model objects (ollama-python 0.5+)
- Plain dicts (older ollama-python releases or test mocks)

Before this fix, `isinstance(m, dict)` was a silent no-op against Pydantic
responses, so a missing model never raised ValueError as intended.
"""

import pytest
from unittest.mock import patch, MagicMock

from rag.indexing.embedder import Embedder
from rag.indexing.context_generator import ContextGenerator


# ---------------------------------------------------------------------------
# Helpers — simulate ListResponse shape returned by ollama 0.5+ Pydantic API
# ---------------------------------------------------------------------------

def _pydantic_model_obj(model_name: str):
    """A non-dict object exposing `.model` like ollama.ListResponse.models[i]."""
    obj = MagicMock(spec=['model', 'digest', 'size'])
    obj.model = model_name
    # Important: spec=[...] makes hasattr false for anything not listed,
    # which matches today's ollama Pydantic Model surface (no `.name` attr).
    return obj


def _pydantic_list_response(model_names: list):
    """A non-dict object with `.get('models', [])` returning Pydantic-style entries."""
    response = MagicMock()
    response.get.side_effect = lambda key, default=None: (
        [_pydantic_model_obj(n) for n in model_names] if key == 'models' else default
    )
    return response


# ---------------------------------------------------------------------------
# Embedder
# ---------------------------------------------------------------------------

class TestEmbedderModelAvailability:
    def test_pydantic_response_with_target_model_present(self):
        """Pydantic ListResponse containing the target model — no exception."""
        with patch("rag.indexing.embedder.ollama.Client") as mock_cls:
            instance = MagicMock()
            instance.list.return_value = _pydantic_list_response(['nomic-embed-text', 'llama3.1:8b'])
            mock_cls.return_value = instance

            # Should not raise
            Embedder(model='nomic-embed-text')

    def test_pydantic_response_with_target_model_missing(self):
        """Pydantic ListResponse missing the target model — must raise ValueError."""
        with patch("rag.indexing.embedder.ollama.Client") as mock_cls:
            instance = MagicMock()
            instance.list.return_value = _pydantic_list_response(['llama3.1:8b'])
            mock_cls.return_value = instance

            with pytest.raises(ValueError, match=r"Model nomic-embed-text not found"):
                Embedder(model='nomic-embed-text')

    def test_dict_response_backward_compat(self):
        """Older dict-shaped responses still work."""
        with patch("rag.indexing.embedder.ollama.Client") as mock_cls:
            instance = MagicMock()
            instance.list.return_value = {
                'models': [
                    {'model': 'nomic-embed-text'},
                    {'name': 'llama3.1:8b'},  # legacy 'name' key
                ]
            }
            mock_cls.return_value = instance

            Embedder(model='nomic-embed-text')  # no raise
            Embedder(model='llama3.1')  # 'in' match works on legacy 'name' field too


# ---------------------------------------------------------------------------
# ContextGenerator
# ---------------------------------------------------------------------------

class TestContextGeneratorModelAvailability:
    def test_pydantic_response_with_target_model_present(self):
        with patch("rag.indexing.context_generator.ollama.Client") as mock_cls:
            instance = MagicMock()
            instance.list.return_value = _pydantic_list_response(['llama3.1:8b'])
            mock_cls.return_value = instance

            ContextGenerator(model='llama3.1:8b')  # no raise

    def test_pydantic_response_with_target_model_missing(self):
        with patch("rag.indexing.context_generator.ollama.Client") as mock_cls:
            instance = MagicMock()
            instance.list.return_value = _pydantic_list_response(['nomic-embed-text'])
            mock_cls.return_value = instance

            with pytest.raises(ValueError, match=r"Model llama3.1:8b not found"):
                ContextGenerator(model='llama3.1:8b')

    def test_dict_response_backward_compat(self):
        """Older dict-shaped responses still work for ContextGenerator too."""
        with patch("rag.indexing.context_generator.ollama.Client") as mock_cls:
            instance = MagicMock()
            instance.list.return_value = {
                'models': [
                    {'model': 'llama3.1:8b'},
                    {'name': 'nomic-embed-text'},  # legacy 'name' key
                ]
            }
            mock_cls.return_value = instance

            ContextGenerator(model='llama3.1:8b')  # no raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
