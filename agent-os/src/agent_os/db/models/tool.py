"""Tool ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from agent_os.db.connection import Base
from agent_os.db.models.tool_call import RiskLevel


class Tool(Base):
    __tablename__ = "tools"

    tool_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    permissions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    risk_level: Mapped[RiskLevel | None] = mapped_column(Enum(RiskLevel), default=RiskLevel.LOW)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    timeout_sec: Mapped[int] = mapped_column(Integer, default=30)
    max_retries: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
