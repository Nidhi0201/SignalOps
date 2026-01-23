#!/bin/bash
# SignalOps Phase 1 Startup Script

set -e

echo "🚀 Starting SignalOps Phase 1..."

# Start infrastructure
echo "📦 Starting Docker containers (OpenSearch, Redis, Postgres)..."
cd "$(dirname "$0")"
docker compose up -d

echo "⏳ Waiting for OpenSearch to be ready..."
sleep 10

# Check if OpenSearch is ready
until curl -s -u admin:admin http://localhost:9200 > /dev/null 2>&1; do
  echo "Waiting for OpenSearch..."
  sleep 2
done

echo "✅ Infrastructure is ready!"
echo ""
echo "📝 Next steps:"
echo "1. Backend: cd backend && poetry install && poetry run uvicorn app.main:app --reload"
echo "2. Frontend: cd frontend && npm run dev"
echo "3. Test: curl -X POST http://localhost:8000/logs/ingest -H 'Content-Type: application/json' -d '{\"service\":\"payment-service\",\"level\":\"ERROR\",\"message\":\"Payment failed\"}'"
echo ""
echo "🌐 Frontend will be at http://localhost:3000"
echo "🔧 Backend API will be at http://localhost:8000"
echo "📊 OpenSearch will be at http://localhost:9200"
