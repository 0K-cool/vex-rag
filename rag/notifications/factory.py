"""Notifier Factory - Create notifiers from configuration"""

import logging
from typing import Dict, Any, List, Optional

from .models import IndexingStage
from .interface import NotifierInterface
from .null import NullNotifier
from .console import ConsoleNotifier
from .webhook import WebhookNotifier
from .composite import CompositeNotifier

logger = logging.getLogger(__name__)


def _parse_stages(stage_names: List[str]) -> List[IndexingStage]:
    stages = []
    for name in stage_names:
        try:
            stages.append(IndexingStage[name.upper()])
        except KeyError:
            logger.warning(f"Unknown stage name: {name}")
    return stages


def create_notifier_from_config(config: Dict[str, Any]) -> NotifierInterface:
    """Create a notifier from configuration dictionary."""
    notifications_config = config.get("notifications", {})
    if not notifications_config:
        return NullNotifier()

    notifiers: List[NotifierInterface] = []

    # Console notifier
    console_config = notifications_config.get("console", {})
    if console_config.get("enabled", True):
        notifiers.append(ConsoleNotifier(
            show_progress_bar=console_config.get("show_progress_bar", True),
            verbose=console_config.get("verbose", False),
        ))

    # Webhook notifier
    webhook_config = notifications_config.get("webhook", {})
    if webhook_config.get("enabled", False):
        url = webhook_config.get("url", "")
        if url:
            notify_stages = None
            if "notify_stages" in webhook_config:
                notify_stages = _parse_stages(webhook_config["notify_stages"])
            notifiers.append(WebhookNotifier(
                url=url,
                template=webhook_config.get("template", "discord"),
                notify_stages=notify_stages,
                min_interval=webhook_config.get("min_interval", 2.0),
                headers=webhook_config.get("headers", {}),
                timeout=webhook_config.get("timeout", 10),
            ))

    if not notifiers:
        return NullNotifier()
    elif len(notifiers) == 1:
        return notifiers[0]
    else:
        return CompositeNotifier(notifiers)
