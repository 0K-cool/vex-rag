"""
Vex RAG Notifications - Pluggable progress notification system

Provides progress notifications during indexing operations.
Supports console output, webhooks (Discord/Slack/Teams), and custom implementations.

Usage:
    from rag.notifications import ConsoleNotifier, ProgressEvent, IndexingStage

    notifier = ConsoleNotifier()
    notifier.start("/path/to/doc.md")
    notifier.notify(ProgressEvent(
        stage=IndexingStage.CHUNKING,
        message="Chunked document",
        current=1,
        total=1
    ))
    notifier.finish(success=True, message="Indexed 42 chunks")
"""

from .models import IndexingStage, ProgressEvent, STAGE_INFO
from .interface import NotifierInterface
from .null import NullNotifier
from .console import ConsoleNotifier
from .webhook import WebhookNotifier
from .composite import CompositeNotifier
from .factory import create_notifier_from_config

__all__ = [
    # Models
    "IndexingStage",
    "ProgressEvent",
    "STAGE_INFO",
    # Interface
    "NotifierInterface",
    # Implementations
    "NullNotifier",
    "ConsoleNotifier",
    "WebhookNotifier",
    "CompositeNotifier",
    # Factory
    "create_notifier_from_config",
]
