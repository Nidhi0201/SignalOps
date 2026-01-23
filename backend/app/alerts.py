"""
Alert and Incident API endpoints.
"""
from datetime import datetime, timedelta
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import AlertRule, Incident
from app.schemas import (
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertRuleOut,
    IncidentOut,
    IncidentUpdate,
)
import json

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("", response_model=AlertRuleOut, status_code=201)
def create_alert_rule(
    rule: AlertRuleCreate,
    db: Session = Depends(get_db),
):
    """Create a new alert rule."""
    db_rule = AlertRule(**rule.model_dump())
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    return db_rule


@router.get("", response_model=list[AlertRuleOut])
def list_alert_rules(
    enabled: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    """List all alert rules, optionally filtered by enabled status."""
    query = db.query(AlertRule)
    if enabled is not None:
        query = query.filter(AlertRule.enabled == enabled)
    return query.order_by(desc(AlertRule.created_at)).all()


@router.get("/{rule_id}", response_model=AlertRuleOut)
def get_alert_rule(rule_id: int, db: Session = Depends(get_db)):
    """Get a specific alert rule."""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return rule


@router.patch("/{rule_id}", response_model=AlertRuleOut)
def update_alert_rule(
    rule_id: int,
    update: AlertRuleUpdate,
    db: Session = Depends(get_db),
):
    """Update an alert rule."""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)
    rule.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(rule)
    return rule


@router.post("/{rule_id}/toggle", response_model=AlertRuleOut)
def toggle_alert_rule(rule_id: int, db: Session = Depends(get_db)):
    """Toggle enabled status of an alert rule."""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    rule.enabled = not rule.enabled
    rule.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=204)
def delete_alert_rule(rule_id: int, db: Session = Depends(get_db)):
    """Delete an alert rule."""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    db.delete(rule)
    db.commit()
    return None


# Incident endpoints
@router.get("/incidents", response_model=list[IncidentOut])
def list_incidents(
    status: Optional[str] = None,
    alert_rule_id: Optional[int] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List incidents, optionally filtered by status or alert rule."""
    query = db.query(Incident)
    if status:
        query = query.filter(Incident.status == status)
    if alert_rule_id:
        query = query.filter(Incident.alert_rule_id == alert_rule_id)
    return query.order_by(desc(Incident.created_at)).limit(limit).all()


@router.get("/incidents/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    """Get a specific incident."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.patch("/incidents/{incident_id}", response_model=IncidentOut)
def update_incident(
    incident_id: int,
    update: IncidentUpdate,
    db: Session = Depends(get_db),
):
    """Update an incident (e.g., acknowledge or resolve)."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(incident, key, value)
    incident.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(incident)
    return incident


@router.post("/incidents/{incident_id}/ack", response_model=IncidentOut)
def acknowledge_incident(incident_id: int, db: Session = Depends(get_db)):
    """Acknowledge an incident."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.status = "acknowledged"
    incident.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(incident)
    return incident


@router.post("/incidents/{incident_id}/resolve", response_model=IncidentOut)
def resolve_incident(incident_id: int, db: Session = Depends(get_db)):
    """Resolve an incident."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.status = "resolved"
    incident.end_time = datetime.utcnow()
    incident.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(incident)
    return incident


@router.post("/incidents/{incident_id}/summarize", response_model=IncidentOut)
def summarize_incident_endpoint(incident_id: int, db: Session = Depends(get_db)):
    """Manually trigger AI summarization for an incident."""
    from app.ai_service import summarize_incident
    from app.main import get_opensearch
    
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Get OpenSearch client
    opensearch_client = get_opensearch()
    
    # Parse log query
    try:
        query_body = json.loads(incident.log_query or "{}")
        query_body["size"] = 200
        query_body["sort"] = [{"timestamp": {"order": "desc"}}]
    except:
        query_body = {"query": {"match_all": {}}, "size": 200}
    
    # Fetch logs
    logs_resp = opensearch_client.search(index="logs", body=query_body)
    sample_logs = [hit["_source"] for hit in logs_resp.get("hits", {}).get("hits", [])]
    
    # Get alert rule for context
    alert_rule = db.query(AlertRule).filter(AlertRule.id == incident.alert_rule_id).first()
    service = alert_rule.service if alert_rule else None
    time_window = f"{incident.start_time.isoformat()} to {incident.end_time.isoformat() if incident.end_time else datetime.utcnow().isoformat()}"
    
    # Generate AI summary
    ai_result = summarize_incident(sample_logs, service, time_window)
    incident.ai_summary = ai_result.get("summary")
    incident.ai_root_cause = ai_result.get("root_cause")
    incident.ai_next_steps = ai_result.get("next_steps")
    incident.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(incident)
    return incident
