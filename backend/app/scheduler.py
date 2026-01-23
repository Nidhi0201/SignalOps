"""
Scheduler to check alert rules and create incidents.
"""
from datetime import datetime, timedelta
from typing import Any
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.database import SessionLocal
from app.models import AlertRule, Incident
from opensearchpy import OpenSearch
from app.ai_service import summarize_incident
import json


def get_opensearch_client() -> OpenSearch:
    """Get OpenSearch client for scheduler (not a FastAPI dependency)."""
    return OpenSearch(
        hosts=[{"host": "localhost", "port": 9200}],
        http_auth=None,
        use_ssl=False,
        verify_certs=False,
        timeout=5,
    )


def check_alert_rule(rule: AlertRule, opensearch_client: OpenSearch, db: Session):
    """Check a single alert rule and create incident if threshold exceeded."""
    # Calculate time window
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=rule.window_minutes)

    # Build OpenSearch query
    must: list[dict[str, Any]] = [
        {"term": {"level": rule.level}},
    ]

    if rule.service:
        must.append({"term": {"service": rule.service}})

    must.append({
        "range": {
            "timestamp": {
                "gte": window_start.isoformat(),
                "lte": now.isoformat(),
            }
        }
    })

    query_body = {
        "query": {"bool": {"must": must}},
        "size": 0,  # We only need the count
    }

    try:
        resp = opensearch_client.search(index="logs", body=query_body)
        total_hits = resp.get("hits", {}).get("total", {}).get("value", 0)

        # Check if threshold exceeded
        if total_hits >= rule.threshold_count:
            # Check if there's already an open incident for this rule
            existing = db.query(Incident).filter(
                Incident.alert_rule_id == rule.id,
                Incident.status == "open",
            ).first()

            if not existing:
                # Get sample logs for AI summarization
                query_body_with_logs = query_body.copy()
                query_body_with_logs["size"] = 200  # Get up to 200 logs
                query_body_with_logs["sort"] = [{"timestamp": {"order": "desc"}}]
                
                logs_resp = opensearch_client.search(index="logs", body=query_body_with_logs)
                sample_logs = [hit["_source"] for hit in logs_resp.get("hits", {}).get("hits", [])]
                
                # Create new incident
                incident = Incident(
                    alert_rule_id=rule.id,
                    start_time=window_start,
                    status="open",
                    log_query=json.dumps(query_body),
                    log_count=total_hits,
                )
                db.add(incident)
                db.commit()
                db.refresh(incident)
                
                # Auto-trigger AI summarization
                try:
                    time_window = f"{window_start.isoformat()} to {now.isoformat()}"
                    ai_result = summarize_incident(sample_logs, rule.service, time_window)
                    incident.ai_summary = ai_result.get("summary")
                    incident.ai_root_cause = ai_result.get("root_cause")
                    incident.ai_next_steps = ai_result.get("next_steps")
                    db.commit()
                    print(f"✅ Created incident {incident.id} with AI summary for alert rule '{rule.name}' ({total_hits} logs)")
                except Exception as e:
                    print(f"⚠️  AI summarization failed for incident {incident.id}: {e}")
                    print(f"✅ Created incident {incident.id} without AI summary")
            else:
                # Update existing incident with latest count
                existing.log_count = total_hits
                existing.log_query = json.dumps(query_body)
                existing.updated_at = datetime.utcnow()
                db.commit()
                print(f"📊 Updated incident {existing.id} for alert rule '{rule.name}' ({total_hits} logs)")

    except Exception as e:
        print(f"❌ Error checking alert rule {rule.id}: {e}")


def check_all_alert_rules():
    """Check all enabled alert rules."""
    db = SessionLocal()
    try:
        # Get OpenSearch client
        opensearch_client = get_opensearch_client()

        # Get all enabled alert rules
        rules = db.query(AlertRule).filter(AlertRule.enabled == True).all()

        for rule in rules:
            check_alert_rule(rule, opensearch_client, db)

    except Exception as e:
        print(f"❌ Error in scheduler: {e}")
    finally:
        db.close()


def start_scheduler():
    """Start the background scheduler."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        check_all_alert_rules,
        trigger=IntervalTrigger(minutes=1),
        id="check_alerts",
        name="Check alert rules every minute",
        replace_existing=True,
    )
    scheduler.start()
    print("✅ Alert scheduler started (checking every minute)")
    return scheduler
