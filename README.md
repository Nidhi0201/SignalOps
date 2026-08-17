## SignalOps – Mini Datadog/ELK

[![CI](https://github.com/Nidhi0201/SignalOps/actions/workflows/ci.yml/badge.svg)](https://github.com/Nidhi0201/SignalOps/actions/workflows/ci.yml)

A complete observability platform for log management, alerting, and AI-powered analysis:

- **Ingestion API (FastAPI)**: services send JSON logs to `/logs/ingest`.
- **Indexing (OpenSearch)**: logs are indexed and queryable.
- **Database (Postgres)**: stores alert rules, incidents, and metadata.
- **Alerting System**: automatic incident detection with configurable rules.
- **AI Summarization**: AI-powered incident analysis using Vertex AI/Gemini.
- **RAG Chat Interface**: "Ask My Logs" - natural language queries with citations.
- **Dashboard (Next.js)**: search, explore, and manage logs and incidents.

### Testing

The backend has a pytest suite that runs against **real** OpenSearch and Postgres
(spun up as ephemeral [testcontainers](https://testcontainers.com/) — no mocks),
plus `ruff` lint. Both run in CI on every push (badge above).

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest            # requires a running Docker daemon
ruff check app tests
```

**Coverage (measured, `pytest --cov-branch`):**

| Scope | Line | Branch |
|-------|------|--------|
| Whole `app/` package | 55.6% | 36.2% |
| Core API under test (ingest, search, alerts, incidents) | 76.9% | 56.8% |

60 tests cover: single + batch ingest, every search filter and combination,
pagination edges, malformed-payload rejection, the OpenSearch-unavailable (503)
path, and alert-rule / incident CRUD. The async Redis-Streams consumer tests are
stubbed and skipped until that pipeline is built (see `tests/test_redis_consumer.py`).

### Alerting & incident detection

Alert rules are evaluated on a fixed schedule (configurable via
`EVAL_INTERVAL_SECONDS`, default 60s): each tick queries OpenSearch over a
sliding window and opens/updates/resolves incidents in Postgres. Three rule
types are supported:

- **count** — logs at a level exceed a threshold in the window
- **error_rate** — `(ERROR+FATAL)/total` exceeds a percentage, guarded by a
  minimum sample size (avoids 1/1 = 100% flapping)
- **heartbeat_absence** — a service goes silent (zero logs) in the window

**Flap damping** (the decision core in `app/alert_engine.py` is a pure,
unit-tested function): open only after `for_consecutive` sustained breaches,
auto-resolve only after `resolve_after_clear` consecutive clears, a
`cooldown_minutes` re-arm delay after resolving, and dedup of repeat breaches
into the open incident.

**Measured detection latency** (`scripts/measure_alerting.py` — injects a
labeled fault timeline, replays the evaluator over a virtual clock; 30 trials,
15s poll interval, 2-minute window):

| Rule type | Median | p95 |
|-----------|--------|-----|
| count (error burst) | 26 s | 34 s |
| error_rate | 88 s | 93 s |
| heartbeat_absence | 126 s | 132 s |

**0 false positives across 1,200 evaluation ticks.** Rate- and absence-based
rules are inherently slower than count spikes because the signal must fill the
sliding window — a tradeoff, not a bug. Reproduce:

```bash
docker compose up -d          # OpenSearch + Postgres
cd backend && python -m scripts.measure_alerting --trials 30 --interval 15
```

### Getting Started

#### Prerequisites

- Docker + Docker Compose
- Python 3.11+ with Poetry
- Node.js 20+ and npm/pnpm/yarn

#### Quick Start

1. **Start infrastructure services**

   ```bash
   docker compose up -d
   ```

   This starts:
   - OpenSearch on `http://localhost:9200` (admin/admin)
   - Redis on `localhost:6379`
   - Postgres on `localhost:5432` (signalops/signalops)

2. **Set up and run the backend API**

   ```bash
   cd backend
   poetry install  # or: pip install -r requirements.txt
   poetry run uvicorn app.main:app --reload
   ```

   **Important**: You must be in the `backend` directory when running uvicorn. Alternatively, use the helper script:
   ```bash
   cd backend
   ./run.sh
   ```

   Backend will be available at `http://localhost:8000`

3. **Set up and run the frontend dashboard**

   ```bash
   cd frontend
   npm install  # or pnpm install / yarn install
   npm run dev
   ```

   Frontend will be available at `http://localhost:3000`

4. **Test log ingestion**

   ```bash
   curl -X POST http://localhost:8000/logs/ingest \
     -H "Content-Type: application/json" \
     -d '{
       "service": "payment-service",
       "level": "ERROR",
       "message": "Payment failed due to timeout",
       "trace_id": "abc-123",
       "metadata": {"order_id": "ord_1"}
     }'
   ```

   Or use the test script:
   ```bash
   ./test-ingest.sh
   ```

5. **Search logs via API**

   ```bash
   curl "http://localhost:8000/logs/search?service=payment-service&level=ERROR"
   ```

   Or use the dashboard at `http://localhost:3000` to search visually!

#### Helper Scripts

- `./start.sh` - Starts Docker containers and provides next steps
- `./test-ingest.sh` - Sends a test log to the ingestion API

### Features

✅ **Phase 1: Log Ingestion & Search**
- Ingest logs from multiple services
- Fast search with filters (service, level, time range, keywords)
- Real-time log viewing dashboard

✅ **Phase 2: Alerting & Incident Management**
- Create alert rules with custom thresholds
- Automatic incident detection via background scheduler
- Incident tracking and resolution

✅ **Phase 3: AI-Powered Incident Summarization**
- Automatic incident analysis using Vertex AI/Gemini
- Root cause identification
- Recommended next steps

✅ **Phase 4: "Ask My Logs" RAG Chat**
- Natural language queries about your logs
- AI-powered answers with citations
- Filter by service, level, and time range

### API Endpoints

**Log Management:**
- `POST /logs/ingest` - Ingest single log or batch (accepts `LogIn` or `list[LogIn]`)
- `GET /logs/search` - Search logs with filters:
  - `service` - Filter by service name
  - `level` - Filter by log level (DEBUG, INFO, WARN, ERROR, FATAL)
  - `q` - Free-text search in message field
  - `from` - Start timestamp (ISO format)
  - `to` - End timestamp (ISO format)
  - `page` - Page number (default: 1)
  - `page_size` - Results per page (default: 50)
- `GET /logs/services` - Get list of available services
- `POST /logs/ask` - Ask questions about logs (RAG chat)

**Alerting:**
- `POST /alerts` - Create alert rule
- `GET /alerts` - List all alert rules
- `POST /alerts/{id}/toggle` - Enable/disable alert rule
- `GET /alerts/incidents` - List all incidents
- `GET /alerts/incidents/{id}` - Get incident details
- `POST /alerts/incidents/{id}/ack` - Acknowledge incident
- `POST /alerts/incidents/{id}/resolve` - Resolve incident
- `POST /alerts/incidents/{id}/summarize` - Generate AI summary

**System:**
- `GET /health` - Health check endpoint

### Project Structure

```
SignalOps/
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── main.py      # Main API application
│   │   ├── alerts.py    # Alert & incident endpoints
│   │   ├── scheduler.py # Background alert checker
│   │   ├── ai_service.py # Vertex AI integration
│   │   ├── models.py    # SQLAlchemy models
│   │   └── database.py  # Database connection
│   └── requirements.txt # Python dependencies
├── frontend/             # Next.js 15 dashboard
│   ├── app/
│   │   ├── page.tsx     # Log search dashboard
│   │   ├── alerts/      # Alert management page
│   │   └── ask/         # "Ask My Logs" chat
│   └── package.json     # npm dependencies
├── docker-compose.yml    # Infrastructure services
└── README.md            # This file
```

### Documentation

- `QUICK-START-GUIDE.md` - Quick start guide
- `HOW-TO-USE.md` - Comprehensive user guide
- `GOOGLE-CLOUD-AUTH.md` - Vertex AI authentication setup
- `INSTALL-DOCKER.md` - Docker installation guide
- `GITHUB-SETUP.md` - GitHub repository setup guide

### Technology Stack

- **Backend**: FastAPI, SQLAlchemy, APScheduler
- **Frontend**: Next.js 15, React, TypeScript, Tailwind CSS
- **Database**: PostgreSQL, OpenSearch
- **AI**: Google Vertex AI (Gemini 1.5 Flash)
- **Infrastructure**: Docker Compose, Redis

