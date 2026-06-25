"""
products/mongo_logger.py
Fire-and-forget logging of search queries to MongoDB.
"""

import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _write(user_id, username, query, total_results, result_ids):
    """Runs in a background thread — never raises."""
    try:
        from rivyou.mongo import search_logs, search_history  # import here to avoid circular deps

        now = datetime.now(tz=timezone.utc)

        if search_logs is not None:
            search_logs.insert_one(
                {
                    "user_id":       user_id,
                    "username":      username,
                    "query":         query,
                    "total_results": total_results,
                    "result_ids":    list(result_ids)[:10],
                    "timestamp":     now,
                }
            )

        if search_history is not None:
            search_history.insert_one(
                {
                    "user_id":   user_id,
                    "username":  username,
                    "query":     query,
                    "timestamp": now,
                }
            )

    except Exception as exc:  # noqa: BLE001
        logger.warning("mongo_logger: failed to write search log — %s", exc)


def log_search(user_id, username, query, total_results, result_ids):
    """
    Enqueue a background write to MongoDB.
    Returns immediately; never blocks the search response.
    """
    t = threading.Thread(
        target=_write,
        args=(user_id, username, query, total_results, result_ids),
        daemon=True,
    )
    t.start()