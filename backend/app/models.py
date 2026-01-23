"""
Database models for alerts and incidents.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class AlertRule(Base):
    """Alert rule definition."""
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(String, default="default", index=True)  # For multi-tenancy later
    name = Column(String, nullable=False)
    service = Column(String, nullable=True)  # None = all services
    level = Column(String, nullable=False)  # DEBUG, INFO, WARN, ERROR, FATAL
    window_minutes = Column(Integer, nullable=False)  # Time window in minutes
    threshold_count = Column(Integer, nullable=False)  # Alert if count > threshold
    enabled = Column(Boolean, default=True)
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
