"""
Background scheduler that periodically evaluates alert rules.

The evaluation logic lives in `app.alert_engine`; this module is just the
APScheduler wiring plus best-effort AI summarization of newly opened incidents.
The poll interval is configurable via EVAL_INTERVAL_SECONDS (default 60).
"""
import json
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from opensearchpy import OpenSearch

from app.alert_engine import evaluate_all_rules
from app.database import SessionLocal
from app.models import AlertRule, Incident


def get_opensearch_client() -> OpenSearch:
    """Get OpenSearch client for the scheduler (not a FastAPI dependency)."""
    host = os.getenv("OPENSEARCH_HOST", "localhost")
    port = int(os.getenv("OPENSEARCH_PORT", "9200"))
    return OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_auth=None,
        use_ssl=False,
        verify_certs=False,
        timeout=5,
    )


def _summarize_new_incidents(db, client) -> None:
    """Best-effort AI summary for open incidents that don't have one yet."""
    from app.ai_service import summarize_incident

    pending = (
        db.query(Incident)
        .filter(Incident.status == "open", Incident.ai_summary.is_(None))
        .all()
    )
    for incident in pending:
        try:
            query_body = json.loads(incident.log_query or "{}")
            query_body["size"] = 200
            query_body["sort"] = [{"timestamp": {"order": "desc"}}]
            resp = client.search(index="logs", body=query_body)
            sample = [hit["_source"] for hit in resp.get("hits", {}).get("hits", [])]

            rule = db.query(AlertRule).filter(AlertRule.id == incident.alert_rule_id).first()
            service = rule.service if rule else None
            window = f"{incident.start_time.isoformat()} to now"
            result = summarize_incident(sample, service, window)
            incident.ai_summary = result.get("summary")
            incident.ai_root_cause = result.get("root_cause")
            incident.ai_next_steps = result.get("next_steps")
            db.commit()
        except Exception as e:
            print(f"⚠️  AI summarization failed for incident {incident.id}: {e}")


def run_evaluation_cycle() -> None:
    """One evaluation pass over all enabled rules."""
    db = SessionLocal()
    try:
        client = get_opensearch_client()
        tally = evaluate_all_rules(db, client)
        if tally.get("open") or tally.get("resolve"):
            print(f"🔔 Alert cycle: {tally}")
        if tally.get("open"):
            _summarize_new_incidents(db, client)
    except Exception as e:
        print(f"❌ Error in scheduler: {e}")
    finally:
        db.close()


def start_scheduler():
    """Start the background scheduler."""
    interval = int(os.getenv("EVAL_INTERVAL_SECONDS", "60"))
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_evaluation_cycle,
        trigger=IntervalTrigger(seconds=interval),
        id="check_alerts",
        name=f"Evaluate alert rules every {interval}s",
        replace_existing=True,
    )
    scheduler.start()
    print(f"✅ Alert scheduler started (evaluating every {interval}s)")
    return scheduler
