## SignalOps – Mini Datadog/ELK

This project is a small observability platform:

- **Ingestion API (FastAPI)**: services send JSON logs to `/logs/ingest`.
- **Indexing (OpenSearch)**: logs are indexed and queryable.
- **Queue (Redis Streams)**: planned for streaming pipeline.
- **DB (Postgres)**: planned for alerts, incidents, and users.
- **Dashboard (Next.js)**: search and explore logs.

### Getting started (Phase 1 – Log Search)

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

### API Endpoints

- `POST /logs/ingest` - Ingest single log or batch (accepts `LogIn` or `list[LogIn]`)
- `GET /logs/search` - Search logs with filters:
  - `service` - Filter by service name
  - `level` - Filter by log level (DEBUG, INFO, WARN, ERROR, FATAL)
  - `q` - Free-text search in message field
  - `from` - Start timestamp (ISO format)
  - `to` - End timestamp (ISO format)
  - `page` - Page number (default: 1)
  - `page_size` - Results per page (default: 50)
- `GET /health` - Health check endpoint

### Project Structure

```
SignalOps/
├── backend/           # FastAPI backend
│   ├── app/
│   │   └── main.py    # Main API application
│   └── pyproject.toml # Poetry dependencies
├── frontend/          # Next.js 15 dashboard
│   ├── app/           # App router pages
│   └── package.json   # npm dependencies
├── docker-compose.yml # Infrastructure services
└── README.md          # This file
```

### Next Steps (Phases 2-4)

- **Phase 2**: Alert rules + incidents (Postgres schema + scheduler)
- **Phase 3**: AI incident summarizer
- **Phase 4**: "Ask My Logs" RAG chat

