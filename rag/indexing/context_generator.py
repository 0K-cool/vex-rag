"""
Context Generator - Generate situating context for chunks using Llama 3.1 8B

Implements Anthropic's Contextual Retrieval approach:
- Use local LLM (Llama 3.1 8B) to generate context for each chunk
- Context explains where chunk sits in overall document
- Improves retrieval accuracy by 49% vs traditional RAG

Security: 100% local processing (no cloud APIs, no data exfiltration)
"""

import ollama
from typing import Optional, List, TYPE_CHECKING
from dataclasses import dataclass
import logging
import asyncio

# Type hints for notification system (avoid circular imports)
if TYPE_CHECKING:
    from rag.notifications import NotifierInterface

logger = logging.getLogger(__name__)


@dataclass
class ContextualChunk:
    """Chunk with generated context"""
    original_chunk: str
    generated_context: str
    contextual_chunk: str  # context + original_chunk
    chunk_index: int


class ContextGenerator:
    """Generate contextual information for chunks using local Llama 3.1 8B"""

    def __init__(
        self,
        model: str = "llama3.1:8b",
        temperature: float = 0.3,
        max_tokens: int = 100
    ):
        """
        Initialize context generator

        Args:
            model: Ollama model to use (llama3.1:8b for M1 16GB)
            temperature: Lower = more focused (0.3 recommended)
            max_tokens: Max tokens for context (100 recommended)
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.generation_count = 0

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
                raise ValueError(f"Model {self.model} not found. Available: {available}")
        except ValueError:
            # Re-raise ValueError (model not found)
            raise
        except Exception as e:
            # Only log warning for other exceptions (connection issues, etc.)
            logger.warning(f"Could not verify Ollama model availability: {e}")

    def generate_context(
        self,
        full_document: str,
        chunk: str,
        file_path: str,
        project: str
    ) -> Optional[str]:
        """
        Generate situating context for a chunk

        Args:
            full_document: Complete document content
            chunk: Specific chunk to generate context for
            file_path: Path to source file
            project: Project name (PAI, IR-Platform, etc.)

        Returns:
            Generated context string or None if generation fails
        """
        # Build prompt (Anthropic's recommended format)
        prompt = f"""<document>
{full_document}
</document>

Here is the chunk we want to situate within the whole document:
<chunk>
{chunk}
</chunk>

Please give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else."""

        try:
            # Generate context using Llama 3.1 8B
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                options={
                    'temperature': self.temperature,
                    'num_predict': self.max_tokens,
                }
            )

            context = response['response'].strip()

            # Validate context
            if not context or len(context) < 10:
                logger.warning(f"Generated context too short for chunk in {file_path}")
                return None

            self.generation_count += 1
            return context

        except Exception as e:
            logger.error(f"Context generation failed for {file_path}: {e}")
            return None

    async def _generate_context_async(
        self,
        full_document: str,
        chunk: str,
        file_path: str,
        project: str,
        chunk_index: int,
        semaphore: asyncio.Semaphore
    ) -> Optional[ContextualChunk]:
        """
        Async version of generate_context for parallel processing

        Args:
            full_document: Complete document content
            chunk: Specific chunk to generate context for
            file_path: Path to source file
            project: Project name
            chunk_index: Index of this chunk
            semaphore: Semaphore to limit concurrency

        Returns:
            ContextualChunk object or None if generation fails
        """
        async with semaphore:
            # Build prompt
            prompt = f"""<document>
{full_document}
</document>

Here is the chunk we want to situate within the whole document:
<chunk>
{chunk}
</chunk>

Please give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else."""

            try:
                # Use AsyncClient for concurrent requests
                client = ollama.AsyncClient()
                response = await client.generate(
                    model=self.model,
                    prompt=prompt,
                    options={
                        'temperature': self.temperature,
                        'num_predict': self.max_tokens,
                    }
                )

                context = response['response'].strip()

                # Validate context
                if not context or len(context) < 10:
                    logger.warning(f"Generated context too short for chunk {chunk_index}")
                    return None

                self.generation_count += 1

                # Create ContextualChunk object
                return ContextualChunk(
                    original_chunk=chunk,
                    generated_context=context,
                    contextual_chunk=f"{context}\n\n{chunk}",
                    chunk_index=chunk_index
                )

            except Exception as e:
                logger.error(f"Async context generation failed for chunk {chunk_index}: {e}")
                return None

    def _should_generate_context(self, chunk_text: str) -> bool:
        """
        Determine if a chunk needs context generation (selective optimization)

        Skips chunks that are self-contained or don't benefit from context:
        - Headers/titles (markdown #, ##, ###)
        - Code blocks (```language)
        - Very short chunks (<100 chars)
        - Pure list items without explanation
        - Table rows

        Args:
            chunk_text: The chunk content to evaluate

        Returns:
            True if context should be generated, False to skip
        """
        text = chunk_text.strip()

        # Skip very short chunks (likely headers or list items)
        if len(text) < 100:
            return False

        # Skip markdown headers (self-contained)
        if text.startswith('#'):
            return False

        # Skip code blocks (already clear context)
        if text.startswith('```') or '```' in text[:50]:
            return False

        # Skip pure list items (single line starting with -, *, 1., etc.)
        lines = text.split('\n')
        if len(lines) <= 2 and any(text.startswith(prefix) for prefix in ['- ', '* ', '1. ', '2. ', '3. ']):
            return False

        # Skip table rows (markdown tables)
        if text.startswith('|') and text.count('|') > 2:
            return False

        # Generate context for everything else (paragraphs, explanations, etc.)
        return True

    def generate_contexts_parallel(
        self,
        chunks: List,
        full_document: str,
        file_path: str,
        project: str,
        max_workers: int = 4,
        notifier: Optional["NotifierInterface"] = None
    ) -> List[ContextualChunk]:
        """
        Generate contexts for multiple chunks in parallel (4-8x speedup)
        Uses selective generation to skip chunks that don't need context (40-60% reduction)

        Args:
            chunks: List of Chunk objects to process
            full_document: Complete document content
            file_path: Path to source file
            project: Project name
            max_workers: Max parallel workers (4-6 recommended for 16GB+ RAM)
            notifier: Optional progress notifier for UI updates (default: None)

        Returns:
            List of ContextualChunk objects (skips failed generations)
        """
        # Import notification models for progress events
        from rag.notifications import ProgressEvent, IndexingStage, NullNotifier

        # Use null notifier if none provided
        if notifier is None:
            notifier = NullNotifier()

        # Track progress for notifications
        progress_state = {"completed": 0, "total": 0}

        async def _process_all():
            # Create semaphore to limit concurrency
            semaphore = asyncio.Semaphore(max_workers)

            # Filter chunks that need context generation (selective optimization)
            chunks_needing_context = []
            chunks_skipped = []

            for idx, chunk in enumerate(chunks):
                if self._should_generate_context(chunk.text):
                    chunks_needing_context.append((idx, chunk))
                else:
                    # Create ContextualChunk without LLM generation (use original as context)
                    chunks_skipped.append(ContextualChunk(
                        original_chunk=chunk.text,
                        generated_context="",  # No context needed
                        contextual_chunk=chunk.text,  # Just use original
                        chunk_index=idx
                    ))

            logger.info(f"Selective generation: {len(chunks_needing_context)} chunks need context, {len(chunks_skipped)} skipped (self-contained)")

            # Set total for progress tracking
            progress_state["total"] = len(chunks_needing_context)

            # Initial progress notification
            notifier.notify(ProgressEvent(
                stage=IndexingStage.CONTEXT,
                message=f"Generating context for {len(chunks_needing_context)} chunks",
                current=0,
                total=len(chunks_needing_context),
                file_path=file_path
            ))

            # Create tasks only for chunks that need context
            tasks = [
                self._generate_context_async(
                    full_document=full_document,
                    chunk=chunk.text,
                    file_path=file_path,
                    project=project,
                    chunk_index=idx,
                    semaphore=semaphore
                )
                for idx, chunk in chunks_needing_context
            ]

            # Process chunks needing context in parallel with progress tracking
            if tasks:
                logger.info(f"Processing {len(tasks)} chunks in parallel (max {max_workers} workers)...")
                generated_chunks = []

                # Process with progress updates
                for coro in asyncio.as_completed(tasks):
                    result = await coro
                    if result is not None:
                        generated_chunks.append(result)

                    # Update progress
                    progress_state["completed"] += 1
                    notifier.notify(ProgressEvent(
                        stage=IndexingStage.CONTEXT,
                        message=f"Generating context",
                        current=progress_state["completed"],
                        total=progress_state["total"],
                        file_path=file_path
                    ))
            else:
                generated_chunks = []

            # Combine generated and skipped chunks
            all_chunks = generated_chunks + chunks_skipped
            logger.info(f"Total: {len(all_chunks)} chunks ready ({len(generated_chunks)} generated, {len(chunks_skipped)} skipped)")

            return all_chunks

        # Run async event loop (handle both sync and async contexts)
        try:
            # Check if event loop is already running (e.g., in MCP server)
            asyncio.get_running_loop()
            # Event loop running - execute in new thread to avoid conflict
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(lambda: asyncio.run(_process_all()))
                return future.result()
        except RuntimeError:
            # No running event loop - safe to use asyncio.run()
            return asyncio.run(_process_all())

    def create_contextual_chunk(
        self,
        full_document: str,
        chunk_text: str,
        chunk_index: int,
        file_path: str,
        project: str
    ) -> Optional[ContextualChunk]:
        """
        Create a contextual chunk (context + original chunk)

        Args:
            full_document: Complete document
            chunk_text: Chunk text
            chunk_index: Chunk position in document
            file_path: Source file path
            project: Project name

        Returns:
            ContextualChunk object or None if generation fails
        """
        # Generate context
        context = self.generate_context(full_document, chunk_text, file_path, project)

        if not context:
            # Fallback: Create minimal context from file path
            context = f"This is from {file_path} in the {project} project."

        # Combine context + chunk
        contextual_chunk = f"{context}\n\n{chunk_text}"

        return ContextualChunk(
            original_chunk=chunk_text,
            generated_context=context,
            contextual_chunk=contextual_chunk,
            chunk_index=chunk_index
        )

    def batch_generate(
        self,
        full_document: str,
        chunks: list,
        file_path: str,
        project: str,
        show_progress: bool = True
    ) -> list:
        """
        Generate contexts for multiple chunks

        Args:
            full_document: Complete document
            chunks: List of Chunk objects
            file_path: Source file path
            project: Project name
            show_progress: Show progress updates

        Returns:
            List of ContextualChunk objects
        """
        contextual_chunks = []

        for i, chunk in enumerate(chunks):
            if show_progress and i % 5 == 0:
                logger.info(f"Generating context {i+1}/{len(chunks)}...")

            ctx_chunk = self.create_contextual_chunk(
                full_document=full_document,
                chunk_text=chunk.text,
                chunk_index=chunk.chunk_index,
                file_path=file_path,
                project=project
            )

            if ctx_chunk:
                contextual_chunks.append(ctx_chunk)

        if show_progress:
            logger.info(f"Generated {len(contextual_chunks)} contextual chunks")

        return contextual_chunks

    def get_stats(self):
        """Get generation statistics"""
        return {
            'total_generated': self.generation_count,
            'model': self.model
        }
