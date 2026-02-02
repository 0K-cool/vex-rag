"""
Null Notifier - No-op implementation for backward compatibility
"""

from .models import ProgressEvent


class NullNotifier:
    """No-op notifier implementation."""

    def notify(self, event: ProgressEvent) -> None:
        pass

    def start(self, file_path: str, total_stages: int = 6) -> None:
        pass

    def finish(self, success: bool, message: str = "") -> None:
        pass
