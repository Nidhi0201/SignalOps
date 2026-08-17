"""
Redis connection + stream configuration for the async ingestion pipeline.

Producers XADD to LOG_STREAM (bounded by LOG_STREAM_MAXLEN, approximate trim).
Consumers read via the LOG_GROUP consumer group; entries that exhaust retries
go to LOG_DLQ_STREAM.
"""
import os

import redis

LOG_STREAM = os.getenv("LOG_STREAM", "logs:stream")
LOG_GROUP = os.getenv("LOG_GROUP", "ingest-workers")
LOG_DLQ_STREAM = os.getenv("LOG_DLQ_STREAM", "logs:deadletter")
# Bounded stream: keep at most ~this many entries so producer memory is capped.
LOG_STREAM_MAXLEN = int(os.getenv("LOG_STREAM_MAXLEN", "1000000"))

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """FastAPI dependency / shared client (redis-py pools connections internally)."""
    global _client
    if _client is None:
        _client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            decode_responses=True,
        )
    return _client
