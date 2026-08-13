from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.geofence import get_client_ip
from app.core.security import create_access_token, verify_secret
from app.db.models import ExamSession, Student
from app.db.session import get_db
from app.schemas.student import AdminLogin, InviteTokenVerify, StudentLogin, TokenResponse
from app.services.invite_service import hash_invite_token

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def _verify_student_pin(
    payload: StudentLogin,
    request: Request,
    db: AsyncSession,
) -> TokenResponse:
    result = await db.execute(
        select(Student)
        .where(Student.roll_no == payload.roll_no)
        .with_for_update()
    )
    student = result.scalar_one_or_none()

    if not student or not student.secret_pin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid roll number or PIN.",
        )

    if student.is_pin_used:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This PIN has already been used.",
        )

    if not verify_secret(payload.pin, student.secret_pin):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid roll number or PIN.",
        )

    client_ip = get_client_ip(request)
    student.is_pin_used = True
    session = ExamSession(
        student_id=student.id,
        ip_address=client_ip,
        location=None,
        network_isp=None,
    )
    db.add(session)
    await db.flush()
    await db.commit()

    token = create_access_token(
        {
            "sub": student.roll_no,
            "role": "student",
            "student_id": student.id,
            "roll_no": student.roll_no,
            "session_id": session.id,
        }
    )
    return TokenResponse(
        access_token=token,
        role="student",
        student_id=student.id,
        session_id=session.id,
        roll_no=student.roll_no,
    )


@router.post("/student-login", response_model=TokenResponse)
async def student_login(
    payload: StudentLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    return await _verify_student_pin(payload, request, db)


@router.post("/admin-login", response_model=TokenResponse)
async def admin_login(payload: AdminLogin) -> TokenResponse:
    if (
        payload.username != settings.ADMIN_USERNAME
        or payload.password != settings.ADMIN_PASSWORD
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials.",
        )

    token = create_access_token({"sub": payload.username, "role": "admin"})
    return TokenResponse(access_token=token, role="admin")


@router.post("/verify-pin", response_model=TokenResponse)
async def verify_pin(
    payload: StudentLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    return await _verify_student_pin(payload, request, db)


@router.post("/verify-invite", response_model=TokenResponse)
async def verify_invite(
    payload: InviteTokenVerify,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    token_hash = hash_invite_token(payload.token.strip())
    result = await db.execute(
        select(Student)
        .where(Student.invite_token_hash == token_hash)
        .with_for_update()
    )
    student = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if not student or not student.invite_token_expires_at:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid exam invitation link.",
        )

    if student.invite_accepted_at:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This exam invitation link has already been used.",
        )

    expires_at = _as_aware_utc(student.invite_token_expires_at)
    if expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This exam invitation link has expired.",
        )

    if not student.secret_pin:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ask your admin to generate your exam PIN before starting.",
        )

    if student.is_pin_used:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This PIN has already been used.",
        )

    if not verify_secret(payload.pin, student.secret_pin):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid exam invitation link or PIN.",
        )

    client_ip = get_client_ip(request)
    student.invite_accepted_at = now
    student.invite_token_hash = None
    student.is_invite_used = True
    student.is_pin_used = True
    session = ExamSession(
        student_id=student.id,
        ip_address=client_ip,
        location=None,
        network_isp=None,
    )
    db.add(session)
    await db.flush()
    await db.commit()

    token = create_access_token(
        {
            "sub": student.roll_no,
            "role": "student",
            "student_id": student.id,
            "roll_no": student.roll_no,
            "session_id": session.id,
        }
    )
    return TokenResponse(
        access_token=token,
        role="student",
        student_id=student.id,
        session_id=session.id,
        roll_no=student.roll_no,
    )
