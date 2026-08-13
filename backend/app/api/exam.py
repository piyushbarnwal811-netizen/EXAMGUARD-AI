from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_student
from app.db.models import ExamLog, ExamSession, Question, Response
from app.db.session import get_db
from app.schemas.exam import AnswerSubmit, QuestionOut, ResponseOut

router = APIRouter(prefix="/exam", tags=["exam"])


async def _latest_session(
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


@router.get("/questions", response_model=list[QuestionOut])
async def get_questions(
    db: AsyncSession = Depends(get_db),
    _subject: dict[str, object] = Depends(require_student),
) -> list[QuestionOut]:
    result = await db.execute(select(Question).order_by(Question.id))
    questions = result.scalars().all()
    return [
        QuestionOut(
            id=question.id,
            question=question.question_text,
            options=[
                question.option_a,
                question.option_b,
                question.option_c,
                question.option_d,
            ],
        )
        for question in questions
    ]


@router.post("/answers", response_model=ResponseOut)
async def submit_answer(
    payload: AnswerSubmit,
    db: AsyncSession = Depends(get_db),
    subject: dict[str, object] = Depends(require_student),
) -> ResponseOut:
    student_id = int(subject["student_id"])
    question = await db.get(Question, payload.question_id)
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found.",
        )

    submitted_at = datetime.now(timezone.utc)
    result = await db.execute(
        select(Response).where(
            Response.student_id == student_id,
            Response.question_id == payload.question_id,
        )
    )
    response = result.scalar_one_or_none()

    if response:
        response.selected_option = payload.selected_option
        response.timestamp = submitted_at
    else:
        response = Response(
            student_id=student_id,
            question_id=payload.question_id,
            selected_option=payload.selected_option,
            timestamp=submitted_at,
        )
        db.add(response)

    await db.commit()
    return ResponseOut(
        question_id=payload.question_id,
        selected_option=payload.selected_option,
        submitted_at=submitted_at,
        saved=True,
    )


@router.post("/timestamp")
async def save_timestamp(
    event: str,
    db: AsyncSession = Depends(get_db),
    subject: dict[str, object] = Depends(require_student),
) -> dict[str, str]:
    student_id = int(subject["student_id"])
    timestamp = datetime.now(timezone.utc)
    normalized_event = event.strip().upper().replace("-", "_").replace(" ", "_")
    session = await _latest_session(db, student_id, subject)

    if normalized_event in {"END", "EXAM_END", "SUBMIT"}:
        if session:
            session.end_time = timestamp

    db.add(
        ExamLog(
            student_id=student_id,
            session_id=session.id if session else None,
            event_type=normalized_event,
            timestamp=timestamp,
            details=(
                f'{{"source":"exam_timestamp","session_id":'
                f'{session.id if session else "null"}}}'
            ),
        )
    )
    await db.commit()
    return {"event": normalized_event, "timestamp": timestamp.isoformat()}
