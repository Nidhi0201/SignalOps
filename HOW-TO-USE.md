# How to Use SignalOps - Complete User Guide

## 🚀 Quick Start

### Step 1: Make Sure Everything is Running

```bash
# Check services
docker compose ps

# If not running, start them:
docker compose up -d

# Start backend (if not running)
cd backend
source venv/bin/activate
uvicorn app.main:app --reload

# Start frontend (in new terminal)
cd frontend
npm run dev
```

### Step 2: Open the Dashboard

Open your browser: **http://localhost:3000**

---

## 📝 Feature 1: Log Search (Phase 1)

### Test via UI:

1. **Go to:** `http://localhost:3000`
2. **You'll see:** Log search form
3. **Try searching:**
   - Leave all fields empty → Click "Search Logs" → See all logs
   - Enter `payment-service` in Service field → Search
   - Select `ERROR` from Level dropdown → Search
   - Type `timeout` in Query field → Search

### Test via API (Terminal):

**First, let's add some sample logs:**

```bash
# Add a payment error
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "service": "payment-service",
    "level": "ERROR",
    "message": "Payment failed due to timeout",
    "trace_id": "trace-001",
    "metadata": {"order_id": "ord_123", "amount": 99.99}
  }'

# Add an auth warning
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "service": "auth-service",
    "level": "WARN",
    "message": "Multiple failed login attempts",
    "trace_id": "trace-002"
  }'

# Add an order info log
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "service": "order-service",
    "level": "INFO",
    "message": "Order created successfully",
    "trace_id": "trace-003"
  }'
```

**Now search for them:**

```bash
# Search all logs
curl "http://localhost:8000/logs/search"

# Search by service
curl "http://localhost:8000/logs/search?service=payment-service"

# Search by level
curl "http://localhost:8000/logs/search?level=ERROR"

# Search by keyword
curl "http://localhost:8000/logs/search?q=timeout"
```

**What to expect:**
- You'll see JSON with log entries
- Each log has: id, timestamp, service, level, message, trace_id, metadata
- Logs appear in the UI dashboard

---

## 🚨 Feature 2: Alerts & Incidents (Phase 2)

### Test via UI:

1. **Go to:** `http://localhost:3000/alerts`
2. **Create an Alert Rule:**
   - Click "+ New Rule"
   - Fill in:
     - Name: `High Error Rate`
     - Service: `payment-service` (or leave empty for all services)
     - Level: `ERROR`
     - Window: `5` minutes
     - Threshold: `3` (alert if more than 3 errors in 5 minutes)
   - Click "Create Rule"

3. **Trigger the Alert:**
   - Go back to main page or use API to generate logs
   - Generate 4+ ERROR logs quickly:

```bash
# Generate multiple errors to trigger alert
for i in {1..5}; do
  curl -X POST http://localhost:8000/logs/ingest \
    -H "Content-Type: application/json" \
    -d "{\"service\":\"payment-service\",\"level\":\"ERROR\",\"message\":\"Payment error $i\"}"
  sleep 1
done
```

4. **Wait 1 minute** - The scheduler checks every minute
5. **Check Incidents:**
   - Go back to `/alerts` page
   - You should see a new incident appear!
   - It will show: log count, start time, status

6. **Resolve Incident:**
   - Click "Resolve" button on the incident
   - Status changes to "resolved"

### Test via API:

**Create alert rule:**
```bash
curl -X POST http://localhost:8000/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Payment Errors",
    "service": "payment-service",
    "level": "ERROR",
    "window_minutes": 5,
    "threshold_count": 3,
    "enabled": true
  }'
```

**List alert rules:**
```bash
curl http://localhost:8000/alerts
```

**Generate logs to trigger:**
```bash
for i in {1..5}; do
  curl -X POST http://localhost:8000/logs/ingest \
    -H "Content-Type: application/json" \
    -d "{\"service\":\"payment-service\",\"level\":\"ERROR\",\"message\":\"Error $i\"}"
done
```

**Wait 1 minute, then check incidents:**
```bash
curl http://localhost:8000/alerts/incidents
```

**Resolve an incident:**
```bash
# Get incident ID from above, then:
curl -X POST http://localhost:8000/alerts/incidents/1/resolve
```

---

## 🤖 Feature 3: AI Incident Summarizer (Phase 3)

### Test via UI:

1. **Create an incident** (follow Feature 2 steps)
2. **Wait 1 minute** - Incident is created automatically
3. **Check the incident** on `/alerts` page
4. **You should see:**
   - **Summary:** AI-generated description of what happened
   - **Root Cause:** Hypothesis about the issue
   - **Next Steps:** Recommended actions

**If summary doesn't appear:**
- Click "Generate AI Summary" button
- Wait a few seconds
- Summary will appear

### Test via API:

**Manually trigger AI summary:**
```bash
# First, get an incident ID
INCIDENT_ID=$(curl -s http://localhost:8000/alerts/incidents | jq -r '.[0].id')

# Generate AI summary
curl -X POST http://localhost:8000/alerts/incidents/$INCIDENT_ID/summarize
```

**Check the summary:**
```bash
curl http://localhost:8000/alerts/incidents/$INCIDENT_ID | jq '.ai_summary'
```

**What to expect:**
- Detailed summary (not just log counts)
- Root cause hypothesis
- Actionable next steps
- Takes 2-5 seconds to generate

---

## 💬 Feature 4: Ask My Logs (Phase 4)

### Test via UI:

1. **Go to:** `http://localhost:3000/ask`
2. **You'll see:** Chat interface with filter sidebar
3. **Set filters (optional):**
   - Service: `payment-service`
   - Level: `ERROR`
   - Time range: Last hour
4. **Ask a question:**
   - Type: `"What payment errors occurred?"`
   - Click "Ask"
   - Wait 3-6 seconds
5. **See the answer:**
   - AI-generated response
   - Citations below showing relevant logs
   - Each citation has: log ID, timestamp, service, level, message

### Test via API:

**First, make sure you have some logs:**
```bash
# Add some logs
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"payment-service","level":"ERROR","message":"Payment timeout after 30s"}'

curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"payment-service","level":"ERROR","message":"Credit card validation failed"}'
```

**Ask a question:**
```bash
curl -X POST http://localhost:8000/logs/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What payment errors occurred?",
    "service": "payment-service",
    "level": "ERROR"
  }'
```

**What to expect:**
- Natural language answer
- Citations array with log details
- Answer references specific logs

---

## 🎯 Complete Test Scenario

Here's a full end-to-end test:

### Step 1: Add Sample Logs
```bash
# Payment errors
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"payment-service","level":"ERROR","message":"Payment gateway timeout"}'

curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"payment-service","level":"ERROR","message":"Credit card declined"}'

# Auth warnings
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"auth-service","level":"WARN","message":"Failed login attempt"}'

# Order info
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"order-service","level":"INFO","message":"Order #12345 created"}'
```

### Step 2: Search Logs (UI)
1. Go to `http://localhost:3000`
2. Search for `payment-service` → See 2 logs
3. Filter by `ERROR` → See only errors
4. Search for `timeout` → See timeout error

### Step 3: Create Alert Rule (UI)
1. Go to `http://localhost:3000/alerts`
2. Create rule: "Payment Errors" → ERROR level → >2 in 5 min
3. Generate 3 more payment errors:

```bash
for i in {1..3}; do
  curl -X POST http://localhost:8000/logs/ingest \
    -H "Content-Type: application/json" \
    -d "{\"service\":\"payment-service\",\"level\":\"ERROR\",\"message\":\"Error $i\"}"
done
```

### Step 4: Wait for Incident (1 minute)
- Scheduler checks every minute
- Incident is created automatically
- AI summary is generated automatically

### Step 5: View Incident (UI)
1. Go to `/alerts` page
2. See the incident with:
   - Log count
   - AI summary
   - Root cause
   - Next steps

### Step 6: Ask Questions (UI)
1. Go to `http://localhost:3000/ask`
2. Ask: `"Why did payment fail?"`
3. See AI answer with citations
4. Ask: `"What errors happened in the last hour?"`

---

## 📋 Sample Data Script

Save this as `add-sample-data.sh`:

```bash
#!/bin/bash
echo "📤 Adding sample logs..."

# Payment service logs
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"payment-service","level":"ERROR","message":"Payment gateway timeout after 30s","trace_id":"pay-001"}'

curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"payment-service","level":"ERROR","message":"Credit card validation failed","trace_id":"pay-002"}'

curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"payment-service","level":"INFO","message":"Payment processed successfully","trace_id":"pay-003"}'

# Auth service logs
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"auth-service","level":"WARN","message":"Multiple failed login attempts detected","trace_id":"auth-001"}'

curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"auth-service","level":"INFO","message":"User login successful","trace_id":"auth-002"}'

# Order service logs
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"order-service","level":"INFO","message":"Order created successfully","trace_id":"order-001"}'

curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"order-service","level":"ERROR","message":"Inventory check failed","trace_id":"order-002"}'

# Database service logs
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"db-service","level":"WARN","message":"Slow query detected","trace_id":"db-001"}'

echo ""
echo "✅ Sample logs added!"
echo ""
echo "Now try:"
echo "1. Search logs at http://localhost:3000"
echo "2. Create alerts at http://localhost:3000/alerts"
echo "3. Ask questions at http://localhost:3000/ask"
```

---

## 🎬 Quick Demo Flow

**5-Minute Demo:**

1. **Add logs** (30 seconds)
   ```bash
   ./add-sample-data.sh
   ```

2. **Search logs** (30 seconds)
   - Go to `http://localhost:3000`
   - Search by service, level, keywords

3. **Create alert** (1 minute)
   - Go to `/alerts`
   - Create rule: ERROR > 2 in 5 min
   - Generate 3 errors to trigger

4. **View incident** (1 minute)
   - Wait 1 minute
   - See incident with AI summary

5. **Ask questions** (2 minutes)
   - Go to `/ask`
   - Ask: "What errors occurred?"
   - See AI answer with citations

---

## 💡 Tips

- **Logs appear immediately** after ingestion
- **Alerts check every 1 minute** - be patient!
- **AI summaries take 2-5 seconds** to generate
- **Use the UI** for visual exploration
- **Use API** for automation/testing

---

## 🐛 Troubleshooting

**No logs showing?**
- Check if logs were ingested: `curl http://localhost:8000/logs/search`
- Check OpenSearch: `curl http://localhost:9200/logs/_count`

**Alert not triggering?**
- Check rule is enabled
- Make sure you generated enough logs
- Wait at least 1 minute for scheduler

**AI not working?**
- Check Vertex AI is configured
- System works in fallback mode without AI
- Check backend logs for errors

**Frontend not loading?**
- Make sure frontend is running: `npm run dev` in frontend/
- Check browser console for errors
- Verify backend is on port 8000

---

## 📚 Next Steps

Once you're comfortable:
1. Create your own alert rules
2. Ingest logs from your own services
3. Use Ask My Logs for real troubleshooting
4. Customize for your use case

Enjoy exploring SignalOps! 🚀
