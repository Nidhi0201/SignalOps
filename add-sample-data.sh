#!/bin/bash
# Add sample logs to SignalOps for testing

echo "📤 Adding sample logs to SignalOps..."
echo ""

# Payment service logs
echo "Adding payment-service logs..."
curl -s -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"payment-service","level":"ERROR","message":"Payment gateway timeout after 30s","trace_id":"pay-001","metadata":{"gateway":"stripe","retry_count":3}}' > /dev/null

curl -s -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"payment-service","level":"ERROR","message":"Credit card validation failed","trace_id":"pay-002","metadata":{"card_type":"visa","amount":99.99}}' > /dev/null

curl -s -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"payment-service","level":"INFO","message":"Payment processed successfully","trace_id":"pay-003","metadata":{"order_id":"ord_123","amount":49.99}}' > /dev/null

# Auth service logs
echo "Adding auth-service logs..."
curl -s -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"auth-service","level":"WARN","message":"Multiple failed login attempts detected","trace_id":"auth-001","metadata":{"user_id":"user_789","ip":"192.168.1.100}}' > /dev/null

curl -s -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"auth-service","level":"INFO","message":"User login successful","trace_id":"auth-002","metadata":{"user_id":"user_123","method":"oauth}}' > /dev/null

# Order service logs
echo "Adding order-service logs..."
curl -s -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"order-service","level":"INFO","message":"Order created successfully","trace_id":"order-001","metadata":{"order_id":"ord_456","status":"pending}}' > /dev/null

curl -s -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"order-service","level":"ERROR","message":"Inventory check failed for product SKU-456","trace_id":"order-002","metadata":{"order_id":"ord_457","sku":"SKU-456}}' > /dev/null

# Database service logs
echo "Adding db-service logs..."
curl -s -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"db-service","level":"WARN","message":"Slow query detected: SELECT * FROM orders","trace_id":"db-001","metadata":{"query_time":"2.5s","table":"orders}}' > /dev/null

curl -s -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"db-service","level":"INFO","message":"Database connection pool healthy","trace_id":"db-002","metadata":{"connections":10,"max_connections":50}}' > /dev/null

# API gateway logs
echo "Adding api-gateway logs..."
curl -s -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"api-gateway","level":"INFO","message":"Request processed: GET /api/v1/products","trace_id":"api-001","metadata":{"method":"GET","path":"/api/v1/products","status":200,"duration_ms":45}}' > /dev/null

curl -s -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"api-gateway","level":"ERROR","message":"Rate limit exceeded for IP 192.168.1.50","trace_id":"api-002","metadata":{"ip":"192.168.1.50","limit":100,"current":150}}' > /dev/null

echo ""
echo "✅ Sample logs added!"
echo ""
echo "📊 Now try these:"
echo ""
echo "1. Search logs:"
echo "   Open http://localhost:3000"
echo "   - Search for 'payment-service'"
echo "   - Filter by 'ERROR' level"
echo "   - Search for 'timeout'"
echo ""
echo "2. Create alert:"
echo "   Go to http://localhost:3000/alerts"
echo "   - Click '+ New Rule'"
echo "   - Name: 'Payment Errors'"
echo "   - Service: 'payment-service'"
echo "   - Level: 'ERROR'"
echo "   - Window: 5 minutes"
echo "   - Threshold: 2"
echo ""
echo "3. Trigger alert:"
echo "   Run: for i in {1..3}; do curl -X POST http://localhost:8000/logs/ingest -H 'Content-Type: application/json' -d '{\"service\":\"payment-service\",\"level\":\"ERROR\",\"message\":\"Error '$i'\"}'; done"
echo "   Wait 1 minute, then check /alerts page for incident"
echo ""
echo "4. Ask questions:"
echo "   Go to http://localhost:3000/ask"
echo "   - Ask: 'What payment errors occurred?'"
echo "   - Ask: 'Why did payment fail?'"
echo ""
