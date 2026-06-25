"""
rivyou/mongo.py
MongoDB connection helper — single client instance, reused across requests.
"""

import logging
from django.conf import settings

logger = logging.getLogger(__name__)

_client = None
_db = None

search_logs = None
search_history = None


def _init():
    global _client, _db, search_logs, search_history

    if _client is not None:
        return  # Already initialised

    try:
        from pymongo import MongoClient
        from pymongo.errors import ConnectionFailure, ConfigurationError

        _client = MongoClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=3000,  # fail fast if Mongo is unreachable
            connectTimeoutMS=3000,
        )
        # Force a cheap round-trip to confirm the server is reachable
        _client.admin.command("ping")

        _db = _client.get_default_database()          # database encoded in the URI
        search_logs    = _db["search_logs"]
        search_history = _db["search_history"]

        logger.info("MongoDB connected successfully.")

    except Exception as exc:                          # noqa: BLE001
        logger.warning(
            "MongoDB unavailable — logging disabled. Reason: %s", exc
        )
        _client = None
        _db = None
        search_logs = None
        search_history = None


# Initialise eagerly at import time (Django app-startup), but never crash.
try:
    _init()
except Exception as exc:                              # noqa: BLE001
    logger.warning("MongoDB init skipped: %s", exc)