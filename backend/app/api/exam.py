import io
import json
import logging
import os
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response as FastApiResponse
from fastapi.concurrency import run_in_threadpool
import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import require_admin, require_student
from app.db.models import ExamLog, ExamSession, Question, Response, Student
from app.db.session import get_db
from app.schemas.exam import (
    AnswerSubmit,
    BulkQuestionImportResult,
    GenerateAiMcqsRequest,
    PublishCoachingExamRequest,
    PublishCoachingExamResponse,
    QuestionAdminOut,
    QuestionCreate,
    QuestionOut,
    ResponseOut,
)
from app.services.question_shuffler import generate_student_paper

router = APIRouter(prefix="/exam", tags=["exam"])
logger = logging.getLogger(__name__)


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
    subject: dict[str, object] = Depends(require_student),
) -> list[QuestionOut]:
    result = await db.execute(select(Question).order_by(Question.id))
    questions = result.scalars().all()
    student_id = int(subject.get("student_id", 1))

    # Deterministic shuffling per student
    shuffled = generate_student_paper(questions, student_seed=student_id)
    return [
        QuestionOut(
            id=item["id"],
            question=item["question"],
            options=item["options"],
        )
        for item in shuffled
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


@router.get("/admin/questions", response_model=list[QuestionAdminOut])
async def list_admin_questions(
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
) -> list[QuestionAdminOut]:
    result = await db.execute(select(Question).order_by(Question.id))
    questions = result.scalars().all()
    return [
        QuestionAdminOut(
            id=q.id,
            question=q.question_text,
            option_a=q.option_a,
            option_b=q.option_b,
            option_c=q.option_c,
            option_d=q.option_d,
            correct_option=q.correct_option,
        )
        for q in questions
    ]


@router.post("/admin/questions", response_model=QuestionAdminOut, status_code=status.HTTP_201_CREATED)
async def create_admin_question(
    payload: QuestionCreate,
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
) -> QuestionAdminOut:
    question = Question(
        question_text=payload.question_text,
        option_a=payload.option_a,
        option_b=payload.option_b,
        option_c=payload.option_c,
        option_d=payload.option_d,
        correct_option=payload.correct_option,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return QuestionAdminOut(
        id=question.id,
        question=question.question_text,
        option_a=question.option_a,
        option_b=question.option_b,
        option_c=question.option_c,
        option_d=question.option_d,
        correct_option=question.correct_option,
    )


@router.delete("/admin/questions/{question_id}")
async def delete_admin_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
) -> dict[str, str | int]:
    question = await db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    await db.delete(question)
    await db.commit()
    return {"status": "deleted", "question_id": question_id}


# ---------------------------------------------------------------------------
# BULK MCQ IMPORT & AUTOMATION SUITE
# ---------------------------------------------------------------------------

def _parse_sheet_to_questions(content: bytes, filename: str) -> tuple[list[dict], list[str]]:
    lower_fn = filename.lower()
    errors: list[str] = []
    try:
        if lower_fn.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        return [], [f"Failed to read file: {e}"]

    df = df.dropna(how="all")
    if df.empty:
        return [], ["The uploaded file is empty."]

    header_map: dict[str, str] = {}
    for col in df.columns:
        norm = re.sub(r"[\s\-_.\t/()]+", "_", str(col).strip().lower()).strip("_")
        if norm in {"question", "question_text", "question_statement", "problem", "q", "statement"}:
            header_map["question"] = col
        elif norm in {"option_a", "optiona", "opt_a", "opta", "a", "option_1", "choice_a"}:
            header_map["option_a"] = col
        elif norm in {"option_b", "optionb", "opt_b", "optb", "b", "option_2", "choice_b"}:
            header_map["option_b"] = col
        elif norm in {"option_c", "optionc", "opt_c", "optc", "c", "option_3", "choice_c"}:
            header_map["option_c"] = col
        elif norm in {"option_d", "optiond", "opt_d", "optd", "d", "option_4", "choice_d"}:
            header_map["option_d"] = col
        elif norm in {"correct_option", "correct_answer", "answer", "ans", "correct", "key", "right_answer"}:
            header_map["correct_option"] = col

    missing = [req for req in ["question", "option_a", "option_b", "option_c", "option_d", "correct_option"] if req not in header_map]
    if missing:
        return [], [f"Missing required columns: {', '.join(missing)}. Please download and use the provided template."]

    parsed: list[dict] = []
    for idx, row in df.iterrows():
        row_num = idx + 2
        q_val = row[header_map["question"]]
        q_text = str(q_val).strip() if pd.notna(q_val) else ""
        if not q_text:
            continue

        opt_a = str(row[header_map["option_a"]]).strip() if pd.notna(row[header_map["option_a"]]) else ""
        opt_b = str(row[header_map["option_b"]]).strip() if pd.notna(row[header_map["option_b"]]) else ""
        opt_c = str(row[header_map["option_c"]]).strip() if pd.notna(row[header_map["option_c"]]) else ""
        opt_d = str(row[header_map["option_d"]]).strip() if pd.notna(row[header_map["option_d"]]) else ""
        raw_ans = str(row[header_map["correct_option"]]).strip() if pd.notna(row[header_map["correct_option"]]) else ""

        if not (opt_a and opt_b and opt_c and opt_d):
            errors.append(f"Row {row_num}: Options A, B, C, and D are all required.")
            continue

        ans_upper = raw_ans.upper()
        correct: str | None = None
        if ans_upper in {"A", "B", "C", "D"}:
            correct = ans_upper
        elif ans_upper in {"1", "OPT 1", "OPTION 1", "OPTION A"}:
            correct = "A"
        elif ans_upper in {"2", "OPT 2", "OPTION 2", "OPTION B"}:
            correct = "B"
        elif ans_upper in {"3", "OPT 3", "OPTION 3", "OPTION C"}:
            correct = "C"
        elif ans_upper in {"4", "OPT 4", "OPTION 4", "OPTION D"}:
            correct = "D"
        else:
            raw_clean = raw_ans.lower()
            if raw_clean == opt_a.lower():
                correct = "A"
            elif raw_clean == opt_b.lower():
                correct = "B"
            elif raw_clean == opt_c.lower():
                correct = "C"
            elif raw_clean == opt_d.lower():
                correct = "D"
            else:
                errors.append(f"Row {row_num}: Answer '{raw_ans}' does not match A, B, C, D or any option text.")
                continue

        parsed.append({
            "question_text": q_text,
            "option_a": opt_a,
            "option_b": opt_b,
            "option_c": opt_c,
            "option_d": opt_d,
            "correct_option": correct,
        })

    return parsed, errors


@router.post("/admin/questions/upload-sheet", response_model=BulkQuestionImportResult)
async def upload_questions_sheet(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
) -> BulkQuestionImportResult:
    """Imports objective MCQs in bulk from Excel (.xlsx, .xls) or CSV spreadsheet."""
    filename = file.filename or ""
    if not (filename.lower().endswith(".xlsx") or filename.lower().endswith(".xls") or filename.lower().endswith(".csv")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an Excel spreadsheet (.xlsx, .xls) or CSV (.csv).",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    parsed_rows, errors = await run_in_threadpool(_parse_sheet_to_questions, content, filename)

    if not parsed_rows and errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Could not parse questions", "errors": errors},
        )

    new_questions = [
        Question(
            question_text=r["question_text"],
            option_a=r["option_a"],
            option_b=r["option_b"],
            option_c=r["option_c"],
            option_d=r["option_d"],
            correct_option=r["correct_option"],
        )
        for r in parsed_rows
    ]

    db.add_all(new_questions)
    await db.commit()

    return BulkQuestionImportResult(
        status="success",
        imported_count=len(new_questions),
        skipped_count=len(errors),
        errors=errors[:20],
    )


@router.post("/admin/questions/bulk", response_model=BulkQuestionImportResult)
async def create_bulk_questions(
    payload: list[QuestionCreate],
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
) -> BulkQuestionImportResult:
    """Inserts a list of parsed questions into the database in a single transaction."""
    if not payload:
        raise HTTPException(status_code=400, detail="Question list cannot be empty.")

    new_questions = [
        Question(
            question_text=p.question_text,
            option_a=p.option_a,
            option_b=p.option_b,
            option_c=p.option_c,
            option_d=p.option_d,
            correct_option=p.correct_option,
        )
        for p in payload
    ]

    db.add_all(new_questions)
    await db.commit()

    return BulkQuestionImportResult(
        status="success",
        imported_count=len(new_questions),
        skipped_count=0,
    )


@router.get("/admin/questions/sample-template")
async def download_question_template(
    format: str = Query("xlsx"),
    _admin: dict[str, object] = Depends(require_admin),
):
    """Generates a downloadable Excel or CSV question template."""
    sample_data = [
        {
            "Question": "Which data structure follows the LIFO (Last-In-First-Out) principle?",
            "Option A": "Queue",
            "Option B": "Stack",
            "Option C": "Array",
            "Option D": "Linked List",
            "Correct Answer": "B",
        },
        {
            "Question": "What is the average time complexity of searching in a Binary Search Tree?",
            "Option A": "O(1)",
            "Option B": "O(n)",
            "Option C": "O(log n)",
            "Option D": "O(n^2)",
            "Correct Answer": "C",
        },
        {
            "Question": "Which protocol is used for secure communication over the web?",
            "Option A": "HTTP",
            "Option B": "FTP",
            "Option C": "HTTPS",
            "Option D": "SMTP",
            "Correct Answer": "C",
        },
        {
            "Question": "Which SQL keyword is used to sort the result-set in descending order?",
            "Option A": "SORT DESC",
            "Option B": "ORDER BY ... DESC",
            "Option C": "GROUP BY DESC",
            "Option D": "ALIGN DESC",
            "Correct Answer": "B",
        },
        {
            "Question": "Which of the following is volatile primary memory in a computer?",
            "Option A": "ROM",
            "Option B": "Hard Disk Drive",
            "Option C": "RAM",
            "Option D": "SSD",
            "Correct Answer": "C",
        },
    ]

    df = pd.DataFrame(sample_data)

    if format.lower() == "csv":
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        return FastApiResponse(
            content=csv_buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="mcq_questions_template.csv"'},
        )
    else:
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="MCQs")
        return FastApiResponse(
            content=out.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="mcq_questions_template.xlsx"'},
        )


@router.post("/admin/questions/generate-ai-mcqs")
async def generate_ai_mcqs(
    payload: GenerateAiMcqsRequest,
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
) -> dict:
    """Generates objective MCQs using Gemini AI (with intelligent fallback)."""
    settings = get_settings()
    api_key = getattr(settings, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
    questions_list: list[dict] = []

    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt = (
                f"Generate exactly {payload.count} multiple choice questions (MCQs) for the topic '{payload.topic}' with difficulty '{payload.difficulty}'.\n"
                "Return ONLY a raw JSON array of objects with keys:\n"
                '  "question_text": "question statement",\n'
                '  "option_a": "choice A",\n'
                '  "option_b": "choice B",\n'
                '  "option_c": "choice C",\n'
                '  "option_d": "choice D",\n'
                '  "correct_option": "A", "B", "C", or "D"\n'
                "No markdown, no backticks, only JSON array."
            )
            response = client.models.generate_content(
                model=getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash"),
                contents=prompt,
            )
            raw = response.text or ""
            raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
            raw = re.sub(r"\s*```$", "", raw.strip()).strip()
            loaded = json.loads(raw)
            if isinstance(loaded, list):
                for item in loaded:
                    if "question_text" in item and "option_a" in item and "correct_option" in item:
                        correct = str(item["correct_option"]).strip().upper()
                        if correct in {"A", "B", "C", "D"}:
                            questions_list.append({
                                "question_text": str(item["question_text"]).strip(),
                                "option_a": str(item["option_a"]).strip(),
                                "option_b": str(item["option_b"]).strip(),
                                "option_c": str(item["option_c"]).strip(),
                                "option_d": str(item["option_d"]).strip(),
                                "correct_option": correct,
                            })
        except Exception as e:
            logger.warning(f"Gemini MCQ generation failed: {e}. Falling back to domain generator.")

    # Fallback algorithmic / domain generator if AI key not configured or failed
    if not questions_list:
        topic_lower = payload.topic.lower()
        templates = [
            ("Which concept in {topic} is primarily used to optimize time performance?", "Caching / Memoization", "Infinite Recursion", "Linear Searching", "Random Delay", "A"),
            ("What is a core advantage of using {topic} in enterprise systems?", "Modularity and maintainability", "Guaranteed zero memory usage", "Elimination of all errors", "Automatic hardware acceleration", "A"),
            ("Which of the following is considered an anti-pattern when designing {topic}?", "Tight coupling of components", "High cohesion", "Graceful exception handling", "Comprehensive logging", "A"),
            ("What is the standard time complexity for searching optimal paths in {topic}?", "O(log n)", "O(n^3)", "O(2^n)", "O(1)", "A"),
            ("Which fundamental protocol or rule governs communication in {topic}?", "Encapsulation & Abstraction", "Uncontrolled Mutation", "Hardcoded Dependencies", "Global Shared State", "A"),
            ("How does asynchronous execution benefit applications working with {topic}?", "Prevents blocking the main thread", "Slows down CPU clock", "Bypasses all security firewalls", "Replaces memory with disk", "A"),
            ("In {topic}, what does idempotency mean?", "An operation can be applied multiple times without changing the result", "An operation runs in O(1) time always", "An operation only works on integers", "An operation cannot be reversed", "A"),
            ("Which testing technique is most effective for validating corner cases in {topic}?", "Boundary Value Analysis", "Manual guessing", "Skipping assertion checks", "Running code once", "A"),
        ]

        import random
        selected_templates = templates[:payload.count]
        for idx, (tmpl, opt1, opt2, opt3, opt4, correct) in enumerate(selected_templates):
            q_text = tmpl.format(topic=payload.topic.title())
            # Shuffle options deterministically
            opts = [opt1, opt2, opt3, opt4]
            random.seed(hash(payload.topic) + idx)
            random.shuffle(opts)
            correct_letter = ["A", "B", "C", "D"][opts.index(opt1)]
            questions_list.append({
                "question_text": q_text,
                "option_a": opts[0],
                "option_b": opts[1],
                "option_c": opts[2],
                "option_d": opts[3],
                "correct_option": correct_letter,
            })

    if payload.save_immediately and questions_list:
        db_items = [
            Question(
                question_text=q["question_text"],
                option_a=q["option_a"],
                option_b=q["option_b"],
                option_c=q["option_c"],
                option_d=q["option_d"],
                correct_option=q["correct_option"],
            )
            for q in questions_list
        ]
        db.add_all(db_items)
        await db.commit()

    return {
        "status": "success",
        "topic": payload.topic,
        "count": len(questions_list),
        "saved_to_db": payload.save_immediately,
        "questions": questions_list,
    }


@router.delete("/admin/questions/all")
async def delete_all_admin_questions(
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
) -> dict[str, str]:
    """Deletes all MCQ questions from the database."""
    await db.execute(delete(Question))
    await db.commit()
    return {"status": "cleared", "message": "All objective questions have been deleted."}


# ---------------------------------------------------------------------------
# COACHING PUBLISH & BRANDED SHAREABLE LINKS
# ---------------------------------------------------------------------------
published_coaching_exams: dict[str, dict] = {}


def _slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s or "exam"


@router.post("/admin/publish-coaching-exam", response_model=PublishCoachingExamResponse)
async def publish_coaching_exam(
    payload: PublishCoachingExamRequest,
    _admin: dict[str, object] = Depends(require_admin),
) -> PublishCoachingExamResponse:
    """Publishes the current objective MCQ test for a specific coaching/institute and creates a shareable link."""
    import secrets
    import urllib.parse
    settings = get_settings()
    base_url = getattr(settings, "FRONTEND_URL", "https://examguard-ai.vercel.app").rstrip("/")

    coaching_slug = _slugify(payload.coaching_name)
    exam_slug = _slugify(payload.exam_title)
    unique_suffix = secrets.token_hex(3)
    slug = f"{coaching_slug}-{exam_slug}-{unique_suffix}"

    exam_data = {
        "slug": slug,
        "coaching_name": payload.coaching_name.strip(),
        "exam_title": payload.exam_title.strip(),
        "duration_minutes": payload.duration_minutes,
        "instructions": payload.instructions or "Please keep your camera enabled and avoid switching tabs.",
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    published_coaching_exams[slug] = exam_data

    query_params = urllib.parse.urlencode({
        "coaching": payload.coaching_name.strip(),
        "exam": payload.exam_title.strip(),
        "duration": payload.duration_minutes,
        "exam_id": slug,
    })
    shareable_url = f"{base_url}/src/pages/mcq-exam.html?{query_params}"

    whatsapp_text = (
        f"📝 *Online Proctored Exam Announcement*\n"
        f"🏛️ *Institute:* {payload.coaching_name.strip()}\n"
        f"📚 *Exam:* {payload.exam_title.strip()}\n"
        f"⏱️ *Duration:* {payload.duration_minutes} Minutes\n"
        f"📱 *Device:* 100% Mobile & PC Friendly\n\n"
        f"👉 *Start Exam Here:* {shareable_url}\n\n"
        f"⚠️ *Instructions:* Open link, enter your Name & Roll Number to start. Screen lockdown and dynamic identity watermark are active."
    )
    whatsapp_share_url = f"https://api.whatsapp.com/send?text={urllib.parse.quote(whatsapp_text)}"

    return PublishCoachingExamResponse(
        status="published",
        slug=slug,
        coaching_name=payload.coaching_name.strip(),
        exam_title=payload.exam_title.strip(),
        duration_minutes=payload.duration_minutes,
        shareable_url=shareable_url,
        whatsapp_share_url=whatsapp_share_url,
    )


@router.get("/coaching-exam/{slug}")
async def get_published_coaching_exam(slug: str):
    """Retrieves published coaching exam metadata by slug."""
    data = published_coaching_exams.get(slug)
    if not data:
        raise HTTPException(status_code=404, detail="Coaching exam link not found or expired.")
    return data


@router.get("/admin/coaching-submissions")
async def list_coaching_submissions(
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
):
    """Lists all candidate submissions for objective/coaching assessments with their score and status."""
    students = (await db.execute(select(Student).order_by(Student.id.desc()))).scalars().all()
    questions = (await db.execute(select(Question))).scalars().all()
    q_map = {q.id: q.correct_option for q in questions}
    total_questions = len(questions)

    records = []
    for s in students:
        session_res = await db.execute(
            select(ExamSession).where(ExamSession.student_id == s.id).order_by(ExamSession.start_time.desc())
        )
        session = session_res.scalars().first()

        resp_res = await db.execute(
            select(Response).where(Response.student_id == s.id)
        )
        responses = resp_res.scalars().all()
        answered = len(responses)
        correct = sum(1 for r in responses if q_map.get(r.question_id) == r.selected_option)

        phone_count_res = await db.execute(
            select(func.count(ExamLog.id)).where(
                ExamLog.student_id == s.id,
                ExamLog.event_type.in_(["MOBILE_PHONE_DETECTED", "MOBILE_DEVICE_DETECTED", "SECONDARY_PHONE_CHEATING"])
            )
        )
        phone_count = phone_count_res.scalar() or 0

        is_completed = (session is not None and session.end_time is not None) or answered > 0
        started_at = (
            session.start_time.isoformat()
            if session and session.start_time
            else (s.created_at.isoformat() if s.created_at else None)
        )
        submitted_at = session.end_time.isoformat() if session and session.end_time else None

        records.append({
            "student_id": s.id,
            "name": s.name,
            "roll_no": s.roll_no or "N/A",
            "email": s.email,
            "coaching_name": (session.location if session and session.location else "Direct Online Portal"),
            "total_questions": total_questions,
            "answered_count": answered,
            "correct_count": correct,
            "score_percentage": round((correct / total_questions * 100), 1) if total_questions > 0 else 0,
            "status": "Completed" if is_completed else "In Progress",
            "phone_violations": phone_count,
            "started_at": started_at,
            "submitted_at": submitted_at,
        })

    return records


@router.get("/admin/export-coaching-results")
async def export_coaching_results(
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
):
    """Exports all candidate results as an in-memory, highly reliable Excel report."""
    students = (await db.execute(select(Student).order_by(Student.id.desc()))).scalars().all()
    questions = (await db.execute(select(Question))).scalars().all()
    q_map = {q.id: q.correct_option for q in questions}
    total_questions = len(questions)

    records = []
    for s in students:
        session_res = await db.execute(
            select(ExamSession).where(ExamSession.student_id == s.id).order_by(ExamSession.start_time.desc())
        )
        session = session_res.scalars().first()

        resp_res = await db.execute(
            select(Response).where(Response.student_id == s.id)
        )
        responses = resp_res.scalars().all()
        answered = len(responses)
        correct = sum(1 for r in responses if q_map.get(r.question_id) == r.selected_option)

        phone_count_res = await db.execute(
            select(func.count(ExamLog.id)).where(
                ExamLog.student_id == s.id,
                ExamLog.event_type.in_(["MOBILE_PHONE_DETECTED", "MOBILE_DEVICE_DETECTED", "SECONDARY_PHONE_CHEATING"])
            )
        )
        phone_count = phone_count_res.scalar() or 0

        is_completed = (session is not None and session.end_time is not None) or answered > 0
        started_at = (
            session.start_time.strftime("%Y-%m-%d %H:%M:%S")
            if session and session.start_time
            else (s.created_at.strftime("%Y-%m-%d %H:%M:%S") if s.created_at else "")
        )
        submitted_at = (
            session.end_time.strftime("%Y-%m-%d %H:%M:%S")
            if session and session.end_time
            else (started_at if is_completed else "")
        )

        records.append({
            "Roll Number": s.roll_no or "N/A",
            "Student Name": s.name,
            "Email / Contact": s.email,
            "Coaching / Batch": session.location if session and session.location else "Coaching Portal",
            "Total Questions": total_questions,
            "Questions Answered": answered,
            "Correct Answers (Score)": correct,
            "Score Percentage (%)": round((correct / total_questions * 100), 1) if total_questions > 0 else 0,
            "Exam Status": "Completed" if is_completed else "In Progress",
            "Secondary Mobile Phone Detected": f"YES ({phone_count} alerts)" if phone_count > 0 else "NO (Clean)",
            "Exam Start Time": started_at,
            "Exam Submission Time": submitted_at,
        })

    df = pd.DataFrame(records)
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Candidate Results")
    out.seek(0)

    filename = f"ExamGuard_Candidate_Results_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.xlsx"
    return FastApiResponse(
        content=out.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )





