"""
Pydantic schemas for API requests/responses.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# Alert Rule Schemas
class AlertRuleCreate(BaseModel):
    name: str
    service: Optional[str] = None
    level: str  # DEBUG, INFO, WARN, ERROR, FATAL
    window_minutes: int = Field(gt=0, description="Time window in minutes")
    threshold_count: int = Field(gt=0, description="Alert if count exceeds this")
    enabled: bool = True


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    service: Optional[str] = None
    level: Optional[str] = None
    window_minutes: Optional[int] = Field(None, gt=0)
    threshold_count: Optional[int] = Field(None, gt=0)
    enabled: Optional[bool] = None


class AlertRuleOut(BaseModel):
    id: int
    org_id: str
    name: str
    service: Optional[str]
    level: str
    window_minutes: int
    threshold_count: int
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Incident Schemas
class IncidentOut(BaseModel):
    id: int
    alert_rule_id: int
    start_time: datetime
    end_time: Optional[datetime]
    status: str
    log_query: Optional[str]
    log_count: int
    ai_summary: Optional[str]
    ai_root_cause: Optional[str]
    ai_next_steps: Optional[str]
    created_at: datetime
    updated_at: datetime
    alert_rule: Optional[AlertRuleOut] = None

    class Config:
        from_attributes = True


class IncidentUpdate(BaseModel):
    status: Optional[str] = None  # open, acknowledged, resolved
    end_time: Optional[datetime] = None
