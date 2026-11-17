from datetime import datetime, timezone
import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.geofence import get_client_ip
from app.core.security import create_access_token, verify_secret
from app.db.models import ExamSession, Institute, Student
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


def _verify_admin_password(plain_password: str, stored_password: str) -> bool:
    if not stored_password:
        return False
    if stored_password.startswith("$2b$") or stored_password.startswith("$2a$"):
        return verify_secret(plain_password, stored_password)
    return hmac.compare_digest(plain_password.strip(), stored_password.strip())


@router.post("/admin-login", response_model=TokenResponse)
async def admin_login(
    payload: AdminLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    login_id = payload.identifier.strip().lower()
    if not login_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email is required.",
        )

    clean_admin = settings.ADMIN_USERNAME.strip().lower()
    master_identifiers = {clean_admin, "piyushbarnwal811@gmail.com"}

    # 1. Check Master Super-Admin credentials from settings / env
    if (
        login_id in master_identifiers
        and _verify_admin_password(payload.password, settings.ADMIN_PASSWORD)
    ):
        token = create_access_token({
            "sub": "piyushbarnwal811@gmail.com",
            "role": "admin",
            "is_super_admin": True,
            "institute_name": "Master Administration",
        })
        return TokenResponse(
            access_token=token,
            role="admin",
            is_super_admin=True,
            institute_name="Master Administration",
        )

    # 2. Check Institute / Coaching Admin credentials from Database
    result = await db.execute(
        select(Institute).where(
            or_(
                func.lower(Institute.username) == login_id,
                func.lower(Institute.email) == login_id,
            )
        )
    )
    institute = result.scalar_one_or_none()

    if institute:
        if not institute.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Aapka coaching account inactive kar diya gaya hai. Kripya master admin se contact karein.",
            )
        if verify_secret(payload.password, institute.password_hash):
            is_super = (
                institute.code == "SUPER-ADMIN"
                or (institute.email and institute.email.lower() == "piyushbarnwal811@gmail.com")
                or institute.username.lower() == "piyushbarnwal811@gmail.com"
            )
            role = "admin" if is_super else "coaching_admin"
            token = create_access_token({
                "sub": institute.username,
                "role": role,
                "is_super_admin": is_super,
                "institute_id": institute.id,
                "institute_name": "Master Administration" if is_super else institute.name,
                "allowed_exams": ["*"] if is_super else [institute.name],
            })
            return TokenResponse(
                access_token=token,
                role=role,
                is_super_admin=is_super,
                institute_name="Master Administration" if is_super else institute.name,
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid admin credentials. Username ya password galat hai.",
    )


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

    if payload.pin:
        if not student.secret_pin:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This invitation does not have a PIN configured.",
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

    claim_result = await db.execute(
        update(Student)
        .where(
            Student.id == student.id,
            Student.invite_token_hash == token_hash,
            Student.invite_accepted_at.is_(None),
            Student.invite_token_expires_at >= now,
        )
        .values(
            invite_accepted_at=now,
            is_invite_used=True,
            is_pin_used=True,
        )
        .execution_options(synchronize_session=False)
    )
    if claim_result.rowcount != 1:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This exam invitation link has already been used.",
        )

    client_ip = get_client_ip(request)
    student.invite_accepted_at = now
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


class CoachingCandidateOnboard(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    roll_no: str = Field(..., min_length=1, max_length=50)
    contact: str | None = None
    coaching_name: str = Field(..., min_length=1, max_length=200)
    exam_id: str | None = None


@router.post("/coaching-candidate-onboard", response_model=TokenResponse)
async def coaching_candidate_onboard(
    payload: CoachingCandidateOnboard,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    roll_no = payload.roll_no.strip().upper()
    name = payload.name.strip()
    if not name or len(name) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student name must be at least 2 characters long.",
        )
    if not roll_no:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid roll number is required.",
        )

    contact = (payload.contact or "").strip()
    email = contact if "@" in contact else f"{roll_no.lower()}@student.examguard.ai"

    result = await db.execute(select(Student).where(Student.roll_no == roll_no))
    student = result.scalar_one_or_none()

    if not student:
        # Guard against duplicate emails across two different roll numbers
        email_conflict = (
            await db.execute(select(Student.id).where(Student.email == email))
        ).scalar_one_or_none()
        safe_email = (
            f"{roll_no.lower()}@student.examguard.ai" if email_conflict else email
        )
        if safe_email != email:
            fallback_conflict = (
                await db.execute(select(Student.id).where(Student.email == safe_email))
            ).scalar_one_or_none()
            if fallback_conflict:
                safe_email = f"{roll_no.lower()}.{int(datetime.now(timezone.utc).timestamp())}@student.examguard.ai"

        student = Student(
            name=name,
            roll_no=roll_no,
            email=safe_email,
            is_pin_used=True,
            is_invite_used=True,
        )
        db.add(student)
        try:
            await db.flush()
        except IntegrityError:
            # Concurrent race condition: another onboarding created this roll_no simultaneously
            await db.rollback()
            student = (await db.execute(select(Student).where(Student.roll_no == roll_no))).scalar_one()
    else:
        student.name = name

    # Prevent duplicate attempts: check if candidate already completed and submitted this examination
    completed_session = (
        await db.execute(
            select(ExamSession)
            .where(
                ExamSession.student_id == student.id,
                ExamSession.end_time.is_not(None),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if completed_session:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Aapka exam pehle hi submit ho chuka hai. Duplicate attempts allowed nahi hain (Exam already completed).",
        )

    client_ip = get_client_ip(request)

    # Session reuse: if candidate has an existing active session (not submitted), reuse it
    active_session = (
        await db.execute(
            select(ExamSession)
            .where(
                ExamSession.student_id == student.id,
                ExamSession.end_time.is_(None),
            )
            .order_by(ExamSession.start_time.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if active_session:
        session = active_session
        session.ip_address = client_ip
        session.location = payload.coaching_name.strip()
    else:
        session = ExamSession(
            student_id=student.id,
            ip_address=client_ip,
            location=payload.coaching_name.strip(),
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
            "candidate_name": student.name,
            "coaching_name": payload.coaching_name.strip(),
        }
    )
    return TokenResponse(
        access_token=token,
        role="student",
        student_id=student.id,
        session_id=session.id,
        roll_no=student.roll_no,
    )

