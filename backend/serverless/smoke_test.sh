#!/usr/bin/env bash
# Verify a DEPLOYED SignalOps ingestion Lambda end to end: POST a log through the
# API Gateway URL, then confirm the entry landed in the Redis Stream.
#
# Usage:
#   INGEST_API_URL=https://xxxx.execute-api.us-east-1.amazonaws.com/logs/ingest \
#   REDIS_HOST=your-host REDIS_PORT=6379 REDIS_PASSWORD=your-pw [REDIS_TLS=1] \
#   ./smoke_test.sh
set -euo pipefail

: "${INGEST_API_URL:?set INGEST_API_URL (from the sam deploy output)}"
: "${REDIS_HOST:?set REDIS_HOST}"
: "${REDIS_PORT:?set REDIS_PORT}"

redis() {
  redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" \
    ${REDIS_PASSWORD:+-a "$REDIS_PASSWORD"} ${REDIS_TLS:+--tls} "$@" 2>/dev/null
}

before=$(redis XLEN logs:stream || echo 0)
echo "POST -> $INGEST_API_URL"
resp=$(curl -s -X POST "$INGEST_API_URL" -H 'Content-Type: application/json' \
  -d '{"service":"smoke","level":"INFO","message":"smoke test"}')
echo "response: $resp"
after=$(redis XLEN logs:stream)

echo "logs:stream length: $before -> $after"
if [ "$after" -gt "$before" ]; then
  echo "PASS: the serverless producer enqueued the log."
else
  echo "FAIL: nothing was enqueued — check REDIS_* values and RedisSsl, and the"
  echo "      function's CloudWatch logs for the exact error."
  exit 1
fi
