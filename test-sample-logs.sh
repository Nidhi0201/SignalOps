#!/bin/bash
# Test SignalOps with sample logs

echo "🧪 Testing SignalOps with sample logs..."
echo ""

# Sample logs for different services and levels
echo "📤 Ingesting sample logs..."

# Payment service errors
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "service": "payment-service",
    "level": "ERROR",
    "message": "Payment failed due to timeout",
    "trace_id": "trace-001",
    "metadata": {"order_id": "ord_12345", "amount": 99.99}
  }'

echo ""
sleep 1

curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "service": "payment-service",
    "level": "ERROR",
    "message": "Credit card validation failed",
    "trace_id": "trace-002",
    "metadata": {"order_id": "ord_12346", "card_type": "visa"}
  }'

echo ""
sleep 1

# Auth service logs
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "service": "auth-service",
    "level": "WARN",
    "message": "Multiple failed login attempts detected",
    "trace_id": "trace-003",
    "metadata": {"user_id": "user_789", "ip": "192.168.1.100"}
  }'

echo ""
sleep 1

curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "service": "auth-service",
    "level": "INFO",
    "message": "User login successful",
    "trace_id": "trace-004",
    "metadata": {"user_id": "user_123", "method": "oauth"}
  }'

echo ""
sleep 1

# Order service logs
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "service": "order-service",
    "level": "INFO",
    "message": "Order created successfully",
    "trace_id": "trace-005",
    "metadata": {"order_id": "ord_12347", "status": "pending"}
  }'

echo ""
sleep 1

curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "service": "order-service",
    "level": "ERROR",
    "message": "Inventory check failed for product SKU-456",
    "trace_id": "trace-006",
    "metadata": {"order_id": "ord_12348", "sku": "SKU-456"}
  }'

echo ""
sleep 1

# Database service logs
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "service": "db-service",
    "level": "WARN",
    "message": "Slow query detected: SELECT * FROM orders",
    "trace_id": "trace-007",
    "metadata": {"query_time": "2.5s", "table": "orders"}
  }'

echo ""
sleep 1

curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "service": "db-service",
    "level": "INFO",
    "message": "Database connection pool healthy",
    "trace_id": "trace-008",
    "metadata": {"connections": 10, "max_connections": 50}
  }'

echo ""
sleep 1

# API gateway logs
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "service": "api-gateway",
    "level": "INFO",
    "message": "Request processed: GET /api/v1/products",
    "trace_id": "trace-009",
    "metadata": {"method": "GET", "path": "/api/v1/products", "status": 200, "duration_ms": 45}
  }'

echo ""
sleep 1

curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "service": "api-gateway",
    "level": "ERROR",
    "message": "Rate limit exceeded for IP 192.168.1.50",
    "trace_id": "trace-010",
    "metadata": {"ip": "192.168.1.50", "limit": 100, "current": 150}
  }'

echo ""
echo ""
echo "✅ Sample logs ingested!"
echo ""
echo "🔍 Now try searching:"
echo "   - All ERROR logs: curl 'http://localhost:8000/logs/search?level=ERROR'"
echo "   - Payment service: curl 'http://localhost:8000/logs/search?service=payment-service'"
echo "   - Search for 'timeout': curl 'http://localhost:8000/logs/search?q=timeout'"
echo ""
echo "🌐 Or open the dashboard: http://localhost:3000"
echo "   Try filtering by:"
echo "   - Service: payment-service"
echo "   - Level: ERROR"
echo "   - Query: timeout"
