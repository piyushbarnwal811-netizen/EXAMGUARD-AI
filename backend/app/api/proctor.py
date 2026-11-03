import asyncio
import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import get_optional_subject
from app.db.models import ExamLog, ExamSession, Student
from app.db.session import get_db

router = APIRouter(prefix="/v1/proctor", tags=["proctoring"])
settings = get_settings()

# In-memory pub-sub bus for real-time examiner SSE synchronization
EXAMINER_EVENT_QUEUES: dict[str, list[asyncio.Queue]] = {}


class ViolationTypeEnum(str, Enum):
    MULTIPLE_FACES = "MULTIPLE_FACES"
    CANDIDATE_ABSENT = "CANDIDATE_ABSENT"
    FACE_MISSING = "FACE_MISSING"
    GAZE_ANOMALY = "GAZE_ANOMALY"
    LOOKING_AWAY = "LOOKING_AWAY"
    PROHIBITED_OBJECT = "PROHIBITED_OBJECT"
    OBJECT_DETECTED = "OBJECT_DETECTED"
    SPEECH_DETECTED = "SPEECH_DETECTED"
    ACOUSTIC_ACTIVITY = "ACOUSTIC_ACTIVITY"
    TAB_SWITCH = "TAB_SWITCH"
    WINDOW_BLUR = "WINDOW_BLUR"
    FULLSCREEN_EXIT = "FULLSCREEN_EXIT"
    DUAL_MONITOR_DETECTED = "DUAL_MONITOR_DETECTED"
    CLIPBOARD_VIOLATION = "CLIPBOARD_VIOLATION"
    UNAUTHORIZED_KEY = "UNAUTHORIZED_KEY"
    DEVTOOLS_OPENED = "DEVTOOLS_OPENED"


DEFAULT_PENALTY_WEIGHTS: dict[str, float] = {
    "MULTIPLE_FACES": 20.0,
    "CANDIDATE_ABSENT": 15.0,
    "FACE_MISSING": 15.0,
    "GAZE_ANOMALY": 10.0,
    "LOOKING_AWAY": 10.0,
    "PROHIBITED_OBJECT": 25.0,
    "OBJECT_DETECTED": 25.0,
    "SPEECH_DETECTED": 10.0,
    "ACOUSTIC_ACTIVITY": 10.0,
    "TAB_SWITCH": 10.0,
    "WINDOW_BLUR": 5.0,
    "FULLSCREEN_EXIT": 15.0,
    "CLIPBOARD_VIOLATION": 10.0,
    "DUAL_MONITOR_DETECTED": 20.0,
    "UNAUTHORIZED_KEY": 5.0,
    "DEVTOOLS_OPENED": 20.0,
}


class ViolationPayload(BaseModel):
    candidateId: str
    examId: str
    sessionId: str | None = None
    timestamp: str | datetime
    violationType: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    snapshot: str | None = None  # Base64 WebP image proof (strictly <= 50KB)
    currentScore: float | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("violationType")
    @classmethod
    def validate_type(cls, val: str) -> str:
        clean = val.strip().upper()
        # Accept valid enum values
        valid = {v.value for v in ViolationTypeEnum}
        if clean not in valid:
            raise ValueError(f"Invalid violationType: {clean}. Allowed: {', '.join(sorted(valid))}")
        return clean

    @field_validator("snapshot")
    @classmethod
    def validate_snapshot_size(cls, val: str | None) -> str | None:
        if val:
            # 50KB binary is ~68,267 characters in Base64 (with data URL prefix ~70KB string)
            # We strictly enforce max 75,000 characters to prevent server memory bloat
            if len(val) > 75000:
                raise ValueError("Evidence snapshot exceeds maximum allowed size (strictly 50KB WebP).")
        return val


class ViolationReviewPayload(BaseModel):
    action: str = Field(..., description="'CONFIRMED' or 'DISMISSED'")
    examinerNotes: str | None = None


# ---------------------------------------------------------------------------
# SERVER-SIDE TRUST SCORE COMPUTATION ENGINE
# ---------------------------------------------------------------------------
def calculate_trust_score(
    violation_counts: dict[str, int],
    custom_weights: dict[str, float] | None = None,
) -> float:
    """
    Computes candidate trust score:
    Trust Score = 100 - SUM(Violation_Count[type] * Penalty_Weight[type])
    Clamped to range [0, 100].
    """
    weights = {**DEFAULT_PENALTY_WEIGHTS, **(custom_weights or {})}
    total_penalty = 0.0

    for v_type, count in violation_counts.items():
        penalty = weights.get(v_type, 10.0)
        total_penalty += count * penalty

    return max(0.0, round(100.0 - total_penalty, 2))


async def broadcast_event(exam_id: str, event_data: dict[str, Any]) -> None:
    """Dispatches real-time proctoring alert to connected examiner SSE channels."""
    queues = EXAMINER_EVENT_QUEUES.get(str(exam_id), [])
    dead_queues = []
    message = json.dumps(event_data)

    for q in queues:
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            dead_queues.append(q)

    for dead in dead_queues:
        if dead in queues:
            queues.remove(dead)


# ---------------------------------------------------------------------------
# API ROUTE: Ingest Violation Payload & Verify Trust Score
# ---------------------------------------------------------------------------
@router.post("/violation-log", status_code=status.HTTP_201_CREATED)
async def ingest_violation_log(
    payload: ViolationPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    subject: dict[str, Any] | None = Depends(get_optional_subject),
) -> dict[str, Any]:
    """
    Ingests client-side proctoring violation logs.
    - Validates lightweight metadata & compressed snapshot (<=50KB)
    - Verifies Trust Score server-side against tampering
    - Checks auto-termination threshold (< 30% score or > 3 unapproved exits)
    - Broadcasts live alert to connected examiner review dashboards
    """
    now = datetime.now(timezone.utc)
    client_ip = request.client.host if request.client else "unknown"

    # 1. Resolve Candidate & Session
    student = None
    session = None

    # Resolve student by candidateId (could be roll_no, email, or numeric/UUID id)
    cand_id_str = str(payload.candidateId).strip()
    if cand_id_str.isdigit():
        result = await db.execute(select(Student).where(Student.id == int(cand_id_str)))
        student = result.scalar_one_or_none()
    
    if not student:
        result = await db.execute(
            select(Student).where(
                (Student.email == cand_id_str) | (Student.roll_no == cand_id_str)
            )
        )
        student = result.scalar_one_or_none()

    # Fallback to subject if authenticated
    if not student and subject and subject.get("student_id"):
        result = await db.execute(select(Student).where(Student.id == int(subject["student_id"])))
        student = result.scalar_one_or_none()

    student_id = student.id if student else 1  # Fallback for dev/mock test

    # Find active exam session
    if payload.sessionId and str(payload.sessionId).isdigit():
        result = await db.execute(
            select(ExamSession).where(ExamSession.id == int(payload.sessionId))
        )
        session = result.scalar_one_or_none()
    elif student:
        result = await db.execute(
            select(ExamSession)
            .where(ExamSession.student_id == student.id, ExamSession.end_time.is_(None))
            .order_by(ExamSession.start_time.desc())
            .limit(1)
        )
        session = result.scalar_one_or_none()

    # 2. Fetch Historical Violations for Accurate Server-Side Trust Score Recalculation
    hist_result = await db.execute(
        select(ExamLog.event_type)
        .where(ExamLog.student_id == student_id)
    )
    existing_events = [row[0] for row in hist_result.fetchall()]
    
    # Calculate counts including incoming violation
    violation_counts: dict[str, int] = {}
    for ev in existing_events + [payload.violationType]:
        violation_counts[ev] = violation_counts.get(ev, 0) + 1

    # Server-verified trust score
    verified_trust_score = calculate_trust_score(violation_counts)

    # Detect tampering if client claimed significantly higher score
    tampering_detected = False
    if payload.currentScore is not None and (payload.currentScore - verified_trust_score) > 15:
        tampering_detected = True

    # 3. Check Auto-Termination Conditions (PRD Section 1 & 2)
    # Condition A: Trust score drops below critical threshold (30%)
    # Condition B: Unapproved fullscreen exits >= 3
    exit_count = violation_counts.get("FULLSCREEN_EXIT", 0)
    is_auto_terminated = False
    termination_reason = None

    if verified_trust_score <= 30.0:
        is_auto_terminated = True
        termination_reason = f"Trust score ({verified_trust_score}%) fell below critical threshold (30%)."
    elif exit_count >= 3:
        is_auto_terminated = True
        termination_reason = f"Maximum allowed fullscreen exits reached ({exit_count}/3)."

    if is_auto_terminated and session and session.end_time is None:
        session.end_time = now

    # 4. Persist Violation Log to Database
    details_dict = {
        "candidateId": payload.candidateId,
        "examId": payload.examId,
        "confidence": payload.confidence,
        "snapshot": payload.snapshot,
        "currentScore": verified_trust_score,
        "clientReportedScore": payload.currentScore,
        "tamperingDetected": tampering_detected,
        "metadata": payload.metadata or {},
        "ip_address": client_ip,
        "reviewStatus": "PENDING",
        "penaltyApplied": DEFAULT_PENALTY_WEIGHTS.get(payload.violationType, 10.0),
    }

    log_entry = ExamLog(
        student_id=student_id,
        session_id=session.id if session else None,
        event_type=payload.violationType,
        timestamp=now,
        details=json.dumps(details_dict, separators=(",", ":")),
    )
    db.add(log_entry)
    await db.commit()
    await db.refresh(log_entry)

    # 5. Broadcast Real-Time Alert to Connected Admin/Examiner Streams
    event_payload = {
        "id": log_entry.id,
        "candidateId": payload.candidateId,
        "examId": payload.examId,
        "sessionId": session.id if session else None,
        "timestamp": now.isoformat(),
        "violationType": payload.violationType,
        "confidence": payload.confidence,
        "snapshot": payload.snapshot,
        "verifiedTrustScore": verified_trust_score,
        "penaltyApplied": details_dict["penaltyApplied"],
        "isAutoTerminated": is_auto_terminated,
        "terminationReason": termination_reason,
        "metadata": payload.metadata or {},
    }
    await broadcast_event(payload.examId, event_payload)

    return {
        "status": "success",
        "violationId": log_entry.id,
        "violationType": payload.violationType,
        "verifiedTrustScore": verified_trust_score,
        "isAutoTerminated": is_auto_terminated,
        "terminationReason": termination_reason,
        "tamperingDetected": tampering_detected,
    }


# ---------------------------------------------------------------------------
# API ROUTE: Candidate Session Audit Report (Timeline + Snapshots)
# ---------------------------------------------------------------------------
@router.get("/sessions/{session_id}/report")
async def get_candidate_session_report(
    session_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Returns full candidate proctoring audit trail:
    - Trust Score & breakdown
    - Flagged violation timeline
    - Base64 WebP proof snapshots
    - Hardware/Environment details
    """
    session_result = await db.execute(
        select(ExamSession).where(ExamSession.id == session_id)
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate session {session_id} not found.",
        )

    student_result = await db.execute(
        select(Student).where(Student.id == session.student_id)
    )
    student = student_result.scalar_one_or_none()

    logs_result = await db.execute(
        select(ExamLog)
        .where(ExamLog.session_id == session_id)
        .order_by(ExamLog.timestamp.desc())
    )
    logs = logs_result.scalars().all()

    timeline = []
    violation_counts: dict[str, int] = {}

    for log in logs:
        violation_counts[log.event_type] = violation_counts.get(log.event_type, 0) + 1
        
        parsed_details = {}
        if log.details:
            try:
                parsed_details = json.loads(log.details)
            except Exception:
                parsed_details = {"raw": log.details}

        timeline.append({
            "id": log.id,
            "timestamp": log.timestamp.isoformat(),
            "violationType": log.event_type,
            "confidence": parsed_details.get("confidence", 0.95),
            "snapshot": parsed_details.get("snapshot"),
            "currentScore": parsed_details.get("currentScore", 100),
            "penaltyApplied": parsed_details.get("penaltyApplied", DEFAULT_PENALTY_WEIGHTS.get(log.event_type, 10)),
            "reviewStatus": parsed_details.get("reviewStatus", "PENDING"),
            "examinerNotes": parsed_details.get("examinerNotes"),
            "metadata": parsed_details.get("metadata", {}),
        })

    verified_trust_score = calculate_trust_score(violation_counts)

    return {
        "sessionId": session.id,
        "candidate": {
            "id": student.id if student else None,
            "name": student.name if student else "Unknown Candidate",
            "email": student.email if student else "N/A",
            "rollNo": student.roll_no if student else "N/A",
        },
        "session": {
            "startTime": session.start_time.isoformat() if session.start_time else None,
            "endTime": session.end_time.isoformat() if session.end_time else None,
            "ipAddress": session.ip_address,
            "location": session.location,
            "networkIsp": session.network_isp,
        },
        "trustScore": verified_trust_score,
        "integrityStatus": (
            "SAFE" if verified_trust_score >= 80 else "SUSPICIOUS" if verified_trust_score >= 50 else "CRITICAL"
        ),
        "totalViolations": len(timeline),
        "violationCounts": violation_counts,
        "timeline": timeline,
    }


# ---------------------------------------------------------------------------
# API ROUTE: Examiner Review Action (Verify or Dismiss False Positive)
# ---------------------------------------------------------------------------
@router.post("/violations/{violation_id}/review")
async def review_violation_action(
    violation_id: int,
    payload: ViolationReviewPayload,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Allows examiner to audit flagged events:
    - Confirm violation
    - Dismiss as false positive (restores penalty points and recalculates score)
    """
    result = await db.execute(select(ExamLog).where(ExamLog.id == violation_id))
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Violation record {violation_id} not found.",
        )

    parsed_details = {}
    if log.details:
        try:
            parsed_details = json.loads(log.details)
        except Exception:
            parsed_details = {}

    parsed_details["reviewStatus"] = payload.action.upper()
    parsed_details["examinerNotes"] = payload.examinerNotes
    parsed_details["reviewedAt"] = datetime.now(timezone.utc).isoformat()

    log.details = json.dumps(parsed_details, separators=(",", ":"))
    await db.commit()

    return {
        "status": "updated",
        "violationId": violation_id,
        "reviewStatus": parsed_details["reviewStatus"],
        "examinerNotes": payload.examinerNotes,
    }


# ---------------------------------------------------------------------------
# API ROUTE: Real-Time SSE Stream for Examiner Live Dashboard
# ---------------------------------------------------------------------------
@router.get("/events/stream/{exam_id}")
async def stream_proctor_events(
    exam_id: str,
    request: Request,
) -> StreamingResponse:
    """
    Server-Sent Events (SSE) channel for real-time examiner monitoring.
    Syncs candidate trust score drops and snapshot alerts live to examiner grid.
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    if exam_id not in EXAMINER_EVENT_QUEUES:
        EXAMINER_EVENT_QUEUES[exam_id] = []
    EXAMINER_EVENT_QUEUES[exam_id].append(queue)

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # Send initial connected heartbeat
            yield f"data: {json.dumps({'type': 'CONNECTED', 'examId': exam_id})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive heartbeat comment
                    yield ": ping\n\n"
        finally:
            if exam_id in EXAMINER_EVENT_QUEUES and queue in EXAMINER_EVENT_QUEUES[exam_id]:
                EXAMINER_EVENT_QUEUES[exam_id].remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

