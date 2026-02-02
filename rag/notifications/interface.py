"""
Notifier Interface - Protocol definition for notification implementations
"""

from typing import Protocol, runtime_checkable

from .models import ProgressEvent


@runtime_checkable
class NotifierInterface(Protocol):
    """Protocol for progress notification implementations."""

    def notify(self, event: ProgressEvent) -> None:
        """Send a progress notification."""
        ...

    def start(self, file_path: str, total_stages: int = 6) -> None:
        """Signal the start of indexing for a file."""
        ...

    def finish(self, success: bool, message: str = "") -> None:
        """Signal the end of indexing."""
        ...
