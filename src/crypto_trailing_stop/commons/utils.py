import logging
from typing import Any

logger = logging.getLogger(__name__)


def backoff_on_backoff_handler(details: dict[str, Any]) -> None:
    logger.warning(
        f"[Retry {details['tries']}] " + f"Waiting {details['wait']:.2f}s due to {str(details['exception'])}"
    )
