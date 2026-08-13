import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.geofence import get_client_ip, is_ip_allowed
from app.core.security import get_optional_subject, require_student
from app.db.models import ExamLog, ExamSession
from app.db.session import get_db
from app.schemas.exam import TrackingEvent

router = APIRouter(prefix="/tracking", tags=["tracking"])
settings = get_settings()


async def _latest_session(db: AsyncSession, student_id: int) -> ExamSession | None:
    result = await db.execute(
        select(ExamSession)
        .where(
            ExamSession.student_id == student_id,
            ExamSession.end_time.is_(None),
        )
        .order_by(ExamSession.start_time.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()
    if session:
        return session

    result = await db.execute(
        select(ExamSession)
        .where(ExamSession.student_id == student_id)
        .order_by(ExamSession.start_time.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _session_for_subject(
    db: AsyncSession,
    student_id: int,
    subject: dict[str, object],
) -> ExamSession | None:
    session_id = subject.get("session_id")
    if session_id:
        result = await db.execute(
            select(ExamSession).where(
                ExamSession.id == int(session_id),
                ExamSession.student_id == student_id,
            )
        )
        session = result.scalar_one_or_none()
        if session:
            return session

    return await _latest_session(db, student_id)


def _details_json(
    payload: TrackingEvent,
    client_ip: str,
    session_id: int | None,
) -> str:
    details = payload.model_dump(exclude_none=True, mode="json")
    details.pop("event_type", None)
    details["ip_address"] = client_ip
    details["session_id"] = session_id
    return json.dumps(details, separators=(",", ":"))


@router.get("/ip")
async def read_ip(request: Request) -> dict[str, str | bool]:
    client_ip = get_client_ip(request)
    return {
        "ip": client_ip,
        "allowed": is_ip_allowed(client_ip, settings.ALLOWED_IP_RANGES),
    }


@router.post("/events")
async def log_event(
    payload: TrackingEvent,
    request: Request,
    db: AsyncSession = Depends(get_db),
    subject: dict[str, object] = Depends(require_student),
) -> dict[str, str | int | None]:
    client_ip = get_client_ip(request)
    student_id = int(subject["student_id"])
    timestamp = datetime.now(timezone.utc)
    session = await _session_for_subject(db, student_id, subject)

    db.add(
        ExamLog(
            student_id=student_id,
            session_id=session.id if session else None,
            event_type=payload.event_type,
            timestamp=timestamp,
            details=_details_json(payload, client_ip, session.id if session else None),
        )
    )

    if session:
        if payload.event_type == "EXAM_END" and session.end_time is None:
            session.end_time = timestamp
        if payload.event_type == "LOCATION":
            if payload.location:
                session.location = payload.location
            elif payload.latitude is not None and payload.longitude is not None:
                session.location = f"{payload.latitude},{payload.longitude}"
        if payload.network_isp:
            session.network_isp = payload.network_isp

    await db.commit()
    return {
        "status": "logged",
        "event_type": payload.event_type,
        "ip": client_ip,
        "session_id": session.id if session else None,
        "timestamp": timestamp.isoformat(),
    }


@router.get("/geofence/check")
async def check_geofence(
    request: Request,
    db: AsyncSession = Depends(get_db),
    subject: dict[str, object] | None = Depends(get_optional_subject),
) -> dict[str, str | bool]:
    client_ip = get_client_ip(request)
    allowed = is_ip_allowed(client_ip, settings.ALLOWED_IP_RANGES)

    if subject and subject.get("role") == "student":
        student_id = int(subject["student_id"])
        session = await _latest_session(db, student_id)
        if session and session.ip_address != client_ip:
            session.ip_address = client_ip

        if not allowed:
            db.add(
                ExamLog(
                    student_id=student_id,
                    session_id=session.id if session else None,
                    event_type="IP_MISMATCH",
                    timestamp=datetime.now(timezone.utc),
                    details=json.dumps(
                        {
                            "ip_address": client_ip,
                            "allowed_ranges": settings.ALLOWED_IP_RANGES,
                            "session_id": session.id if session else None,
                        },
                        separators=(",", ":"),
                    ),
                )
            )
        await db.commit()

    return {
        "ip": client_ip,
        "allowed": allowed,
        "allowed_ranges": settings.ALLOWED_IP_RANGES,
    }
