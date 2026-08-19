"""
AWS Lambda: serverless log-ingestion producer for SignalOps.

API Gateway (POST /logs/ingest) -> this handler -> XADD to the Redis Stream,
returning 202 immediately. It is a serverless front door to the *same* async
pipeline the FastAPI service feeds: the consumer (app/consumer.py) drains the
stream into OpenSearch either way. Redis is reached over the network via
REDIS_HOST / REDIS_PORT (e.g. an ElastiCache endpoint inside the VPC).

The module is self-contained (no FastAPI/OpenSearch imports) so the deployment
package stays small — just redis + pydantic.
"""
import base64
import json
import os
from datetime import datetime
from typing import Any, Literal, Optional

import redis
from pydantic import BaseModel, Field, ValidationError

LOG_STREAM = os.getenv("LOG_STREAM", "logs:stream")
LOG_STREAM_MAXLEN = int(os.getenv("LOG_STREAM_MAXLEN", "1000000"))

_client: Optional[redis.Redis] = None


def _get_client() -> redis.Redis:
    """Cached Redis client (reused across warm Lambda invocations).

    Supports password auth and TLS so it works with managed Redis (Redis Cloud,
    Upstash) as well as an in-VPC ElastiCache with no auth.
    """
    global _client
    if _client is None:
        _client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD") or None,
            ssl=os.getenv("REDIS_SSL", "false").lower() == "true",
            decode_responses=True,
            socket_timeout=5,
        )
    return _client


class LogIn(BaseModel):
    """Mirrors the FastAPI ingest schema so both producers accept the same payload."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    service: str
    level: Literal["DEBUG", "INFO", "WARN", "ERROR", "FATAL"]
    message: str
    trace_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def handler(event: dict, context: Any = None) -> dict:
    """API Gateway proxy handler. Accepts one log object or a list of them."""
    raw_body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode("utf-8")

    try:
        payload = json.loads(raw_body)
    except (ValueError, TypeError):
        return _response(400, {"error": "request body must be valid JSON"})

    items = payload if isinstance(payload, list) else [payload]
    try:
        logs = [LogIn.model_validate(item) for item in items]
    except ValidationError as exc:
        return _response(422, {"error": "validation failed", "detail": exc.errors()})

    client = _get_client()
    stream_ids = []
    for log in logs:
        body = log.model_dump(mode="json")
        stream_ids.append(
            client.xadd(
                LOG_STREAM, {"data": json.dumps(body)},
                maxlen=LOG_STREAM_MAXLEN, approximate=True,
            )
        )

    return _response(202, {"accepted": len(stream_ids), "stream_ids": stream_ids})
