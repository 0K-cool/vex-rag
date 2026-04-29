"""
Unit tests for ContextGenerator AsyncClient socket-leak fix (issue #14).

Verifies:
- generate_contexts_parallel constructs exactly one AsyncClient per call
- The shared AsyncClient's underlying httpx client is closed via _client.aclose()
- The finally block fires even when a task raises an exception
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from dataclasses import dataclass

from rag.indexing.context_generator import ContextGenerator, ContextualChunk


# ---------------------------------------------------------------------------
# Minimal stub for Chunk objects expected by generate_contexts_parallel
# ---------------------------------------------------------------------------

@dataclass
class _FakeChunk:
    """Minimal stand-in for rag.indexing.chunker.Chunk"""
    text: str


def _make_qualifying_chunks(n: int) -> list:
    """Return n chunks whose text is long enough to pass _should_generate_context."""
    return [_FakeChunk(text="A" * 200 + f" chunk {i}") for i in range(n)]


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _build_generator_with_patched_sync_client(mock_sync_cls):
    """Construct a ContextGenerator using the already-patched ollama.Client class."""
    mock_sync_instance = MagicMock()
    mock_sync_instance.list.return_value = {"models": [{"name": "llama3.1:8b"}]}
    mock_sync_cls.return_value = mock_sync_instance
    return ContextGenerator()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestContextGeneratorAsyncClientLeak:
    """Tests for the one-client-per-call fix (issue #14)."""

    def test_generate_contexts_parallel_constructs_one_client(self):
        """AsyncClient must be instantiated exactly once per generate_contexts_parallel call."""
        chunks = _make_qualifying_chunks(3)

        with patch("rag.indexing.context_generator.ollama.Client") as mock_sync_cls, \
             patch("rag.indexing.context_generator.ollama.AsyncClient") as mock_async_cls:

            gen = _build_generator_with_patched_sync_client(mock_sync_cls)

            # Each task calls client.generate(); make it return a valid response
            mock_async_instance = MagicMock()
            mock_async_instance.generate = AsyncMock(
                return_value={"response": "This chunk describes feature initialization."}
            )
            # Today's ollama-python AsyncClient lacks public close(); production
            # code falls back to _client.aclose(). Simulate that by deleting close.
            del mock_async_instance.close
            mock_async_instance._client = MagicMock()
            mock_async_instance._client.aclose = AsyncMock()
            mock_async_cls.return_value = mock_async_instance

            gen.generate_contexts_parallel(
                chunks=chunks,
                full_document="Full document content for testing purposes.",
                file_path="test.md",
                project="test-project",
            )

            # AsyncClient constructor called exactly once regardless of chunk count
            mock_async_cls.assert_called_once_with(timeout=gen._ollama_timeout)

    def test_generate_contexts_parallel_uses_close_when_available(self):
        """When the installed library exposes public close(), it's preferred over the httpx fallback."""
        chunks = _make_qualifying_chunks(3)

        with patch("rag.indexing.context_generator.ollama.Client") as mock_sync_cls, \
             patch("rag.indexing.context_generator.ollama.AsyncClient") as mock_async_cls:

            gen = _build_generator_with_patched_sync_client(mock_sync_cls)

            mock_async_instance = MagicMock()
            mock_async_instance.generate = AsyncMock(
                return_value={"response": "ok"}
            )
            # Future ollama-python: public close() exists and works.
            mock_async_instance.close = AsyncMock()
            mock_async_instance._client = MagicMock()
            mock_async_instance._client.aclose = AsyncMock()
            mock_async_cls.return_value = mock_async_instance

            gen.generate_contexts_parallel(
                chunks=chunks,
                full_document="doc",
                file_path="test.md",
                project="test-project",
            )

            # Public close() preferred; httpx fallback NOT called
            mock_async_instance.close.assert_awaited_once()
            mock_async_instance._client.aclose.assert_not_awaited()

    def test_generate_contexts_parallel_closes_client(self):
        """_client.aclose() must be awaited exactly once after processing completes."""
        chunks = _make_qualifying_chunks(3)

        with patch("rag.indexing.context_generator.ollama.Client") as mock_sync_cls, \
             patch("rag.indexing.context_generator.ollama.AsyncClient") as mock_async_cls:

            gen = _build_generator_with_patched_sync_client(mock_sync_cls)

            mock_async_instance = MagicMock()
            mock_async_instance.generate = AsyncMock(
                return_value={"response": "This chunk describes feature initialization."}
            )
            del mock_async_instance.close  # match real ollama-python 0.6.x
            mock_async_instance._client = MagicMock()
            mock_async_instance._client.aclose = AsyncMock()
            mock_async_cls.return_value = mock_async_instance

            gen.generate_contexts_parallel(
                chunks=chunks,
                full_document="Full document content for testing purposes.",
                file_path="test.md",
                project="test-project",
            )

            # aclose() awaited exactly once via the AttributeError fallback
            mock_async_instance._client.aclose.assert_awaited_once()

    def test_generate_contexts_parallel_closes_client_on_error(self):
        """_client.aclose() must still be awaited when a task raises an exception."""
        chunks = _make_qualifying_chunks(3)

        with patch("rag.indexing.context_generator.ollama.Client") as mock_sync_cls, \
             patch("rag.indexing.context_generator.ollama.AsyncClient") as mock_async_cls:

            gen = _build_generator_with_patched_sync_client(mock_sync_cls)

            mock_async_instance = MagicMock()
            # Simulate a network error on every generate call
            mock_async_instance.generate = AsyncMock(
                side_effect=ConnectionError("ollama unreachable")
            )
            del mock_async_instance.close  # match real ollama-python 0.6.x
            mock_async_instance._client = MagicMock()
            mock_async_instance._client.aclose = AsyncMock()
            mock_async_cls.return_value = mock_async_instance

            # Errors inside tasks are caught by _generate_context_async's own try/except,
            # so generate_contexts_parallel should not raise — it returns partial results.
            result = gen.generate_contexts_parallel(
                chunks=chunks,
                full_document="Full document content for testing purposes.",
                file_path="test.md",
                project="test-project",
            )

            # No results (all tasks failed), but no exception propagated
            assert isinstance(result, list)

            # aclose() still awaited despite task failures
            mock_async_instance._client.aclose.assert_awaited_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
