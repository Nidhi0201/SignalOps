#!/bin/bash
# Start all SignalOps services

set -e

echo "🚀 Starting SignalOps..."

# Start Docker containers
echo "📦 Starting Docker containers (OpenSearch, Redis, Postgres)..."
cd "$(dirname "$0")"
docker compose up -d

echo "⏳ Waiting for OpenSearch to be ready..."
sleep 15

# Check if OpenSearch is ready
until curl -s -u admin:admin http://localhost:9200 > /dev/null 2>&1; do
  echo "Waiting for OpenSearch..."
  sleep 2
done

echo "✅ Infrastructure is ready!"
echo ""
echo "📝 Backend and Frontend should already be running."
echo "   Backend: http://localhost:8000"
echo "   Frontend: http://localhost:3000"
echo ""
echo "🧪 Test with: ./test-sample-logs.sh"
