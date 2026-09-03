from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    roll_no: Mapped[str | None] = mapped_column(
        String(50),
        unique=True,
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    # Stored as a bcrypt hash. The plaintext PIN is returned only when generated.
    secret_pin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_pin_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    invite_token_hash: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
    )
    is_invite_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    invite_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    invite_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    invite_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    invite_status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=utc_now,
        nullable=True,
    )

    sessions: Mapped[list["ExamSession"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )
    logs: Mapped[list["ExamLog"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )
    responses: Mapped[list["Response"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )
    code_submissions: Mapped[list["CodeSubmission"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )


class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ip_address: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    network_isp: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    student: Mapped["Student"] = relationship(back_populates="sessions")
    logs: Mapped[list["ExamLog"]] = relationship(back_populates="session")


class ExamLog(Base):
    __tablename__ = "exam_logs"
    __table_args__ = (
        Index("ix_exam_logs_student_event_timestamp", "student_id", "event_type", "timestamp"),
        Index("ix_exam_logs_session_timestamp", "session_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("exam_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    details: Mapped[str | None] = mapped_column(Text, nullable=True)

    student: Mapped["Student"] = relationship(back_populates="logs")
    session: Mapped["ExamSession | None"] = relationship(back_populates="logs")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    option_a: Mapped[str] = mapped_column(String(255), nullable=False)
    option_b: Mapped[str] = mapped_column(String(255), nullable=False)
    option_c: Mapped[str] = mapped_column(String(255), nullable=False)
    option_d: Mapped[str] = mapped_column(String(255), nullable=False)
    correct_option: Mapped[str] = mapped_column(String(1), nullable=False)

    responses: Mapped[list["Response"]] = relationship(back_populates="question")


class Response(Base):
    __tablename__ = "responses"
    __table_args__ = (
        UniqueConstraint("student_id", "question_id", name="uq_response_student_question"),
        Index("ix_responses_student_timestamp", "student_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    selected_option: Mapped[str] = mapped_column(String(1), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    student: Mapped["Student"] = relationship(back_populates="responses")
    question: Mapped["Question"] = relationship(back_populates="responses")


class CodingContest(Base):
    __tablename__ = "coding_contests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=utc_now,
        nullable=True,
    )

    problems: Mapped[list["CodingProblem"]] = relationship(
        back_populates="contest",
        cascade="all, delete-orphan",
    )
    submissions: Mapped[list["CodeSubmission"]] = relationship(back_populates="contest")


class CodingProblem(Base):
    __tablename__ = "coding_problems"
    __table_args__ = (
        UniqueConstraint("contest_id", "order_index", name="uq_problem_contest_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contest_id: Mapped[int] = mapped_column(
        ForeignKey("coding_contests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    input_format: Mapped[str] = mapped_column(Text, nullable=False)
    output_format: Mapped[str] = mapped_column(Text, nullable=False)
    constraints: Mapped[str] = mapped_column(Text, nullable=False)
    starter_code_python: Mapped[str] = mapped_column(Text, nullable=False)
    starter_code_cpp: Mapped[str] = mapped_column(Text, nullable=False)
    starter_code_java: Mapped[str] = mapped_column(Text, nullable=False)
    enabled_languages: Mapped[str] = mapped_column(String(80), default="python,cpp,java", nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_score: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    contest: Mapped["CodingContest"] = relationship(back_populates="problems")
    test_cases: Mapped[list["CodingTestCase"]] = relationship(
        back_populates="problem",
        cascade="all, delete-orphan",
    )
    submissions: Mapped[list["CodeSubmission"]] = relationship(back_populates="problem")


class CodingTestCase(Base):
    __tablename__ = "coding_test_cases"
    __table_args__ = (
        UniqueConstraint("problem_id", "sort_order", name="uq_test_case_problem_order"),
        Index("ix_test_cases_problem_visible", "problem_id", "is_visible"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("coding_problems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    input_data: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    problem: Mapped["CodingProblem"] = relationship(back_populates="test_cases")


class CodeSubmission(Base):
    __tablename__ = "code_submissions"
    __table_args__ = (
        Index("ix_code_submissions_student_problem_time", "student_id", "problem_id", "submitted_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contest_id: Mapped[int] = mapped_column(
        ForeignKey("coding_contests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("coding_problems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    passed_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    visible_results: Mapped[str] = mapped_column(Text, nullable=False)
    hidden_results: Mapped[str] = mapped_column(Text, nullable=False)
    is_auto_submitted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    student: Mapped["Student"] = relationship(back_populates="code_submissions")
    contest: Mapped["CodingContest"] = relationship(back_populates="submissions")
    problem: Mapped["CodingProblem"] = relationship(back_populates="submissions")


class CodeDraft(Base):
    __tablename__ = "code_drafts"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "contest_id",
            "problem_id",
            name="uq_code_draft_student_contest_problem",
        ),
        Index("ix_code_drafts_student_problem", "student_id", "problem_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contest_id: Mapped[int] = mapped_column(
        ForeignKey("coding_contests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("coding_problems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        index=True,
    )
