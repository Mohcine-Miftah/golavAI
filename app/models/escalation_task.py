"""
app/models/escalation_task.py — Human escalation task model.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class EscalationTask(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "escalation_tasks"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False)
    # angry_customer | ambiguous_location | payment_dispute | low_confidence
    # | outside_policy | technical_error | repeated_failure | manual
    reason_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)  # open | in_progress | resolved
    assigned_to: Mapped[str | None] = mapped_column(String(200), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship(  # noqa: F821
        "Conversation", back_populates="escalation_tasks"
    )

    __table_args__ = (
        Index("ix_escalation_tasks_status", "status"),
        Index("ix_escalation_tasks_conversation_id", "conversation_id"),
    )

    def __repr__(self) -> str:
        return f"<EscalationTask id={self.id} status={self.status} reason={self.reason_code}>"
