"""
Database models for alerts and incidents.
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class AlertRule(Base):
    """Alert rule definition."""
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(String, default="default", index=True)  # For multi-tenancy later
    name = Column(String, nullable=False)
    service = Column(String, nullable=True)  # None = all services
    # level = the level counted by a "count" rule (required for count rules).
    # Unused by error_rate (errors := ERROR+FATAL) and heartbeat_absence.
    level = Column(String, nullable=True)
    window_minutes = Column(Integer, nullable=False)  # Sliding window in minutes

    # rule_type: how the metric is computed and compared.
    #   count             -> # logs at `level` in window >= threshold_count
    #   error_rate        -> (ERROR+FATAL)/total in window >= threshold_value %,
    #                        guarded by total >= threshold_count (min sample size)
    #   heartbeat_absence -> # logs from `service` in window == 0 (service went silent)
    rule_type = Column(String, nullable=False, default="count")
    threshold_count = Column(Integer, nullable=False)  # count threshold / min volume
    threshold_value = Column(Float, nullable=True)  # error-rate percentage (0-100)

    # Flap damping
    for_consecutive = Column(Integer, nullable=False, default=1)  # sustained breaches to open
    resolve_after_clear = Column(Integer, nullable=False, default=2)  # clear evals to auto-resolve
    cooldown_minutes = Column(Integer, nullable=False, default=5)  # re-arm delay after resolve

    enabled = Column(Boolean, default=True)

    # Evaluator runtime state (persisted between ticks)
    breach_streak = Column(Integer, nullable=False, default=0)
    clear_streak = Column(Integer, nullable=False, default=0)
    cooldown_until = Column(DateTime, nullable=True)
    last_evaluated_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to incidents
    incidents = relationship("Incident", back_populates="alert_rule")


class Incident(Base):
    """Incident created when an alert rule triggers."""
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    alert_rule_id = Column(Integer, ForeignKey("alert_rules.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)  # None if still open
    status = Column(String, default="open")  # open, acknowledged, resolved
    log_query = Column(Text)  # JSON query used to find matching logs
    log_count = Column(Integer, default=0)  # Number of logs that matched
    ai_summary = Column(Text, nullable=True)
    ai_root_cause = Column(Text, nullable=True)
    ai_next_steps = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to alert rule
    alert_rule = relationship("AlertRule", back_populates="incidents")
