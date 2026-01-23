# 🚀 SignalOps Quick Start Guide

## Step-by-Step: Test All Features

### Prerequisites Check ✅

Make sure these are running:
- ✅ Docker containers (OpenSearch, Postgres, Redis)
- ✅ Backend on `http://localhost:8000`
- ✅ Frontend on `http://localhost:3000`

---

## 🎯 5-Minute Test Flow

### Step 1: Add Sample Data (30 seconds)

**Option A: Use the script**
```bash
cd /Users/nidhiprajapati/Desktop/SignalOps
./add-sample-data.sh
```

**Option B: Manual (copy-paste)**
```bash
# Payment errors
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"payment-service","level":"ERROR","message":"Payment timeout"}'

curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"payment-service","level":"ERROR","message":"Credit card declined"}'

# Auth warning
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"auth-service","level":"WARN","message":"Failed login attempts"}'

# Order info
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{"service":"order-service","level":"INFO","message":"Order created"}'
```

**✅ Expected:** No errors, logs are ingested

---

### Step 2: Search Logs (1 minute)

1. **Open browser:** `http://localhost:3000`

2. **You'll see:** Log search form with filters

3. **Try these searches:**
   - **Empty search:** Click "Search Logs" → See all logs
   - **By service:** Type `payment-service` → Search → See payment logs
   - **By level:** Select `ERROR` → Search → See only errors
   - **By keyword:** Type `timeout` → Search → See timeout logs
   - **Combined:** Service=`payment-service` + Level=`ERROR` → Search

**✅ Expected:** Logs appear in the results section below

---

### Step 3: Create Alert Rule (1 minute)

1. **Go to:** `http://localhost:3000/alerts`
   - Or click "Alerts & Incidents →" link from main page

2. **Create a rule:**
   - Click "+ New Rule" button
   - Fill in the form:
     ```
     Name: Payment Errors
     Service: payment-service
     Level: ERROR
     Window: 5
     Threshold Count: 2
     ```
   - Click "Create Rule"

3. **You'll see:** New rule appears in the list

**✅ Expected:** Rule shows as "Enabled" with green badge

---

### Step 4: Trigger Alert (1 minute)

**Generate logs to trigger the alert:**

```bash
# Generate 3 payment errors (more than threshold of 2)
for i in {1..3}; do
  curl -X POST http://localhost:8000/logs/ingest \
    -H "Content-Type: application/json" \
    -d "{\"service\":\"payment-service\",\"level\":\"ERROR\",\"message\":\"Payment error $i\"}"
done
```

**Wait 1 minute** - The scheduler checks every minute

**Check for incident:**
- Go back to `/alerts` page
- Scroll to "Incidents" section
- You should see a new incident!

**✅ Expected:** 
- Incident appears with status "open"
- Shows log count (should be 3+)
- Shows start time
- **If AI is working:** Shows AI summary, root cause, next steps

---

### Step 5: View AI Summary (30 seconds)

**If AI summary didn't appear automatically:**

1. **Click "Generate AI Summary"** button on the incident
2. **Wait 3-5 seconds**
3. **See:**
   - **Summary:** Description of what happened
   - **Root Cause:** Hypothesis about the issue
   - **Next Steps:** Recommended actions

**✅ Expected:** Detailed AI-generated analysis (not just log counts)

---

### Step 6: Ask My Logs (2 minutes)

1. **Go to:** `http://localhost:3000/ask`
   - Or click "Ask My Logs →" link from main page

2. **You'll see:** Chat interface with filter sidebar

3. **Set filters (optional):**
   - Service: `payment-service`
   - Level: `ERROR`

4. **Ask questions:**
   - Type: `"What payment errors occurred?"`
   - Click "Ask"
   - Wait 3-6 seconds

5. **See the answer:**
   - AI-generated response appears
   - Citations section below shows relevant logs
   - Each citation has: timestamp, service, level, message, log ID

6. **Try more questions:**
   - `"Why did payment fail?"`
   - `"What errors happened in payment-service?"`
   - `"Show me timeout issues"`

**✅ Expected:** Natural language answers with log citations

---

## 📋 What Each Feature Does

### 1. Log Search
- **What it does:** Search and filter logs
- **Use case:** Find specific logs, debug issues
- **Example:** "Show me all ERROR logs from payment-service"

### 2. Alert Rules
- **What it does:** Monitor logs and create incidents
- **Use case:** Get notified when errors spike
- **Example:** "Alert if ERROR count > 10 in 5 minutes"

### 3. Incidents
- **What it does:** Tracks when alerts trigger
- **Use case:** Track and manage issues
- **Example:** See all open incidents, resolve them

### 4. AI Summaries
- **What it does:** Analyzes incidents automatically
- **Use case:** Understand what happened quickly
- **Example:** Get summary, root cause, next steps

### 5. Ask My Logs
- **What it does:** Natural language log queries
- **Use case:** Ask questions about your logs
- **Example:** "Why did checkout fail?"

---

## 🎬 Complete Demo Script

Run this to test everything:

```bash
# 1. Add sample data
./add-sample-data.sh

# 2. Create alert rule
curl -X POST http://localhost:8000/alerts \
  -H "Content-Type: application/json" \
  -d '{"name":"Payment Errors","service":"payment-service","level":"ERROR","window_minutes":5,"threshold_count":2}'

# 3. Trigger alert
for i in {1..3}; do
  curl -X POST http://localhost:8000/logs/ingest \
    -H "Content-Type: application/json" \
    -d "{\"service\":\"payment-service\",\"level\":\"ERROR\",\"message\":\"Error $i\"}"
done

# 4. Wait 1 minute, then check
echo "Wait 1 minute, then run:"
echo "curl http://localhost:8000/alerts/incidents"

# 5. Ask a question
curl -X POST http://localhost:8000/logs/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What payment errors occurred?"}'
```

---

## 🖥️ UI Navigation

**Main Pages:**
- `/` - Log Search (main page)
- `/alerts` - Alerts & Incidents
- `/ask` - Ask My Logs chat

**Navigation:**
- Links at top of each page
- "Alerts & Incidents →" from main page
- "Ask My Logs →" from main page
- "← Back to Logs" from alerts/ask pages

---

## 💡 Pro Tips

1. **Start with sample data** - Use `add-sample-data.sh`
2. **Use UI for exploration** - Easier to see results
3. **Use API for automation** - Script your tests
4. **Wait for scheduler** - Alerts check every 1 minute
5. **AI takes time** - Summaries take 2-5 seconds

---

## 🎉 You're Ready!

Now you know how to:
- ✅ Search logs
- ✅ Create alerts
- ✅ View incidents
- ✅ Use AI summaries
- ✅ Ask questions about logs

Start exploring! 🚀
