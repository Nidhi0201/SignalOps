import json
import os
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from opensearchpy import OpenSearch
from pydantic import BaseModel, Field
from redis import Redis

from app.alerts import router as alerts_router
from app.database import Base, engine
from app.redis_client import LOG_STREAM, LOG_STREAM_MAXLEN, get_redis
from app.scheduler import start_scheduler

app = FastAPI(title="SignalOps Backend", version="0.1.0")

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include alert routes
app.include_router(alerts_router)

# Initialize database tables on startup
@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    # Start alert scheduler (skipped in tests / CI via DISABLE_SCHEDULER=1)
    if os.getenv("DISABLE_SCHEDULER") != "1":
        start_scheduler()


class LogIn(BaseModel):
  timestamp: datetime = Field(default_factory=datetime.utcnow)
  service: str
  level: Literal["DEBUG", "INFO", "WARN", "ERROR", "FATAL"]
  message: str
  trace_id: Optional[str] = None
  metadata: dict[str, Any] = Field(default_factory=dict)


class LogOut(LogIn):
  id: str


_os_singleton: Optional[OpenSearch] = None


def get_opensearch() -> OpenSearch:
  """
  Return a cached OpenSearch client (connection reuse across requests).

  Host/port come from OPENSEARCH_HOST/OPENSEARCH_PORT (default localhost:9200).
  """
  global _os_singleton
  if _os_singleton is not None:
    return _os_singleton
  try:
    client = OpenSearch(
      hosts=[{"host": os.getenv("OPENSEARCH_HOST", "localhost"),
              "port": int(os.getenv("OPENSEARCH_PORT", "9200"))}],
      http_auth=None,  # No auth if security is disabled
      use_ssl=False,
      verify_certs=False,
      timeout=5,
    )

    # Test connection
    client.info()

    # Ensure index exists with a simple mapping.
    index_name = "logs"
    if not client.indices.exists(index=index_name):
      client.indices.create(
        index=index_name,
        body={
          "mappings": {
            "properties": {
              "timestamp": {"type": "date"},
              "service": {"type": "keyword"},
              "level": {"type": "keyword"},
              "message": {"type": "text"},
              "trace_id": {"type": "keyword"},
              "metadata": {"type": "object", "enabled": True},
            }
          }
        },
      )

    _os_singleton = client
    return client
  except Exception as e:
    raise HTTPException(
      status_code=503,
      detail=f"OpenSearch connection failed. Make sure Docker containers are running: docker compose up -d. Error: {str(e)}"
    )


@app.post("/logs/ingest", status_code=202)
def ingest_logs(
  payload: list[LogIn] | LogIn,
  r: Redis = Depends(get_redis),
) -> dict[str, Any]:
  """
  Async ingest: append each log to a Redis Stream and return immediately (202).
  A separate consumer process (app.consumer) bulk-indexes into OpenSearch.
  The stream is bounded (MAXLEN ~) so producer memory stays capped.
  """
  logs = payload if isinstance(payload, list) else [payload]
  stream_ids: list[str] = []
  for log in logs:
    body = log.model_dump(mode="json")
    entry_id = r.xadd(
      LOG_STREAM, {"data": json.dumps(body)},
      maxlen=LOG_STREAM_MAXLEN, approximate=True,
    )
    stream_ids.append(entry_id)

  return {"accepted": len(stream_ids), "stream_ids": stream_ids}


@app.post("/logs/ingest/sync", response_model=list[LogOut])
def ingest_logs_sync(
  payload: list[LogIn] | LogIn,
  client: OpenSearch = Depends(get_opensearch),
) -> list[LogOut]:
  """
  Synchronous ingest straight to OpenSearch (blocks until indexed).
  Retained for the sync-vs-async ingestion benchmark.
  """
  logs = payload if isinstance(payload, list) else [payload]
  results: list[LogOut] = []

  for log in logs:
    body = log.model_dump()
    resp = client.index(index="logs", body=body)
    results.append(LogOut(id=resp["_id"], **body))

  return results


@app.get("/logs/search", response_model=list[LogOut])
def search_logs(
  service: Optional[str] = None,
  level: Optional[str] = None,
  q: Optional[str] = None,
  from_ts: Optional[datetime] = Query(None, alias="from"),
  to_ts: Optional[datetime] = Query(None, alias="to"),
  page: int = 1,
  page_size: int = 50,
  client: OpenSearch = Depends(get_opensearch),
) -> list[LogOut]:
  """
  Search logs by service / level / time window / free-text query.
  """
  if page < 1:
    raise HTTPException(status_code=400, detail="page must be >= 1")

  must: list[dict[str, Any]] = []

  if service:
    must.append({"term": {"service": service}})
  if level:
    must.append({"term": {"level": level}})
  if from_ts or to_ts:
    range_query: dict[str, Any] = {}
    if from_ts:
      range_query["gte"] = from_ts
    if to_ts:
      range_query["lte"] = to_ts
    must.append({"range": {"timestamp": range_query}})
  if q:
    must.append({"match": {"message": q}})

  body: dict[str, Any] = {
    "query": {"bool": {"must": must or [{"match_all": {}}]}},
    "sort": [{"timestamp": {"order": "desc"}}],
    "from": (page - 1) * page_size,
    "size": page_size,
  }

  resp = client.search(index="logs", body=body)
  hits = resp.get("hits", {}).get("hits", [])

  results: list[LogOut] = []
  for hit in hits:
    source = hit["_source"]
    # Coerce timestamp back to datetime via Pydantic by re-parsing.
    log = LogOut(id=hit["_id"], **source)
    results.append(log)

  return results


@app.get("/health")
def health() -> dict[str, str]:
  return {"status": "ok"}


@app.get("/logs/services")
def get_services(client: OpenSearch = Depends(get_opensearch)) -> list[str]:
  """
  Get list of all unique service names from logs.
  """
  try:
    # Use aggregation to get unique service names
    body = {
      "size": 0,
      "aggs": {
        "services": {
          "terms": {
            "field": "service",
            "size": 100  # Get up to 100 unique services
          }
        }
      }
    }
    resp = client.search(index="logs", body=body)
    buckets = resp.get("aggregations", {}).get("services", {}).get("buckets", [])
    services = [bucket["key"] for bucket in buckets]
    return sorted(services)
  except Exception:
    # If aggregation fails, fallback to getting services from recent logs
    try:
      resp = client.search(index="logs", body={"size": 1000})
      hits = resp.get("hits", {}).get("hits", [])
      services = set()
      for hit in hits:
        service = hit.get("_source", {}).get("service")
        if service:
          services.add(service)
      return sorted(list(services))
    except Exception:
      return []


# Phase 4: Ask My Logs RAG Chat
class AskRequest(BaseModel):
  question: str
  service: Optional[str] = None
  level: Optional[str] = None
  from_ts: Optional[datetime] = None
  to_ts: Optional[datetime] = None
  limit: int = 50

  class Config:
    populate_by_name = True
    json_schema_extra = {
      "example": {
        "question": "Why did payment fail?",
        "service": "payment-service",
        "level": "ERROR",
        "from": "2024-01-15T00:00:00Z",
        "to": "2024-01-15T23:59:59Z"
      }
    }


@app.post("/logs/ask")
def ask_logs(
  request: AskRequest,
  client: OpenSearch = Depends(get_opensearch),
) -> dict[str, Any]:
  """
  Ask a question about logs using RAG (Retrieval-Augmented Generation).
  Returns answer with citations to relevant logs.
  """
  from app.ai_service import answer_log_question

  # Build search query to retrieve relevant logs
  must: list[dict[str, Any]] = []
  should: list[dict[str, Any]] = []

  # Service filter (normalize to match stored service names)
  if request.service:
    # Normalize service name - stored as lowercase with hyphens
    service_normalized = request.service.lower().strip()
    # Use term query for exact match on keyword field
    must.append({"term": {"service": service_normalized}})

  # Level filter
  if request.level:
    must.append({"term": {"level": request.level}})

  # Date range filter - only apply if both dates provided
  # This prevents filtering out all logs when user sets wrong date
  if request.from_ts and request.to_ts:
    must.append({"range": {"timestamp": {"gte": request.from_ts, "lte": request.to_ts}}})
  # If only one date provided, don't filter by date (search all logs)

  # Add question keywords to search (as should clause for better matching)
  if request.question:
    should.append({"match": {"message": {"query": request.question, "operator": "or"}}})
    # Also try fuzzy matching for typos
    should.append({"match": {"message": {"query": request.question, "fuzziness": "AUTO"}}})

  # Build query
  query: dict[str, Any] = {}
  if must and should:
    query = {"bool": {"must": must, "should": should, "minimum_should_match": 1}}
  elif must:
    query = {"bool": {"must": must}}
  elif should:
    query = {"bool": {"should": should, "minimum_should_match": 1}}
  else:
    query = {"match_all": {}}

  query_body: dict[str, Any] = {
    "query": query,
    "sort": [{"timestamp": {"order": "desc"}}],
    "size": request.limit,
  }

  # Search logs
  resp = client.search(index="logs", body=query_body)
  hits = resp.get("hits", {}).get("hits", [])

  logs = []
  for hit in hits:
    source = hit["_source"]
    source["id"] = hit["_id"]  # Add OpenSearch ID
    logs.append(source)

  # Build context
  context = f"Searching {len(logs)} logs"
  if request.service:
    context += f" from {request.service}"
  if request.from_ts or request.to_ts:
    context += " in specified time range"

  # Get AI answer
  result = answer_log_question(request.question, logs, context)

  return {
    "question": request.question,
    "answer": result["answer"],
    "citations": result["citations"],
    "log_count": len(logs),
  }

