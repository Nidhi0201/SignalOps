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
| Whole `app/` package | 63.0% | 47.7% |
| Alert-engine decision core | 97% | 100% |

100 tests cover: ingest (async + sync), every search filter and combination,
pagination edges (including `search_after` cursors), malformed-payload rejection,
OpenSearch-unavailable (503), alert-rule / incident CRUD, the alert evaluator
(three rule types + flap damping), the Redis consumer (batching, redelivery /
claim on worker death, dead-lettering, and the end-to-end ingest → consumer →
search pipeline), and the serverless ingestion Lambda handler.

### Async ingestion pipeline

`POST /logs/ingest` appends to a **Redis Stream** and returns `202` immediately;
a separate consumer (`app/consumer.py`, run `python -m app.consumer`) reads the
stream via a **consumer group** and bulk-indexes into OpenSearch. Documents use
the Redis entry ID as the OpenSearch `_id`, so redeliveries overwrite rather than
duplicate (at-least-once ack → effectively exactly-once in the index).

- **Consumer groups** let multiple workers share the stream with no
  double-processing — scale with `docker compose up --scale consumer=3`.
- **Batching** by size (`CONSUMER_BATCH_SIZE`) or flush interval
  (`CONSUMER_FLUSH_MS`); one `_bulk` request per batch.
- **Recovery**: `XAUTOCLAIM` reclaims entries left pending by a dead worker;
  entries that exhaust `CONSUMER_MAX_RETRIES` are routed to a dead-letter stream.
- **Bounded stream** (`LOG_STREAM_MAXLEN`) caps producer memory; graceful
  shutdown drains the in-flight batch. The synchronous path is retained at
  `POST /logs/ingest/sync` for comparison.
- **Serverless producer**: an AWS Lambda (API Gateway → Lambda → Redis Stream)
  is an interchangeable on-demand front door to the same pipeline — see
  [`backend/serverless/`](backend/serverless/README.md).

**Measured** (`scripts/benchmark_ingest.py`, single API worker, 5,000 logs):

| Ingestion path | Throughput |
|----------------|-----------|
| synchronous (`/logs/ingest/sync`) | ~2,000 logs/sec |
| async Redis Streams (`/logs/ingest`) | **~9,750 logs/sec (4.8×)** |

p95 end-to-end latency (async POST → searchable) ≈ **1.06 s**, dominated by
OpenSearch's 1 s `refresh_interval` (tunable). Reproduce:

```bash
docker compose up -d                     # now includes the consumer worker
cd backend && python -m scripts.benchmark_ingest --n 5000 --concurrency 8
```

### Scale benchmarks (1M documents)

`scripts/generate_logs.py` bulk-loads realistic structured logs across 8 services
with a configurable error rate; `scripts/bench_search.py` measures search latency
and the pagination optimization. Measured on a single OpenSearch 2.11 node (1 GB
heap) at **1,000,000 documents, 136 MB on disk**:

- **Bulk ingestion: 19,810 docs/sec** sustained over the full load (1M in 50.5 s).

Search latency at 1M documents (p50 / p95):

| query | p50 | p95 |
|-------|-----|-----|
| free-text (`match` on message) | 6 ms | 12 ms |
| filtered (service + level) | 2 ms | 3 ms |
| filtered + time range | 4 ms | 8 ms |
| free-text + filters combined | 3 ms | 7 ms |

**Slowest pattern + optimization — deep pagination.** The original search used
`from`/`size`, which degrades linearly with depth and is hard-capped at
OpenSearch's 10,000-result window (deeper pages return HTTP 400). Switching to a
`search_after` cursor (with an `_id` sort tiebreaker for stable ordering) makes
deep pages constant-cost and removes the ceiling:

| pagination | p50 | p95 |
|------------|-----|-----|
| `from`/`size` at `from=0` | 4 ms | 9 ms |
| `from`/`size` at `from=9950` (near cap) | 54 ms | 72 ms |
| **`search_after` (any depth)** | **4 ms** | **8 ms** |

→ ~13× faster at the deep end and no 10k limit. `GET /logs/search` now accepts an
optional `search_after` cursor (`[timestamp, id]` of the last returned row).
(The unscored term/range filters were also tested in a `filter` clause; at this
index size the difference was within noise, so the query shape was left as-is.)
Reproduce:

```bash
docker compose up -d
cd backend
python -m scripts.generate_logs --count 1000000 --recreate
python -m scripts.bench_search
```

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

