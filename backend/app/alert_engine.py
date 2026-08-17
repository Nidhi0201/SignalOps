"""
Alert evaluation engine.

Split into a PURE decision core (`decide`) that is trivially unit-testable, and
thin I/O around it (`compute_metric` queries OpenSearch, `evaluate_rule` reads
and writes Postgres). The scheduler and the measurement harness both drive
`evaluate_all_rules`, passing an explicit `now` so evaluation is deterministic.

Flap damping:
  * open only after `for_consecutive` sustained breaching evaluations
  * auto-resolve only after `resolve_after_clear` consecutive clear evaluations
  * after resolving, a `cooldown_minutes` re-arm delay blocks immediate reopen
  * while an incident is open, further breaches update it (dedup) rather than
    opening a second incident
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import AlertRule, Incident

ERROR_LEVELS = ["ERROR", "FATAL"]


# --------------------------------------------------------------------------- #
# Pure decision core
# --------------------------------------------------------------------------- #
@dataclass
class Decision:
    action: str  # "open" | "resolve" | "update" | "noop"
    breach_streak: int
    clear_streak: int
    cooldown_until: Optional[datetime]


def decide(
    *,
    breaching: bool,
    has_open_incident: bool,
    breach_streak: int,
    clear_streak: int,
    cooldown_until: Optional[datetime],
    for_consecutive: int,
    resolve_after_clear: int,
    cooldown_minutes: int,
    now: datetime,
) -> Decision:
    """Decide what to do this tick given the metric outcome and prior state.

    This function has no I/O; the returned streak/cooldown values are what the
    caller must persist. Cooldown only blocks *opening* a new incident.
    """
    in_cooldown = cooldown_until is not None and now < cooldown_until

    if breaching:
        breach_streak += 1
        clear_streak = 0
        if has_open_incident:
            return Decision("update", breach_streak, clear_streak, cooldown_until)
        if breach_streak >= for_consecutive and not in_cooldown:
            # Opening clears any lingering cooldown.
            return Decision("open", breach_streak, clear_streak, None)
        return Decision("noop", breach_streak, clear_streak, cooldown_until)

    # not breaching
    clear_streak += 1
    breach_streak = 0
    if has_open_incident and clear_streak >= resolve_after_clear:
        return Decision(
            "resolve", breach_streak, clear_streak, now + timedelta(minutes=cooldown_minutes)
        )
    return Decision("noop", breach_streak, clear_streak, cooldown_until)


# --------------------------------------------------------------------------- #
# Metric computation (OpenSearch I/O)
# --------------------------------------------------------------------------- #
@dataclass
class MetricResult:
    breaching: bool
    observed: float  # count, or error-rate %, or 0 for heartbeat
    incident_count: int  # log_count to record on the incident
    query: dict[str, Any]  # the query used, stored on the incident for later drill-down


def _count(client, must: list[dict[str, Any]]) -> int:
    body = {"query": {"bool": {"must": must}}}
    return int(client.count(index="logs", body=body).get("count", 0))


def _window_filter(now: datetime, window_minutes: int) -> dict[str, Any]:
    start = now - timedelta(minutes=window_minutes)
    return {"range": {"timestamp": {"gte": start.isoformat(), "lte": now.isoformat()}}}


def compute_metric(rule: AlertRule, client, now: datetime) -> MetricResult:
    """Query OpenSearch and decide whether `rule` is breaching right now."""
    window = _window_filter(now, rule.window_minutes)
    service_filter = [{"term": {"service": rule.service}}] if rule.service else []

    if rule.rule_type == "heartbeat_absence":
        must = service_filter + [window]
        total = _count(client, must)
        return MetricResult(
            breaching=(total == 0), observed=total, incident_count=0,
            query={"query": {"bool": {"must": must}}},
        )

    if rule.rule_type == "error_rate":
        base = service_filter + [window]
        total = _count(client, base)
        errors = _count(client, service_filter + [window, {"terms": {"level": ERROR_LEVELS}}])
        rate = (errors / total * 100.0) if total > 0 else 0.0
        breaching = total >= rule.threshold_count and rate >= (rule.threshold_value or 0)
        return MetricResult(
            breaching=breaching, observed=round(rate, 2), incident_count=errors,
            query={"query": {"bool": {"must": service_filter + [{"terms": {"level": ERROR_LEVELS}}]}}},
        )

    # default: count rule
    must = service_filter + [window, {"term": {"level": rule.level}}]
    count = _count(client, must)
    return MetricResult(
        breaching=(count >= rule.threshold_count), observed=count, incident_count=count,
        query={"query": {"bool": {"must": [{"term": {"level": rule.level}}] + service_filter}}},
    )


# --------------------------------------------------------------------------- #
# Orchestration (Postgres I/O)
# --------------------------------------------------------------------------- #
def evaluate_rule(rule: AlertRule, client, db: Session, now: Optional[datetime] = None) -> Optional[str]:
    """Evaluate one rule, applying the decision to the incident table.

    Returns the action taken ("open"/"resolve"/"update"/"noop").
    """
    now = now or datetime.utcnow()
    metric = compute_metric(rule, client, now)

    open_incident = (
        db.query(Incident)
        .filter(Incident.alert_rule_id == rule.id, Incident.status.in_(["open", "acknowledged"]))
        .first()
    )

    decision = decide(
        breaching=metric.breaching,
        has_open_incident=open_incident is not None,
        breach_streak=rule.breach_streak or 0,
        clear_streak=rule.clear_streak or 0,
        cooldown_until=rule.cooldown_until,
        for_consecutive=rule.for_consecutive,
        resolve_after_clear=rule.resolve_after_clear,
        cooldown_minutes=rule.cooldown_minutes,
        now=now,
    )

    if decision.action == "open":
        incident = Incident(
            alert_rule_id=rule.id,
            start_time=now,
            status="open",
            log_query=json.dumps(metric.query),
            log_count=metric.incident_count,
        )
        db.add(incident)
    elif decision.action == "update" and open_incident is not None:
        open_incident.log_count = metric.incident_count
        open_incident.updated_at = now
    elif decision.action == "resolve" and open_incident is not None:
        open_incident.status = "resolved"
        open_incident.end_time = now
        open_incident.updated_at = now

    # Persist evaluator state on the rule.
    rule.breach_streak = decision.breach_streak
    rule.clear_streak = decision.clear_streak
    rule.cooldown_until = decision.cooldown_until
    rule.last_evaluated_at = now

    db.commit()
    return decision.action


def evaluate_all_rules(db: Session, client, now: Optional[datetime] = None) -> dict[str, int]:
    """Evaluate every enabled rule. Returns a tally of actions taken."""
    now = now or datetime.utcnow()
    tally = {"open": 0, "resolve": 0, "update": 0, "noop": 0}
    rules = db.query(AlertRule).filter(AlertRule.enabled.is_(True)).all()
    for rule in rules:
        try:
            action = evaluate_rule(rule, client, db, now)
            tally[action] = tally.get(action, 0) + 1
        except Exception as e:  # one bad rule must not stop the rest
            db.rollback()
            print(f"❌ Error evaluating rule {rule.id} ({rule.name}): {e}")
    return tally
