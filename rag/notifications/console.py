"""Console Notifier - Terminal progress display"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, TextIO

from .models import ProgressEvent, IndexingStage, STAGE_INFO


class ConsoleNotifier:
    """Console-based progress notifier with progress bar support."""

    def __init__(
        self,
        output: TextIO = sys.stderr,
        show_progress_bar: bool = True,
        verbose: bool = False,
        use_colors: Optional[bool] = None,
    ):
        self.output = output
        self.show_progress_bar = show_progress_bar
        self.verbose = verbose
        self.use_colors = use_colors if use_colors is not None else (hasattr(output, 'isatty') and output.isatty())
        self._start_time: Optional[datetime] = None
        self._file_path: Optional[str] = None
        self._current_stage: Optional[IndexingStage] = None

    def _color(self, text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.use_colors else text

    def _green(self, text: str) -> str: return self._color(text, "32")
    def _red(self, text: str) -> str: return self._color(text, "31")
    def _cyan(self, text: str) -> str: return self._color(text, "36")
    def _dim(self, text: str) -> str: return self._color(text, "90")

    def _progress_bar(self, current: int, total: int, width: int = 20) -> str:
        if total == 0: return ""
        pct = current / total
        filled = int(width * pct)
        return f"[{'█' * filled}{'░' * (width - filled)}] {current}/{total}"

    def start(self, file_path: str, total_stages: int = 6) -> None:
        self._start_time = datetime.now()
        self._file_path = file_path
        filename = Path(file_path).name
        print(f"\n📚 Indexing: {self._cyan(filename)}", file=self.output)

    def notify(self, event: ProgressEvent) -> None:
        if event.stage != self._current_stage:
            self._current_stage = event.stage
        if event.is_error:
            print(f"   {self._red('❌')} {self._red(event.error or event.message)}", file=self.output)
        elif not event.is_complete:
            emoji = event.emoji
            if event.total > 0 and self.show_progress_bar:
                progress = self._progress_bar(event.current, event.total)
                line = f"   {emoji} {event.message} {self._dim(progress)}"
            else:
                line = f"   {emoji} {event.message}"
            if event.total > 1 and event.current < event.total:
                print(f"\r{line}", end="", file=self.output)
                self.output.flush()
            else:
                if event.total > 1:
                    print(f"\r{line}", file=self.output)
                else:
                    print(line, file=self.output)

    def finish(self, success: bool, message: str = "") -> None:
        duration = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0
        dur_str = f"({duration:.1f}s)"
        if success:
            print(f"   {self._green('✅')} {message or 'Complete'} {self._dim(dur_str)}", file=self.output)
        else:
            print(f"   {self._red('❌')} {message or 'Failed'} {self._dim(dur_str)}", file=self.output)
        self._start_time = None
        self._file_path = None
