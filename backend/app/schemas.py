"""
Pydantic schemas for API requests/responses.
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

RuleType = Literal["count", "error_rate", "heartbeat_absence"]


# Alert Rule Schemas
class AlertRuleCreate(BaseModel):
    name: str
    service: Optional[str] = None
    level: Optional[str] = None  # required for `count` rules
    window_minutes: int = Field(gt=0, description="Sliding window in minutes")
    rule_type: RuleType = "count"
    threshold_count: int = Field(
        gt=0, description="count threshold, or minimum sample size for error_rate"
    )
    threshold_value: Optional[float] = Field(
        None, gt=0, le=100, description="error-rate percentage (required for error_rate)"
    )
    # Flap damping (balanced defaults)
    for_consecutive: int = Field(1, ge=1, description="sustained breaching evals before opening")
    resolve_after_clear: int = Field(2, ge=1, description="clear evals before auto-resolving")
    cooldown_minutes: int = Field(5, ge=0, description="re-arm delay after resolving")
    enabled: bool = True

    @model_validator(mode="after")
    def _check_required_by_type(self):
        if self.rule_type == "count" and not self.level:
            raise ValueError("count rules require `level`")
        if self.rule_type == "error_rate" and self.threshold_value is None:
            raise ValueError("error_rate rules require `threshold_value` (percentage)")
        if self.rule_type == "heartbeat_absence" and not self.service:
            raise ValueError("heartbeat_absence rules require `service`")
        return self


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    service: Optional[str] = None
    level: Optional[str] = None
    window_minutes: Optional[int] = Field(None, gt=0)
    rule_type: Optional[RuleType] = None
    threshold_count: Optional[int] = Field(None, gt=0)
    threshold_value: Optional[float] = Field(None, gt=0, le=100)
    for_consecutive: Optional[int] = Field(None, ge=1)
    resolve_after_clear: Optional[int] = Field(None, ge=1)
    cooldown_minutes: Optional[int] = Field(None, ge=0)
    enabled: Optional[bool] = None


class AlertRuleOut(BaseModel):
    id: int
    org_id: str
    name: str
    service: Optional[str]
    level: Optional[str]
    window_minutes: int
    rule_type: str
    threshold_count: int
    threshold_value: Optional[float]
    for_consecutive: int
    resolve_after_clear: int
    cooldown_minutes: int
    enabled: bool
    cooldown_until: Optional[datetime]
    last_evaluated_at: Optional[datetime]
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
