"""
app/api/admin/bookings.py — Admin REST API for bookings management.
"""
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_api_key
from app.models.booking import Booking
from app.models.customer import Customer
from app.models.escalation_task import EscalationTask
from app.schemas.booking import BookingResponse, BookingStatusUpdateRequest

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/bookings", response_model=List[BookingResponse])
async def list_bookings(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    """List bookings with optional status filter."""
    query = select(Booking).order_by(Booking.created_at.desc()).limit(limit).offset(offset)
    if status:
        query = query.where(Booking.status == status)
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/bookings/{booking_id}", response_model=BookingResponse)
async def get_booking(booking_id: str, session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(Booking).where(Booking.id == uuid.UUID(booking_id)))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.patch("/bookings/{booking_id}")
async def update_booking_status(
    booking_id: str,
    body: BookingStatusUpdateRequest,
    session: AsyncSession = Depends(get_db),
):
    """Human agent updates booking status."""
    result = await session.execute(select(Booking).where(Booking.id == uuid.UUID(booking_id)))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    from app.models.audit_log import AuditLog
    booking.status = body.status
    if body.notes:
        booking.notes = body.notes

    session.add(AuditLog(
        entity_type="booking",
        entity_id=uuid.UUID(booking_id),
        action=f"booking.status_updated_to_{body.status}",
        actor_type="human",
        details={"notes": body.notes},
    ))
    await session.commit()
    return {"success": True, "status": booking.status}


@router.get("/escalations")
async def list_escalations(
    status: str = "open",
    session: AsyncSession = Depends(get_db),
):
    """List open escalation tasks for human agents."""
    result = await session.execute(
        select(EscalationTask)
        .where(EscalationTask.status == status)
        .order_by(EscalationTask.created_at.asc())
    )
    tasks = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "conversation_id": str(t.conversation_id),
            "reason_code": t.reason_code,
            "reason_text": t.reason_text,
            "status": t.status,
            "created_at": t.created_at.isoformat(),
        }
        for t in tasks
    ]


@router.post("/escalations/{task_id}/resolve")
async def resolve_escalation(task_id: str, session: AsyncSession = Depends(get_db)):
    """Mark an escalation task as resolved and optionally resume AI handling."""
    result = await session.execute(select(EscalationTask).where(EscalationTask.id == uuid.UUID(task_id)))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Escalation task not found")

    from app.models.conversation import Conversation
    from datetime import UTC
    task.status = "resolved"
    task.resolved_at = datetime.now(UTC)

    conv_result = await session.execute(select(Conversation).where(Conversation.id == task.conversation_id))
    conv = conv_result.scalar_one_or_none()
    if conv:
        conv.escalated = False

    await session.commit()
    return {"success": True}
