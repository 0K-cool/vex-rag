#!/usr/bin/env python3
"""
Vex Knowledge Base MCP Server (Plugin Version)

Provides MCP (Model Context Protocol) access to the Vex RAG system.
Enables automatic context injection into Claude Code conversations.

This is a configurable version that reads settings from .vex-rag.yml
in the project directory, making it portable across multiple projects.

Resources:
- vex://search/{query} - Search knowledge base and return top results

Tools:
- index_document - Index a new document into knowledge base
- get_kb_stats - Get knowledge base statistics

100% local, zero cloud APIs, zero data exfiltration.
"""

import sys
import signal
import logging
import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("ERROR: FastMCP not installed. Install with: pip install fastmcp", file=sys.stderr)
    sys.exit(1)

from rag.retrieval.pipeline import RetrievalPipeline
from rag.indexing.document_loader import DocumentLoader
from rag.indexing.indexer import KnowledgeBaseIndexer, _validate_path, SecurityError
from rag.indexing.sanitizer import Sanitizer

# Load configuration
def load_config() -> Dict:
    """Load project-specific RAG configuration from .vex-rag.yml"""
    # Get config path from environment or use default
    config_path = Path(os.getenv("RAG_CONFIG", ".vex-rag.yml"))

    # If relative path, resolve from current directory
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path

    if not config_path.exists():
        # Fallback: try parent directory (for MCP server running from subdirectory)
        config_path = Path.cwd().parent / ".vex-rag.yml"

    if not config_path.exists():
        raise FileNotFoundError(
            f"RAG configuration not found: {config_path}\n"
            f"Create .vex-rag.yml in your project root or set RAG_CONFIG environment variable.\n"
            f"See examples in ~/.claude/plugins/vex-rag/examples/"
        )

    with open(config_path) as f:
        return yaml.safe_load(f)

# Load configuration
try:
    config = load_config()
except FileNotFoundError as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)

# Extract configuration values
PROJECT_NAME = config['project']['name']
DB_PATH = config['database']['path']
ENABLE_RERANKING = config['retrieval'].get('enable_reranking', True)
RERANKER_MODEL = config['retrieval'].get('reranker_model', 'BAAI/bge-reranker-large')
DEFAULT_TOP_K = config['retrieval'].get('default_top_k', 5)
ENABLE_SANITIZATION = config['indexing'].get('enable_sanitization', True)
LOG_LEVEL = config.get('logging', {}).get('level', 'INFO')
LOG_FILE = config.get('logging', {}).get('file', '.claude/logs/rag.log')

# Configure logging
# IMPORTANT: Only log to file, NOT stderr. Stderr output causes Claude Code
# to interpret the MCP server as "failed" even during normal shutdown.
log_file_path = Path(LOG_FILE)
log_file_path.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path)
        # Removed StreamHandler(sys.stderr) - causes "MCP server failed" on shutdown
    ]
)
logger = logging.getLogger('vex_kb_server')
logger.info(f"Vex RAG MCP Server starting for project: {PROJECT_NAME}")
logger.info(f"Configuration loaded from: {os.getenv('RAG_CONFIG', '.vex-rag.yml')}")
logger.info(f"Database path: {DB_PATH}")
logger.info(f"Reranking: {'enabled' if ENABLE_RERANKING else 'disabled'}")

# Initialize MCP server
mcp = FastMCP(f"Vex Knowledge Base ({PROJECT_NAME})")

# Initialize retrieval pipeline (lazy-loaded on first use)
_pipeline: Optional[RetrievalPipeline] = None
_indexer: Optional[KnowledgeBaseIndexer] = None

# Graceful shutdown handling
_shutdown_requested = False

def graceful_shutdown(signum, frame):
    """Handle shutdown signals gracefully"""
    global _shutdown_requested, _pipeline, _indexer

    if _shutdown_requested:
        # Already shutting down, force exit
        logger.info("Forced shutdown")
        sys.exit(0)

    _shutdown_requested = True
    signal_name = signal.Signals(signum).name if signum else "UNKNOWN"
    logger.info(f"Received {signal_name} - initiating graceful shutdown...")

    # Cleanup resources
    try:
        if _pipeline is not None:
            logger.info("Closing retrieval pipeline...")
            # Pipeline cleanup if needed
            _pipeline = None

        if _indexer is not None:
            logger.info("Closing indexer...")
            # Indexer cleanup if needed
            _indexer = None

        logger.info("Vex Knowledge Base MCP Server shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

    sys.exit(0)

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGINT, graceful_shutdown)
# SIGHUP for terminal hangup (when Claude Code exits)
if hasattr(signal, 'SIGHUP'):
    signal.signal(signal.SIGHUP, graceful_shutdown)

logger.info("Signal handlers registered for graceful shutdown")


def get_pipeline() -> RetrievalPipeline:
    """Get or initialize retrieval pipeline"""
    global _pipeline
    if _pipeline is None:
        logger.info("Initializing retrieval pipeline...")
        try:
            _pipeline = RetrievalPipeline(
                db_path=DB_PATH,
                enable_reranking=ENABLE_RERANKING,
                reranker_model=RERANKER_MODEL
            )
            logger.info("Retrieval pipeline initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize pipeline: {e}")
            raise
    return _pipeline


def get_indexer() -> KnowledgeBaseIndexer:
    """Get or initialize knowledge base indexer"""
    global _indexer
    if _indexer is None:
        logger.info("Initializing knowledge base indexer...")
        try:
            _indexer = KnowledgeBaseIndexer(db_path=DB_PATH)
            _indexer.initialize()
            logger.info("Indexer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize indexer: {e}")
            raise
    return _indexer


@mcp.resource("vex://search/{query}")
def search_knowledge_base(query: str) -> str:
    """
    Search the Vex knowledge base and return results with native citations.

    This resource enables automatic context injection - when Claude needs
    information about project documentation, it can automatically search
    the knowledge base.

    Results are formatted for Anthropic's native citations API, which means:
    - Cited text doesn't count toward output tokens
    - Citations have guaranteed valid character indices
    - More reliable source attribution

    Args:
        query: Search query (e.g., "git safety check workflow")

    Returns:
        JSON-formatted documents with citations enabled
    """
    logger.info(f"MCP search request: '{query}'")

    try:
        # Get retrieval pipeline
        pipeline = get_pipeline()

        # Execute search with full hybrid pipeline
        results = pipeline.retrieve(
            query,
            top_k=DEFAULT_TOP_K,
            enable_bm25=True,
            verbose=False
        )

        if not results:
            logger.info(f"No results found for query: '{query}'")
            return json.dumps({
                "query": query,
                "documents": [],
                "message": f"No results found for: {query}"
            }, indent=2)

        logger.info(f"Found {len(results)} results for query: '{query}'")

        # Format results with native citations
        citation_docs = pipeline.format_for_citations(
            results,
            include_context=True
        )

        # Create response with metadata
        response = {
            "query": query,
            "documents": citation_docs,
            "message": f"Retrieved {len(citation_docs)} relevant documents from {PROJECT_NAME} knowledge base"
        }

        return json.dumps(response, indent=2)

    except Exception as e:
        error_msg = f"Search failed: {str(e)}"
        logger.error(error_msg)
        return json.dumps({
            "query": query,
            "documents": [],
            "error": error_msg
        }, indent=2)


@mcp.tool()
def index_document(
    file_path: str,
    project: Optional[str] = None,
    enable_sanitization: Optional[bool] = None
) -> str:
    """
    Index a new document into the Vex knowledge base.

    This tool allows manual indexing of documents during conversations.
    Useful for adding new documentation, skills, or workflows on-the-fly.

    Args:
        file_path: Absolute or relative path to document
        project: Project name (default: from config)
        enable_sanitization: Enable PII sanitization (default: from config)

    Returns:
        Status message with indexing results
    """
    # Use config defaults if not specified
    if project is None:
        project = PROJECT_NAME
    if enable_sanitization is None:
        enable_sanitization = ENABLE_SANITIZATION

    logger.info(f"MCP index request: {file_path} (project={project}, sanitize={enable_sanitization})")

    try:
        # Resolve file path
        path = Path(file_path)
        if not path.is_absolute():
            # Assume relative to current project directory
            path = Path.cwd() / file_path

        # Security: Validate path BEFORE loading file (VUL-002 fix)
        # This prevents reading files outside allowed directories
        try:
            validated_path = _validate_path(str(path))
            logger.info(f"Path validated: {validated_path}")
        except SecurityError as e:
            error_msg = f"Path validation failed: {e}"
            logger.error(error_msg)
            return f"ERROR: {error_msg}"

        if not path.exists():
            error_msg = f"File not found: {path}"
            logger.error(error_msg)
            return f"ERROR: {error_msg}"

        # Get indexer
        indexer = get_indexer()

        # Load document
        loader = DocumentLoader()
        doc = loader.load_file(str(path), project)

        # Sanitize if enabled
        if enable_sanitization:
            sanitizer = Sanitizer(enable_ner=True)
            result = sanitizer.sanitize(doc.content, str(path))
            doc.content = result.sanitized_text

            if result.redaction_count > 0:
                logger.info(f"Sanitization: {result.redaction_count} redactions, {len(result.detected_patterns)} patterns")

        # Index document (full pipeline: chunk → context → embed → index)
        chunk_count = indexer.index_document(doc)

        success_msg = f"Successfully indexed {chunk_count} chunks from {path.name}"
        if enable_sanitization:
            success_msg += f" (sanitized)"

        logger.info(success_msg)
        return success_msg

    except Exception as e:
        error_msg = f"Indexing failed: {str(e)}"
        logger.error(error_msg)
        return f"ERROR: {error_msg}"


@mcp.tool()
def get_kb_stats() -> Dict[str, Any]:
    """
    Get statistics about the Vex knowledge base.

    Returns:
        Dictionary with KB stats (total chunks, projects, files, etc.)
    """
    logger.info("MCP stats request")

    try:
        pipeline = get_pipeline()
        stats = pipeline.get_stats()

        logger.info(f"Stats retrieved: {stats['total_chunks']} total chunks")
        return stats

    except Exception as e:
        error_msg = f"Stats retrieval failed: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}


if __name__ == "__main__":
    import atexit

    def cleanup_on_exit():
        """Cleanup handler for atexit (fallback for graceful shutdown)"""
        global _pipeline, _indexer
        if _pipeline is not None or _indexer is not None:
            logger.info("Atexit cleanup triggered")
            _pipeline = None
            _indexer = None

    atexit.register(cleanup_on_exit)

    logger.info(f"Starting Vex Knowledge Base MCP Server for {PROJECT_NAME}...")
    logger.info(f"Python path: {sys.path}")
    logger.info(f"Working directory: {Path.cwd()}")

    try:
        # Run the MCP server (stdio transport)
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user (KeyboardInterrupt)")
        sys.exit(0)
    except SystemExit:
        # Expected during graceful shutdown, don't log as error
        raise
    except (BrokenPipeError, EOFError, ConnectionResetError, ConnectionAbortedError):
        # Expected when Claude Code closes stdin/stdout pipes during shutdown
        # These are normal termination signals, not errors
        logger.info("Server stopped (pipe closed or connection reset)")
        sys.exit(0)
    except OSError as e:
        # Handle "Bad file descriptor" and similar OS-level errors during shutdown
        if e.errno in (9, 32):  # EBADF, EPIPE
            logger.info(f"Server stopped (OS error during shutdown: {e})")
            sys.exit(0)
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        # Log unexpected errors but exit cleanly to avoid "failed" status
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(0)  # Exit 0 even on error to avoid "MCP server failed" message
