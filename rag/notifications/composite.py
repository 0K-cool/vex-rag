"""Composite Notifier - Combine multiple notifiers"""

from typing import List

from .models import ProgressEvent
from .interface import NotifierInterface


class CompositeNotifier:
    """Combines multiple notifiers into one."""

    def __init__(self, notifiers: List[NotifierInterface]):
        self.notifiers = notifiers

    def notify(self, event: ProgressEvent) -> None:
        for n in self.notifiers:
            try:
                n.notify(event)
            except Exception:
                pass

    def start(self, file_path: str, total_stages: int = 6) -> None:
        for n in self.notifiers:
            try:
                n.start(file_path, total_stages)
            except Exception:
                pass

    def finish(self, success: bool, message: str = "") -> None:
        for n in self.notifiers:
            try:
                n.finish(success, message)
            except Exception:
                pass

    def add(self, notifier: NotifierInterface) -> None:
        self.notifiers.append(notifier)

    def remove(self, notifier: NotifierInterface) -> bool:
        try:
            self.notifiers.remove(notifier)
            return True
        except ValueError:
            return False

    def __len__(self) -> int:
        return len(self.notifiers)
