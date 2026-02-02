"""
Unit tests for the vex-rag notification system.

Tests cover:
- ProgressEvent and IndexingStage models
- NullNotifier (no-op behavior)
- ConsoleNotifier (output formatting)
- WebhookNotifier (payload generation)
- CompositeNotifier (multi-notifier)
- Factory functions (config-based creation)
"""

import io
import json
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from rag.notifications import (
    IndexingStage,
    ProgressEvent,
    STAGE_INFO,
    NotifierInterface,
    NullNotifier,
    ConsoleNotifier,
    WebhookNotifier,
    CompositeNotifier,
    create_notifier_from_config,
)


class TestIndexingStage:
    """Tests for IndexingStage enum"""

    def test_all_stages_exist(self):
        """Verify all expected stages are defined"""
        expected = ["LOADING", "SECURITY", "CHUNKING", "CONTEXT", "EMBEDDING", "INDEXING", "COMPLETE", "ERROR"]
        actual = [stage.name for stage in IndexingStage]
        assert actual == expected

    def test_stage_info_coverage(self):
        """Verify all stages have emoji and description"""
        for stage in IndexingStage:
            assert stage in STAGE_INFO
            emoji, description = STAGE_INFO[stage]
            assert len(emoji) > 0
            assert len(description) > 0


class TestProgressEvent:
    """Tests for ProgressEvent dataclass"""

    def test_basic_creation(self):
        """Test creating a basic progress event"""
        event = ProgressEvent(
            stage=IndexingStage.LOADING,
            message="Loading document"
        )
        assert event.stage == IndexingStage.LOADING
        assert event.message == "Loading document"
        assert event.current == 0
        assert event.total == 0

    def test_with_progress(self):
        """Test creating event with progress tracking"""
        event = ProgressEvent(
            stage=IndexingStage.CONTEXT,
            message="Generating context",
            current=5,
            total=10
        )
        assert event.current == 5
        assert event.total == 10
        assert event.percentage == 50.0

    def test_percentage_calculation(self):
        """Test percentage calculation edge cases"""
        # Normal case
        event1 = ProgressEvent(stage=IndexingStage.EMBEDDING, message="", current=25, total=100)
        assert event1.percentage == 25.0

        # Zero total (avoid division by zero)
        event2 = ProgressEvent(stage=IndexingStage.EMBEDDING, message="", current=0, total=0)
        assert event2.percentage == 0.0

        # Complete
        event3 = ProgressEvent(stage=IndexingStage.EMBEDDING, message="", current=100, total=100)
        assert event3.percentage == 100.0

    def test_is_complete(self):
        """Test is_complete property"""
        complete_event = ProgressEvent(stage=IndexingStage.COMPLETE, message="Done")
        other_event = ProgressEvent(stage=IndexingStage.LOADING, message="Loading")

        assert complete_event.is_complete is True
        assert other_event.is_complete is False

    def test_is_error(self):
        """Test is_error property"""
        error_event = ProgressEvent(stage=IndexingStage.ERROR, message="Failed", error="Something went wrong")
        other_event = ProgressEvent(stage=IndexingStage.LOADING, message="Loading")

        assert error_event.is_error is True
        assert other_event.is_error is False

    def test_emoji_property(self):
        """Test emoji property returns correct emoji"""
        for stage in IndexingStage:
            event = ProgressEvent(stage=stage, message="test")
            expected_emoji = STAGE_INFO[stage][0]
            assert event.emoji == expected_emoji

    def test_stage_description_property(self):
        """Test stage_description property"""
        event = ProgressEvent(stage=IndexingStage.CHUNKING, message="test")
        assert event.stage_description == "Chunking"

    def test_to_dict(self):
        """Test serialization to dictionary"""
        event = ProgressEvent(
            stage=IndexingStage.EMBEDDING,
            message="Generating embeddings",
            current=10,
            total=50,
            file_path="/path/to/file.md"
        )
        d = event.to_dict()

        assert d["stage"] == "EMBEDDING"
        assert d["message"] == "Generating embeddings"
        assert d["current"] == 10
        assert d["total"] == 50
        assert d["percentage"] == 20.0
        assert d["file_path"] == "/path/to/file.md"
        assert "timestamp" in d

    def test_str_representation(self):
        """Test string representation"""
        event1 = ProgressEvent(stage=IndexingStage.LOADING, message="Loading document")
        assert "Loading document" in str(event1)

        event2 = ProgressEvent(stage=IndexingStage.CONTEXT, message="Generating", current=5, total=10)
        assert "[5/10]" in str(event2)
        assert "50%" in str(event2)


class TestNullNotifier:
    """Tests for NullNotifier (no-op implementation)"""

    def test_implements_interface(self):
        """Verify NullNotifier satisfies NotifierInterface"""
        notifier = NullNotifier()
        assert isinstance(notifier, NotifierInterface)

    def test_methods_are_no_op(self):
        """Verify all methods do nothing (no exceptions)"""
        notifier = NullNotifier()

        # These should all succeed without doing anything
        notifier.start("/path/to/file.md")
        notifier.notify(ProgressEvent(stage=IndexingStage.LOADING, message="test"))
        notifier.finish(success=True, message="done")
        notifier.finish(success=False, message="failed")


class TestConsoleNotifier:
    """Tests for ConsoleNotifier"""

    def test_implements_interface(self):
        """Verify ConsoleNotifier satisfies NotifierInterface"""
        notifier = ConsoleNotifier()
        assert isinstance(notifier, NotifierInterface)

    def test_start_outputs_filename(self):
        """Test start() outputs filename"""
        output = io.StringIO()
        notifier = ConsoleNotifier(output=output, use_colors=False)

        notifier.start("/path/to/document.md")

        output_text = output.getvalue()
        assert "document.md" in output_text
        assert "Indexing" in output_text

    def test_notify_outputs_message(self):
        """Test notify() outputs progress message"""
        output = io.StringIO()
        notifier = ConsoleNotifier(output=output, use_colors=False)

        notifier.start("/path/to/file.md")
        notifier.notify(ProgressEvent(
            stage=IndexingStage.CHUNKING,
            message="Created 10 chunks"
        ))

        output_text = output.getvalue()
        assert "Created 10 chunks" in output_text

    def test_progress_bar_display(self):
        """Test progress bar is displayed"""
        output = io.StringIO()
        notifier = ConsoleNotifier(output=output, show_progress_bar=True, use_colors=False)

        notifier.start("/path/to/file.md")
        notifier.notify(ProgressEvent(
            stage=IndexingStage.EMBEDDING,
            message="Embedding",
            current=5,
            total=10
        ))

        output_text = output.getvalue()
        # Progress bar should contain block characters
        assert "5/10" in output_text

    def test_finish_success(self):
        """Test finish() with success=True"""
        output = io.StringIO()
        notifier = ConsoleNotifier(output=output, use_colors=False)

        notifier.start("/path/to/file.md")
        notifier.finish(success=True, message="Indexed 42 chunks")

        output_text = output.getvalue()
        assert "42 chunks" in output_text

    def test_finish_failure(self):
        """Test finish() with success=False"""
        output = io.StringIO()
        notifier = ConsoleNotifier(output=output, use_colors=False)

        notifier.start("/path/to/file.md")
        notifier.finish(success=False, message="Connection failed")

        output_text = output.getvalue()
        assert "Connection failed" in output_text


class TestWebhookNotifier:
    """Tests for WebhookNotifier"""

    def test_implements_interface(self):
        """Verify WebhookNotifier satisfies NotifierInterface"""
        notifier = WebhookNotifier(url="https://example.com/webhook")
        assert isinstance(notifier, NotifierInterface)

    def test_env_var_expansion(self):
        """Test ${VAR} expansion in URL"""
        with patch.dict("os.environ", {"MY_WEBHOOK": "https://discord.com/api/webhooks/123"}):
            notifier = WebhookNotifier(url="${MY_WEBHOOK}")
            assert notifier.url == "https://discord.com/api/webhooks/123"

    def test_stage_filtering(self):
        """Test notify_stages filtering"""
        notifier = WebhookNotifier(
            url="https://example.com/webhook",
            notify_stages=[IndexingStage.COMPLETE, IndexingStage.ERROR]
        )

        # Should filter LOADING stage
        assert notifier._should_notify(IndexingStage.LOADING) is False
        # Should allow COMPLETE stage
        assert notifier._should_notify(IndexingStage.COMPLETE) is True

    def test_discord_template_structure(self):
        """Test Discord payload structure"""
        from rag.notifications.webhook import WEBHOOK_TEMPLATES

        template = WEBHOOK_TEMPLATES["discord"]

        # Test start payload
        payload = template["start"]("/path/to/file.md", 6)
        assert "embeds" in payload
        assert payload["embeds"][0]["title"] == "📚 Indexing Started"

        # Test finish success payload
        payload = template["finish_success"]("Indexed 42 chunks", 5.5)
        assert "embeds" in payload
        assert payload["embeds"][0]["color"] == 5763719  # Green

    def test_slack_template_structure(self):
        """Test Slack payload structure"""
        from rag.notifications.webhook import WEBHOOK_TEMPLATES

        template = WEBHOOK_TEMPLATES["slack"]

        # Test start payload
        payload = template["start"]("/path/to/file.md", 6)
        assert "blocks" in payload

    def test_generic_template_structure(self):
        """Test generic JSON payload structure"""
        from rag.notifications.webhook import WEBHOOK_TEMPLATES

        template = WEBHOOK_TEMPLATES["generic"]

        # Test progress payload
        event = ProgressEvent(
            stage=IndexingStage.CHUNKING,
            message="Chunking document",
            current=1,
            total=1
        )
        payload = template["progress"](event)
        assert payload["event"] == "indexing_progress"
        assert payload["stage"] == "CHUNKING"


class TestCompositeNotifier:
    """Tests for CompositeNotifier"""

    def test_implements_interface(self):
        """Verify CompositeNotifier satisfies NotifierInterface"""
        notifier = CompositeNotifier([])
        assert isinstance(notifier, NotifierInterface)

    def test_notify_calls_all_notifiers(self):
        """Test notify() calls all child notifiers"""
        mock1 = Mock()
        mock2 = Mock()
        composite = CompositeNotifier([mock1, mock2])

        event = ProgressEvent(stage=IndexingStage.LOADING, message="test")
        composite.notify(event)

        mock1.notify.assert_called_once_with(event)
        mock2.notify.assert_called_once_with(event)

    def test_start_calls_all_notifiers(self):
        """Test start() calls all child notifiers"""
        mock1 = Mock()
        mock2 = Mock()
        composite = CompositeNotifier([mock1, mock2])

        composite.start("/path/to/file.md", 6)

        mock1.start.assert_called_once_with("/path/to/file.md", 6)
        mock2.start.assert_called_once_with("/path/to/file.md", 6)

    def test_finish_calls_all_notifiers(self):
        """Test finish() calls all child notifiers"""
        mock1 = Mock()
        mock2 = Mock()
        composite = CompositeNotifier([mock1, mock2])

        composite.finish(success=True, message="done")

        mock1.finish.assert_called_once_with(True, "done")
        mock2.finish.assert_called_once_with(True, "done")

    def test_continues_on_error(self):
        """Test composite continues if one notifier fails"""
        failing_mock = Mock()
        failing_mock.notify.side_effect = Exception("Webhook failed")
        succeeding_mock = Mock()

        composite = CompositeNotifier([failing_mock, succeeding_mock])
        event = ProgressEvent(stage=IndexingStage.LOADING, message="test")

        # Should not raise, should call second notifier
        composite.notify(event)
        succeeding_mock.notify.assert_called_once()

    def test_add_remove_notifiers(self):
        """Test add() and remove() methods"""
        composite = CompositeNotifier([])
        mock = Mock()

        composite.add(mock)
        assert len(composite) == 1

        composite.remove(mock)
        assert len(composite) == 0


class TestFactory:
    """Tests for factory functions"""

    def test_empty_config_returns_null(self):
        """Test empty config returns NullNotifier"""
        notifier = create_notifier_from_config({})
        assert isinstance(notifier, NullNotifier)

    def test_console_enabled_by_default(self):
        """Test console notifier is enabled by default"""
        config = {
            "notifications": {
                "console": {}  # Empty = use defaults
            }
        }
        notifier = create_notifier_from_config(config)
        assert isinstance(notifier, ConsoleNotifier)

    def test_console_can_be_disabled(self):
        """Test console notifier can be disabled"""
        config = {
            "notifications": {
                "console": {"enabled": False}
            }
        }
        notifier = create_notifier_from_config(config)
        assert isinstance(notifier, NullNotifier)

    def test_webhook_disabled_by_default(self):
        """Test webhook notifier is disabled by default"""
        config = {
            "notifications": {
                "webhook": {}  # Empty = disabled by default
            }
        }
        notifier = create_notifier_from_config(config)
        # Should just be console (webhook not enabled)
        assert isinstance(notifier, ConsoleNotifier)

    def test_composite_for_multiple_notifiers(self):
        """Test CompositeNotifier returned when multiple notifiers enabled"""
        config = {
            "notifications": {
                "console": {"enabled": True},
                "webhook": {
                    "enabled": True,
                    "url": "https://example.com/webhook"
                }
            }
        }
        notifier = create_notifier_from_config(config)
        assert isinstance(notifier, CompositeNotifier)
        assert len(notifier) == 2

    def test_stage_filtering_from_config(self):
        """Test notify_stages parsing from config"""
        config = {
            "notifications": {
                "console": {"enabled": False},
                "webhook": {
                    "enabled": True,
                    "url": "https://example.com/webhook",
                    "notify_stages": ["COMPLETE", "ERROR"]
                }
            }
        }
        notifier = create_notifier_from_config(config)
        assert isinstance(notifier, WebhookNotifier)
        assert notifier.notify_stages == [IndexingStage.COMPLETE, IndexingStage.ERROR]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
