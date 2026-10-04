from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.security import require_admin, require_student
from app.db.models import (
    CodeDraft,
    CodeSubmission,
    CodingContest,
    CodingProblem,
    CodingTestCase,
    ExamLog,
    ExamSession,
)
from app.db.session import get_db
from app.schemas.coding import (
    CodeExecutionOut,
    CodeDebugOut,
    CodeDebugRequest,
    CodeDraftAutoSubmitRequest,
    CodeDraftOut,
    CodeDraftSaveRequest,
    CodeRunRequest,
    CodeSubmitRequest,
    CodingProblemAdminOut,
    CodingProblemSaveIn,
    CodingProblemOut,
    CodingProblemsUpdateIn,
    CodingProblemUpdateIn,
    CodingTestCaseAdminOut,
    ContestFinalResultOut,
    ContestGateOut,
    ContestScheduleIn,
    ContestScheduleOut,
    TestCaseResultOut,
    VisibleSampleOut,
)
from app.services.coding_executor import ExecutionCaseResult, execute_code_against_cases

router = APIRouter(prefix="/contest", tags=["coding contest"])
settings = get_settings()
logger = logging.getLogger(__name__)


def _generate_code_debug(
    api_key: str,
    model_name: str,
    timeout_seconds: int,
    language: str,
    source_code: str,
    error_logs: str,
) -> CodeDebugOut:
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name,
        system_instruction=(
            "You are a programming tutor. Analyze only the supplied compiler/runtime error. "
            "Return one JSON object with has_error, error_line, error_summary, "
            "detailed_explanation, and fix_hint. Never return corrected code or a full solution. "
            "Use a short Hindi-English mix when helpful. Set error_line to null if unknown."
        ),
    )
    response = model.generate_content(
        f"Language: {language}\nSource code:\n{source_code}\n\nError logs:\n{error_logs}",
        generation_config={
            "max_output_tokens": 900,
            "response_mime_type": "application/json",
        },
        request_options={"timeout": timeout_seconds},
    )
    raw_text = getattr(response, "text", "")
    if not raw_text:
        raise ValueError("Gemini returned an empty debugging response.")
    return CodeDebugOut.model_validate_json(raw_text)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _contest_status(
    contest: CodingContest | None,
    now: datetime,
) -> tuple[str, int]:
    if contest is None:
        return "LOCKED", 0

    start_time = _as_aware_utc(contest.start_time)
    end_time = _as_aware_utc(contest.end_time)
    if now < start_time:
        return "LOCKED", max(0, int((start_time - now).total_seconds()))
    if now < end_time:
        return "ACTIVE", max(0, int((end_time - now).total_seconds()))
    return "ENDED", 0


def _sorted_cases(problem: CodingProblem) -> list[CodingTestCase]:
    return sorted(problem.test_cases, key=lambda item: item.sort_order)


def _enabled_languages(problem: CodingProblem) -> list[str]:
    raw = (problem.enabled_languages or "python,cpp,java").strip()
    available = {"python", "cpp", "java"}
    parsed = [item.strip().lower() for item in raw.split(",") if item.strip()]
    return [language for language in parsed if language in available]


def _problem_out(problem: CodingProblem) -> CodingProblemOut:
    visible_samples = [
        VisibleSampleOut(
            case_number=test_case.sort_order,
            input_data=test_case.input_data,
            expected_output=test_case.expected_output,
        )
        for test_case in _sorted_cases(problem)
        if test_case.is_visible
    ]
    enabled = _enabled_languages(problem)
    starter_code = {}
    if "python" in enabled:
        starter_code["python"] = problem.starter_code_python
    if "cpp" in enabled:
        starter_code["cpp"] = problem.starter_code_cpp
    if "java" in enabled:
        starter_code["java"] = problem.starter_code_java

    return CodingProblemOut(
        id=problem.id,
        title=problem.title,
        statement=problem.statement,
        input_format=problem.input_format,
        output_format=problem.output_format,
        constraints=problem.constraints,
        enabled_languages=enabled,
        starter_code=starter_code,
        visible_samples=visible_samples,
    )


def _problem_admin_out(problem: CodingProblem) -> CodingProblemAdminOut:
    return CodingProblemAdminOut(
        id=problem.id,
        contest_id=problem.contest_id,
        order_index=problem.order_index,
        title=problem.title,
        statement=problem.statement,
        input_format=problem.input_format,
        output_format=problem.output_format,
        constraints=problem.constraints,
        enabled_languages=_enabled_languages(problem),
        starter_code_python=problem.starter_code_python,
        starter_code_cpp=problem.starter_code_cpp,
        starter_code_java=problem.starter_code_java,
        test_cases=[
            CodingTestCaseAdminOut(
                id=test_case.id,
                sort_order=test_case.sort_order,
                input_data=test_case.input_data,
                expected_output=test_case.expected_output,
                is_visible=test_case.is_visible,
            )
            for test_case in _sorted_cases(problem)
        ],
    )


def _case_result_out(
    result: ExecutionCaseResult,
    reveal_details: bool,
) -> TestCaseResultOut:
    return TestCaseResultOut(
        case_number=result.case_number,
        visibility="VISIBLE" if result.is_visible else "HIDDEN",
        status="PASSED" if result.passed else "FAILED",
        input_data=result.input_data if reveal_details else None,
        expected_output=result.expected_output if reveal_details else None,
        actual_output=result.actual_output if reveal_details else None,
        error_logs=result.error_logs if reveal_details else None,
    )


def _score(passed_cases: int, total_cases: int, max_score: int) -> float:
    if total_cases <= 0:
        return 0
    return round((passed_cases / total_cases) * max_score, 2)


async def _latest_contest(
    db: AsyncSession,
    include_unpublished: bool = False,
    for_update: bool = False,
) -> CodingContest | None:
    stmt = (
        select(CodingContest)
        .options(
            selectinload(CodingContest.problems).selectinload(CodingProblem.test_cases)
        )
        .order_by(CodingContest.id.desc())
        .limit(1)
    )
    if not include_unpublished:
        stmt = stmt.where(CodingContest.is_published.is_(True))
    if for_update:
        stmt = stmt.with_for_update()

    result = await db.execute(stmt)
    return result.scalars().first()


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

    result = await db.execute(
        select(ExamSession)
        .where(ExamSession.student_id == student_id)
        .order_by(ExamSession.start_time.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _problem_for_payload(
    db: AsyncSession,
    problem_id: int,
) -> CodingProblem:
    result = await db.execute(
        select(CodingProblem)
        .options(
            selectinload(CodingProblem.test_cases),
            selectinload(CodingProblem.contest),
        )
        .where(CodingProblem.id == problem_id)
    )
    problem = result.scalar_one_or_none()
    if problem is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coding problem not found.",
        )
    return problem


def _assert_active(contest: CodingContest) -> None:
    now = _now_utc()
    contest_state, _remaining = _contest_status(contest, now)
    if contest_state == "LOCKED":
        raise HTTPException(
            status_code=423,
            detail="Contest is locked until the scheduled start time.",
        )
    if contest_state == "ENDED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contest has ended.",
        )


def _assert_can_submit(contest: CodingContest, auto_submitted: bool) -> None:
    now = _now_utc()
    start_time = _as_aware_utc(contest.start_time)
    end_time = _as_aware_utc(contest.end_time)
    grace_deadline = end_time + timedelta(seconds=settings.AUTO_SUBMIT_GRACE_SECONDS)

    if now < start_time:
        raise HTTPException(
            status_code=423,
            detail="Contest is locked until the scheduled start time.",
        )
    if now < end_time:
        return
    if auto_submitted and now <= grace_deadline:
        return

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Contest has ended and the submission window is closed.",
    )


def _validate_cases(test_cases: list[CodingTestCase], require_full_set: bool) -> None:
    visible_count = sum(1 for test_case in test_cases if test_case.is_visible)
    if visible_count != 2:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Coding problem must have exactly 2 visible sample test cases.",
        )
    if require_full_set and len(test_cases) != 10:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Coding problem must have exactly 10 total test cases.",
        )


def _starter_for_language(problem: CodingProblem, language: str) -> str:
    return {
        "python": problem.starter_code_python,
        "cpp": problem.starter_code_cpp,
        "java": problem.starter_code_java,
    }.get(language, "")


def _stored_case_results(raw_results: str) -> list[TestCaseResultOut]:
    try:
        loaded = json.loads(raw_results)
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return [TestCaseResultOut(**item) for item in loaded if isinstance(item, dict)]


def _submission_out(submission: CodeSubmission) -> CodeExecutionOut:
    return CodeExecutionOut(
        problem_id=submission.problem_id,
        language=submission.language,
        score=submission.score,
        passed_cases=submission.passed_cases,
        total_cases=submission.total_cases,
        visible_results=_stored_case_results(submission.visible_results),
        hidden_results=_stored_case_results(submission.hidden_results),
        submitted=True,
        submission_id=submission.id,
    )


def _final_result_out(submission: CodeSubmission) -> ContestFinalResultOut:
    return ContestFinalResultOut(
        submission_id=submission.id,
        problem_id=submission.problem_id,
        language=submission.language,
        score=submission.score,
        passed_cases=submission.passed_cases,
        total_cases=submission.total_cases,
        submitted_at=_as_aware_utc(submission.submitted_at),
        auto_submitted=submission.is_auto_submitted,
    )


async def _ensure_admin_contest(db: AsyncSession) -> CodingContest:
    contest = await _latest_contest(db, include_unpublished=True, for_update=True)
    if contest is not None:
        return contest

    now = _now_utc()
    # Do not publish or activate a contest just because the admin saves a coding task.
    # The contest schedule endpoints remain responsible for setting the exam window and
    # publication state. This avoids a student-facing contest becoming visible as soon as
    # an admin saves the coding question.
    contest = CodingContest(
        title=settings.DEFAULT_CONTEST_TITLE,
        start_time=now + timedelta(hours=1),
        end_time=now + timedelta(hours=2),
        is_published=False,
    )
    db.add(contest)
    await db.flush()
    return contest


def _apply_problem_payload(
    problem: CodingProblem,
    payload: CodingProblemSaveIn | CodingProblemUpdateIn,
    order_index: int,
) -> None:
    problem.title = payload.title
    problem.statement = payload.statement
    problem.input_format = payload.input_format
    problem.output_format = payload.output_format
    problem.constraints = payload.constraints
    problem.starter_code_python = payload.starter_code_python
    problem.starter_code_cpp = payload.starter_code_cpp
    problem.starter_code_java = payload.starter_code_java
    problem.enabled_languages = ",".join(payload.enabled_languages)
    problem.order_index = order_index


def _test_cases_from_payload(
    payload: CodingProblemSaveIn | CodingProblemUpdateIn,
    problem_id: int,
) -> list[CodingTestCase]:
    return [
        CodingTestCase(
            problem_id=problem_id,
            input_data=test_case.input_data,
            expected_output=test_case.expected_output,
            is_visible=test_case.is_visible,
            sort_order=index,
        )
        for index, test_case in enumerate(payload.test_cases, start=1)
    ]


async def _save_admin_problem_set(
    payloads: list[CodingProblemSaveIn | CodingProblemUpdateIn],
    db: AsyncSession,
) -> list[CodingProblem]:
    contest = await _ensure_admin_contest(db)
    existing_result = await db.execute(
        select(CodingProblem)
        .options(selectinload(CodingProblem.test_cases))
        .where(CodingProblem.contest_id == contest.id)
        .order_by(CodingProblem.order_index)
    )
    existing_problems = list(existing_result.scalars().all())
    existing_by_id = {problem.id: problem for problem in existing_problems}
    payload_ids = [
        payload.id
        for payload in payloads
        if isinstance(payload, CodingProblemSaveIn) and payload.id is not None
    ]

    duplicate_ids = {
        problem_id
        for problem_id in payload_ids
        if payload_ids.count(problem_id) > 1
    }
    if duplicate_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate coding problem id in request.",
        )

    unknown_ids = [
        problem_id for problem_id in payload_ids if problem_id not in existing_by_id
    ]
    if unknown_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coding problem not found in this contest.",
        )

    for problem in existing_problems:
        problem.order_index = -int(problem.id)
    await db.flush()

    saved_problems: list[CodingProblem] = []
    kept_ids: set[int] = set()
    for order_index, payload in enumerate(payloads, start=1):
        payload_id = (
            payload.id
            if isinstance(payload, CodingProblemSaveIn) and payload.id is not None
            else None
        )
        if payload_id is None:
            problem = CodingProblem(
                contest_id=contest.id,
                title=payload.title,
                statement=payload.statement,
                input_format=payload.input_format,
                output_format=payload.output_format,
                constraints=payload.constraints,
                starter_code_python=payload.starter_code_python,
                starter_code_cpp=payload.starter_code_cpp,
                starter_code_java=payload.starter_code_java,
                enabled_languages=",".join(payload.enabled_languages),
                order_index=order_index,
                max_score=100,
            )
            db.add(problem)
            await db.flush()
        else:
            problem = existing_by_id[payload_id]
            kept_ids.add(payload_id)
            _apply_problem_payload(problem, payload, order_index)
            await db.flush()

        await db.execute(
            delete(CodingTestCase).where(CodingTestCase.problem_id == problem.id)
        )
        for test_case in _test_cases_from_payload(payload, problem.id):
            db.add(test_case)
        saved_problems.append(problem)

    for problem in existing_problems:
        if problem.id not in kept_ids:
            await db.delete(problem)

    await db.commit()
    result = await db.execute(
        select(CodingProblem)
        .options(selectinload(CodingProblem.test_cases))
        .where(CodingProblem.contest_id == contest.id)
        .order_by(CodingProblem.order_index)
    )
    return result.scalars().all()


async def _latest_submission_for_contest(
    db: AsyncSession,
    student_id: int,
    contest_id: int,
) -> CodeSubmission | None:
    result = await db.execute(
        select(CodeSubmission)
        .where(
            CodeSubmission.student_id == student_id,
            CodeSubmission.contest_id == contest_id,
        )
        .order_by(CodeSubmission.submitted_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _latest_submissions_for_contest(
    db: AsyncSession,
    student_id: int,
    contest_id: int,
) -> list[CodeSubmission]:
    result = await db.execute(
        select(CodeSubmission)
        .where(
            CodeSubmission.student_id == student_id,
            CodeSubmission.contest_id == contest_id,
        )
        .order_by(CodeSubmission.problem_id, CodeSubmission.submitted_at.desc())
    )
    latest_by_problem: dict[int, CodeSubmission] = {}
    for submission in result.scalars().all():
        if submission.problem_id not in latest_by_problem:
            latest_by_problem[submission.problem_id] = submission
    return list(latest_by_problem.values())


async def _create_code_submission(
    db: AsyncSession,
    subject: dict[str, object],
    problem: CodingProblem,
    language: str,
    source_code: str,
    auto_submitted: bool,
    details: dict[str, object] | None = None,
) -> CodeExecutionOut:
    student_id = int(subject["student_id"])
    enabled = _enabled_languages(problem)
    if language not in enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Language '{language}' is not enabled for this contest.",
        )

    _assert_can_submit(problem.contest, auto_submitted)
    test_cases = _sorted_cases(problem)
    _validate_cases(test_cases, require_full_set=True)

    results = await execute_code_against_cases(source_code, language, test_cases)
    passed_cases = sum(1 for result in results if result.passed)
    score = _score(passed_cases, len(results), problem.max_score)
    session = await _session_for_subject(db, student_id, subject)
    visible_results = [
        _case_result_out(result, reveal_details=True)
        for result in results
        if result.is_visible
    ]
    hidden_results = [
        _case_result_out(result, reveal_details=False)
        for result in results
        if not result.is_visible
    ]

    submission = CodeSubmission(
        student_id=student_id,
        contest_id=problem.contest_id,
        problem_id=problem.id,
        language=language,
        source_code=source_code,
        status="PASSED" if passed_cases == len(results) else "FAILED",
        score=score,
        passed_cases=passed_cases,
        total_cases=len(results),
        visible_results=json.dumps(
            [item.model_dump(exclude_none=True) for item in visible_results]
        ),
        hidden_results=json.dumps(
            [item.model_dump(exclude_none=True) for item in hidden_results]
        ),
        is_auto_submitted=auto_submitted,
        submitted_at=_now_utc(),
    )
    db.add(submission)

    log_details = {
        "contest_id": problem.contest_id,
        "problem_id": problem.id,
        "session_id": session.id if session else None,
        "language": language,
        "score": score,
        "passed_cases": passed_cases,
        "total_cases": len(results),
        **(details or {}),
    }
    db.add(
        ExamLog(
            student_id=student_id,
            session_id=session.id if session else None,
            event_type="AUTO_CODE_SUBMIT" if auto_submitted else "CODE_SUBMIT",
            timestamp=_now_utc(),
            details=json.dumps(log_details),
        )
    )
    await db.commit()
    await db.refresh(submission)
    return CodeExecutionOut(
        problem_id=problem.id,
        language=language,
        score=score,
        passed_cases=passed_cases,
        total_cases=len(results),
        visible_results=visible_results,
        hidden_results=hidden_results,
        submitted=True,
        submission_id=submission.id,
    )


@router.get("/status", response_model=ContestGateOut)
async def contest_status(
    db: AsyncSession = Depends(get_db),
    subject: dict[str, object] = Depends(require_student),
) -> ContestGateOut:
    contest = await _latest_contest(db)
    now = _now_utc()
    contest_state, remaining_seconds = _contest_status(contest, now)

    if contest is None:
        return ContestGateOut(
            status="LOCKED",
            server_time=now,
            start_time=None,
            end_time=None,
            remaining_seconds=0,
            message="No coding contest has been scheduled.",
        )

    student_id = int(subject["student_id"])
    problems = sorted(contest.problems, key=lambda item: item.order_index)
    active_problems = problems if contest_state == "ACTIVE" else []
    problem = active_problems[0] if active_problems else None
    latest_submissions = await _latest_submissions_for_contest(
        db,
        student_id,
        contest.id,
    )
    submitted_problem_ids = [submission.problem_id for submission in latest_submissions]
    final_submission = None
    if contest_state == "ENDED":
        final_submission = await _latest_submission_for_contest(
            db,
            student_id,
            contest.id,
        )
    return ContestGateOut(
        status=contest_state,
        server_time=now,
        start_time=_as_aware_utc(contest.start_time),
        end_time=_as_aware_utc(contest.end_time),
        remaining_seconds=remaining_seconds,
        problem=_problem_out(problem) if problem else None,
        problems=[_problem_out(item) for item in active_problems],
        submitted_problem_ids=submitted_problem_ids,
        final_result=_final_result_out(final_submission) if final_submission else None,
        final_results=[
            _final_result_out(submission)
            for submission in latest_submissions
            if contest_state == "ENDED"
        ],
        message=None if problem or contest_state != "ACTIVE" else "No coding problem configured.",
    )


@router.get("/schedule", response_model=ContestScheduleOut)
async def get_contest_schedule(
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
) -> ContestScheduleOut:
    contest = await _latest_contest(db, include_unpublished=True)
    if contest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No coding contest has been scheduled.",
        )

    now = _now_utc()
    contest_state, remaining_seconds = _contest_status(contest, now)
    return ContestScheduleOut(
        id=contest.id,
        title=contest.title,
        start_time=_as_aware_utc(contest.start_time),
        end_time=_as_aware_utc(contest.end_time),
        is_published=contest.is_published,
        server_time=now,
        status=contest_state,
        remaining_seconds=remaining_seconds,
    )


@router.put("/schedule", response_model=ContestScheduleOut)
async def update_contest_schedule(
    payload: ContestScheduleIn,
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
) -> ContestScheduleOut:
    contest = await _latest_contest(db, include_unpublished=True, for_update=True)
    if contest is None:
        contest = CodingContest(
            title=payload.title or settings.DEFAULT_CONTEST_TITLE,
            start_time=_as_aware_utc(payload.start_time),
            end_time=_as_aware_utc(payload.end_time),
            is_published=payload.is_published,
        )
        db.add(contest)
    else:
        if payload.title:
            contest.title = payload.title
        contest.start_time = _as_aware_utc(payload.start_time)
        contest.end_time = _as_aware_utc(payload.end_time)
        contest.is_published = payload.is_published

    await db.commit()
    await db.refresh(contest)

    now = _now_utc()
    contest_state, remaining_seconds = _contest_status(contest, now)
    return ContestScheduleOut(
        id=contest.id,
        title=contest.title,
        start_time=_as_aware_utc(contest.start_time),
        end_time=_as_aware_utc(contest.end_time),
        is_published=contest.is_published,
        server_time=now,
        status=contest_state,
        remaining_seconds=remaining_seconds,
    )


@router.get("/problem-admin", response_model=CodingProblemAdminOut)
async def get_admin_coding_problem(
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
) -> CodingProblemAdminOut:
    contest = await _latest_contest(db, include_unpublished=True)
    if contest is None or not contest.problems:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No coding problem has been configured.",
        )

    problem = sorted(contest.problems, key=lambda item: item.order_index)[0]
    return _problem_admin_out(problem)


@router.get("/problems-admin", response_model=list[CodingProblemAdminOut])
async def get_admin_coding_problems(
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
) -> list[CodingProblemAdminOut]:
    contest = await _latest_contest(db, include_unpublished=True)
    if contest is None or not contest.problems:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No coding problems have been configured.",
        )

    return [
        _problem_admin_out(problem)
        for problem in sorted(contest.problems, key=lambda item: item.order_index)
    ]


@router.put("/problem-admin", response_model=CodingProblemAdminOut)
async def update_admin_coding_problem(
    payload: CodingProblemUpdateIn,
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
) -> CodingProblemAdminOut:
    problems = await _save_admin_problem_set([payload], db)
    return _problem_admin_out(problems[0])


@router.put("/problems-admin", response_model=list[CodingProblemAdminOut])
async def update_admin_coding_problems(
    payload: CodingProblemsUpdateIn,
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
) -> list[CodingProblemAdminOut]:
    problems = await _save_admin_problem_set(payload.problems, db)
    return [_problem_admin_out(problem) for problem in problems]


@router.put("/draft", response_model=CodeDraftOut)
async def save_code_draft(
    payload: CodeDraftSaveRequest,
    db: AsyncSession = Depends(get_db),
    subject: dict[str, object] = Depends(require_student),
) -> CodeDraftOut:
    student_id = int(subject["student_id"])
    problem = await _problem_for_payload(db, payload.problem_id)
    enabled = _enabled_languages(problem)
    if payload.language not in enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Language '{payload.language}' is not enabled for this contest.",
        )
    _assert_active(problem.contest)

    result = await db.execute(
        select(CodeDraft)
        .where(
            CodeDraft.student_id == student_id,
            CodeDraft.contest_id == problem.contest_id,
            CodeDraft.problem_id == problem.id,
        )
        .with_for_update()
    )
    draft = result.scalar_one_or_none()
    now = _now_utc()

    if draft:
        draft.language = payload.language
        draft.source_code = payload.source_code
        draft.updated_at = now
    else:
        draft = CodeDraft(
            student_id=student_id,
            contest_id=problem.contest_id,
            problem_id=problem.id,
            language=payload.language,
            source_code=payload.source_code,
            created_at=now,
            updated_at=now,
        )
        db.add(draft)

    await db.commit()
    return CodeDraftOut(
        problem_id=problem.id,
        language=payload.language,
        updated_at=now,
        saved=True,
    )


@router.post(
    "/auto-submit-draft",
    response_model=CodeExecutionOut,
    response_model_exclude_none=True,
)
async def auto_submit_latest_draft(
    payload: CodeDraftAutoSubmitRequest,
    db: AsyncSession = Depends(get_db),
    subject: dict[str, object] = Depends(require_student),
) -> CodeExecutionOut:
    student_id = int(subject["student_id"])
    problem = await _problem_for_payload(db, payload.problem_id)
    _assert_can_submit(problem.contest, auto_submitted=True)

    existing_result = await db.execute(
        select(CodeSubmission)
        .where(
            CodeSubmission.student_id == student_id,
            CodeSubmission.contest_id == problem.contest_id,
            CodeSubmission.problem_id == problem.id,
        )
        .order_by(CodeSubmission.submitted_at.desc())
        .limit(1)
    )
    existing_submission = existing_result.scalar_one_or_none()
    if existing_submission:
        return _submission_out(existing_submission)

    draft_result = await db.execute(
        select(CodeDraft).where(
            CodeDraft.student_id == student_id,
            CodeDraft.contest_id == problem.contest_id,
            CodeDraft.problem_id == problem.id,
        )
    )
    draft = draft_result.scalar_one_or_none()
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No saved draft is available for auto-submit.",
        )

    enabled = _enabled_languages(problem)
    language = draft.language if draft.language in enabled else enabled[0]
    source_code = draft.source_code if draft.source_code.strip() else _starter_for_language(problem, language)
    return await _create_code_submission(
        db,
        subject,
        problem,
        language,
        source_code,
        auto_submitted=True,
        details={
            "reason": payload.reason,
            "draft_id": draft.id,
            "draft_updated_at": draft.updated_at.isoformat(),
        },
    )


@router.post(
    "/run-samples",
    response_model=CodeExecutionOut,
    response_model_exclude_none=True,
)
async def run_visible_samples(
    payload: CodeRunRequest,
    db: AsyncSession = Depends(get_db),
    _subject: dict[str, object] = Depends(require_student),
) -> CodeExecutionOut:
    problem = await _problem_for_payload(db, payload.problem_id)
    enabled = _enabled_languages(problem)
    if payload.language not in enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Language '{payload.language}' is not enabled for this contest.",
        )
    _assert_active(problem.contest)
    test_cases = _sorted_cases(problem)
    _validate_cases(test_cases, require_full_set=False)
    visible_cases = [test_case for test_case in test_cases if test_case.is_visible]

    results = await execute_code_against_cases(
        payload.source_code,
        payload.language,
        visible_cases,
    )
    passed_cases = sum(1 for result in results if result.passed)
    visible_results = [_case_result_out(result, reveal_details=True) for result in results]
    return CodeExecutionOut(
        problem_id=problem.id,
        language=payload.language,
        score=_score(passed_cases, len(results), problem.max_score),
        passed_cases=passed_cases,
        total_cases=len(results),
        visible_results=visible_results,
        hidden_results=[],
        submitted=False,
    )


@router.post("/debug", response_model=CodeDebugOut)
async def debug_code_error(
    payload: CodeDebugRequest,
    _subject: dict[str, object] = Depends(require_student),
) -> CodeDebugOut:
    api_key = os.getenv("GEMINI_API_KEY") or settings.GEMINI_API_KEY
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI debugger is unavailable because GEMINI_API_KEY is not configured.",
        )

    model_name = os.getenv("GEMINI_MODEL") or settings.GEMINI_MODEL
    try:
        timeout_seconds = int(
            os.getenv("GEMINI_TIMEOUT_SECONDS") or settings.GEMINI_TIMEOUT_SECONDS
        )
    except (TypeError, ValueError):
        timeout_seconds = 45
    timeout_seconds = max(10, min(timeout_seconds, 120))

    try:
        return await asyncio.wait_for(
            run_in_threadpool(
                _generate_code_debug,
                api_key,
                model_name,
                timeout_seconds,
                payload.language,
                payload.source_code,
                payload.error_logs,
            ),
            timeout=timeout_seconds + 5,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI debugging timed out. Run the sample again to retry.",
        ) from exc
    except Exception as exc:
        logger.exception("AI code debugging failed.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI debugger could not analyze this error. Check the compiler logs above.",
        ) from exc


@router.post(
    "/submit",
    response_model=CodeExecutionOut,
    response_model_exclude_none=True,
)
async def submit_code(
    payload: CodeSubmitRequest,
    db: AsyncSession = Depends(get_db),
    subject: dict[str, object] = Depends(require_student),
) -> CodeExecutionOut:
    problem = await _problem_for_payload(db, payload.problem_id)
    return await _create_code_submission(
        db,
        subject,
        problem,
        payload.language,
        payload.source_code,
        payload.auto_submitted,
    )
