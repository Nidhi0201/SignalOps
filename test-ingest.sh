#!/bin/bash
# Test log ingestion script

echo "📤 Testing log ingestion..."

curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "service": "payment-service",
    "level": "ERROR",
    "message": "Payment failed due to timeout",
    "trace_id": "abc-123",
    "metadata": { "order_id": "ord_1" }
  }'

echo ""
echo ""
echo "✅ Log ingested! Check http://localhost:3000 to see it in the dashboard"
