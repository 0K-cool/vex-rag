"""
Notification Models - Data structures for indexing progress events

Defines the stages of the indexing pipeline and progress event structure
for the pluggable notification system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional


class IndexingStage(Enum):
    """Pipeline stages for indexing progress tracking"""
    LOADING = auto()     # Document loading from disk
    SECURITY = auto()    # RAG security scan (anti-poisoning)
    CHUNKING = auto()    # Document chunking
    CONTEXT = auto()     # Context generation (LLM - slowest stage)
    EMBEDDING = auto()   # Embedding generation
    INDEXING = auto()    # LanceDB write
    COMPLETE = auto()    # Successfully finished
    ERROR = auto()       # Failed with error


# Stage display configuration (emoji, description)
STAGE_INFO = {
    IndexingStage.LOADING: ("📄", "Loading document"),
    IndexingStage.SECURITY: ("🔒", "Security scan"),
    IndexingStage.CHUNKING: ("✂️", "Chunking"),
    IndexingStage.CONTEXT: ("🧠", "Generating context"),
    IndexingStage.EMBEDDING: ("🔢", "Embedding"),
    IndexingStage.INDEXING: ("💾", "Indexing"),
    IndexingStage.COMPLETE: ("✅", "Complete"),
    IndexingStage.ERROR: ("❌", "Error"),
}


@dataclass
class ProgressEvent:
    """
    Progress event emitted during indexing pipeline.

    Attributes:
        stage: Current pipeline stage
        message: Human-readable progress message
        current: Current item number (for progress tracking)
        total: Total items to process (for progress tracking)
        timestamp: When the event occurred
        file_path: Path to file being indexed (optional)
        error: Error message if stage is ERROR (optional)
    """
    stage: IndexingStage
    message: str
    current: int = 0
    total: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    file_path: Optional[str] = None
    error: Optional[str] = None

    @property
    def percentage(self) -> float:
        """Calculate completion percentage (0-100)"""
        if self.total == 0:
            return 0.0
        return (self.current / self.total) * 100.0

    @property
    def is_complete(self) -> bool:
        """Check if this is a completion event"""
        return self.stage == IndexingStage.COMPLETE

    @property
    def is_error(self) -> bool:
        """Check if this is an error event"""
        return self.stage == IndexingStage.ERROR

    @property
    def emoji(self) -> str:
        """Get emoji for current stage"""
        return STAGE_INFO.get(self.stage, ("❓", "Unknown"))[0]

    @property
    def stage_description(self) -> str:
        """Get description for current stage"""
        return STAGE_INFO.get(self.stage, ("❓", "Unknown"))[1]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "stage": self.stage.name,
            "message": self.message,
            "current": self.current,
            "total": self.total,
            "percentage": round(self.percentage, 1),
            "timestamp": self.timestamp.isoformat(),
            "file_path": self.file_path,
            "error": self.error,
        }

    def __str__(self) -> str:
        """Human-readable string representation"""
        if self.total > 0:
            return f"{self.emoji} {self.message} [{self.current}/{self.total}] ({self.percentage:.0f}%)"
        return f"{self.emoji} {self.message}"
