"""Policy ORM model."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from agent_os.db.connection import Base


class PolicyType(str, enum.Enum):
    BUDGET = "budget"
    DATA_BOUNDARY = "data_boundary"
    TOOL_WHITELIST = "tool_whitelist"
    APPROVAL = "approval"


class Policy(Base):
    __tablename__ = "policies"

    policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    policy_type: Mapped[PolicyType] = mapped_column(Enum(PolicyType), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
