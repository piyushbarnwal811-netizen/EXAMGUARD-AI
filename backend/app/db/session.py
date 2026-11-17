from collections.abc import AsyncIterator
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import func, inspect, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.models import Base, CodingContest, CodingProblem, CodingTestCase, Institute, Question

settings = get_settings()


def _normalize_database_url(raw_url: str) -> tuple[str, dict[str, object]]:
    """
    Normalizes DATABASE_URL for async SQLAlchemy with asyncpg / aiosqlite.
    Handles postgres:// and postgresql:// prefixes, SSL parameters, and connect_args.
    """
    raw_url = (raw_url or "").strip()
    if not raw_url:
        raw_url = "sqlite+aiosqlite:///./examguard_prod.db"

    # Normalize driver prefix for async SQLAlchemy
    if raw_url.startswith("postgres://"):
        raw_url = "postgresql+asyncpg://" + raw_url[len("postgres://"):]
    elif raw_url.startswith("postgresql://"):
        raw_url = "postgresql+asyncpg://" + raw_url[len("postgresql://"):]
    elif raw_url.startswith("sqlite:///"):
        raw_url = "sqlite+aiosqlite:///" + raw_url[len("sqlite:///"):]

    connect_args: dict[str, object] = {}

    if raw_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        return raw_url, connect_args

    if raw_url.startswith("postgresql+asyncpg://"):
        parsed = urlparse(raw_url)
        query_params = dict(parse_qsl(parsed.query))

        # Handle SSL requirement for Neon / Supabase / Render
        sslmode = query_params.pop("sslmode", None)
        ssl_val = query_params.pop("ssl", None)
        if sslmode in ("require", "verify-ca", "verify-full", "prefer") or ssl_val in ("true", "1", "require"):
            connect_args["ssl"] = "require"

        # Pop any libpq query params that asyncpg does not recognize as connect kwargs
        unsupported_libpq_params = [
            "channel_binding",
            "target_session_attrs",
            "gssencmode",
            "sslrootcert",
            "sslcert",
            "sslkey",
        ]
        for param in unsupported_libpq_params:
            query_params.pop(param, None)

        clean_query = urlencode(query_params)
        clean_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            clean_query,
            parsed.fragment,
        ))
        return clean_url, connect_args

    return raw_url, connect_args


database_url, connect_args = _normalize_database_url(settings.DATABASE_URL)
engine_kwargs: dict[str, object] = {
    "echo": settings.DB_ECHO,
    "pool_pre_ping": True,
}

if connect_args:
    engine_kwargs["connect_args"] = connect_args

if database_url.startswith("postgresql+asyncpg://"):
    engine_kwargs.update(
        {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
        }
    )

engine = create_async_engine(database_url, **engine_kwargs)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    class_=AsyncSession,
)


def _ensure_student_invite_columns(sync_conn) -> None:
    inspector = inspect(sync_conn)
    if "students" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("students")
    }
    timestamp_type = (
        "TIMESTAMP WITH TIME ZONE"
        if sync_conn.dialect.name == "postgresql"
        else "DATETIME"
    )
    columns = {
        "invite_token_hash": "VARCHAR(255)",
        "is_invite_used": (
            "BOOLEAN NOT NULL DEFAULT FALSE"
            if sync_conn.dialect.name == "postgresql"
            else "BOOLEAN NOT NULL DEFAULT 0"
        ),
        "invite_token_expires_at": timestamp_type,
        "invite_sent_at": timestamp_type,
        "invite_accepted_at": timestamp_type,
    }

    for column_name, column_type in columns.items():
        if column_name not in existing_columns:
            sync_conn.exec_driver_sql(
                f"ALTER TABLE students ADD COLUMN {column_name} {column_type}"
            )

    existing_indexes = {
        index["name"] for index in inspector.get_indexes("students")
    }
    if "ix_students_invite_token_hash" not in existing_indexes:
        sync_conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_students_invite_token_hash "
            "ON students (invite_token_hash)"
        )


def _ensure_exam_log_session_column(sync_conn) -> None:
    inspector = inspect(sync_conn)
    if "exam_logs" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("exam_logs")
    }
    if "session_id" not in existing_columns:
        sync_conn.exec_driver_sql(
            "ALTER TABLE exam_logs ADD COLUMN session_id "
            "INTEGER REFERENCES exam_sessions(id) ON DELETE SET NULL"
        )

    existing_indexes = {
        index["name"] for index in inspector.get_indexes("exam_logs")
    }
    if "ix_exam_logs_session_id" not in existing_indexes:
        sync_conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_exam_logs_session_id "
            "ON exam_logs (session_id)"
        )
    if "ix_exam_logs_session_timestamp" not in existing_indexes:
        sync_conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_exam_logs_session_timestamp "
            "ON exam_logs (session_id, timestamp)"
        )


def _ensure_coding_problem_language_column(sync_conn) -> None:
    inspector = inspect(sync_conn)
    if "coding_problems" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("coding_problems")
    }
    if "enabled_languages" not in existing_columns:
        sync_conn.exec_driver_sql(
            "ALTER TABLE coding_problems ADD COLUMN enabled_languages "
            "VARCHAR(80) NOT NULL DEFAULT 'python,cpp,java'"
        )


async def _seed_questions() -> None:
    async with AsyncSessionLocal() as db:
        count = await db.scalar(select(func.count(Question.id)))
        if count:
            return

        db.add_all(
            [
                Question(
                    id=1,
                    question_text="What does CPU stand for?",
                    option_a="Central Processing Unit",
                    option_b="Computer Personal Unit",
                    option_c="Central Program Utility",
                    option_d="Control Processing User",
                    correct_option="A",
                ),
                Question(
                    id=2,
                    question_text="Which keyword is used to define a function in Python?",
                    option_a="func",
                    option_b="def",
                    option_c="function",
                    option_d="method",
                    correct_option="B",
                ),
            ]
        )
        await db.commit()


def _default_contest_window() -> tuple[datetime, datetime]:
    now_local = datetime.now().astimezone()
    start_local = now_local.replace(hour=11, minute=0, second=0, microsecond=0)
    end_local = now_local.replace(hour=12, minute=30, second=0, microsecond=0)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


async def _seed_coding_contest() -> None:
    async with AsyncSessionLocal() as db:
        count = await db.scalar(select(func.count(CodingContest.id)))
        if count:
            return

        start_time, end_time = _default_contest_window()
        contest = CodingContest(
            title=settings.DEFAULT_CONTEST_TITLE,
            start_time=start_time,
            end_time=end_time,
            is_published=True,
        )
        problem = CodingProblem(
            title="Sum of Two Numbers",
            statement=(
                "Given two integers A and B, read them from standard input and "
                "print their sum."
            ),
            input_format="The input contains two integers A and B separated by whitespace.",
            output_format="Print a single integer: A + B.",
            constraints="-1000000 <= A, B <= 1000000",
            starter_code_python=(
                "import sys\n\n"
                "def solve():\n"
                "    data = sys.stdin.read().strip().split()\n"
                "    a, b = map(int, data[:2])\n"
                "    print(a + b)\n\n"
                "if __name__ == \"__main__\":\n"
                "    solve()\n"
            ),
            starter_code_cpp=(
                "#include <bits/stdc++.h>\n"
                "using namespace std;\n\n"
                "int main() {\n"
                "    long long a, b;\n"
                "    cin >> a >> b;\n"
                "    cout << a + b << '\\n';\n"
                "    return 0;\n"
                "}\n"
            ),
            starter_code_java=(
                "import java.io.*;\n"
                "import java.util.*;\n\n"
                "public class Main {\n"
                "    public static void main(String[] args) throws Exception {\n"
                "        Scanner sc = new Scanner(System.in);\n"
                "        long a = sc.nextLong();\n"
                "        long b = sc.nextLong();\n"
                "        System.out.println(a + b);\n"
                "    }\n"
                "}\n"
            ),
            order_index=1,
            max_score=100,
        )
        cases = [
            ("2 3\n", "5\n", True),
            ("100 250\n", "350\n", True),
            ("0 0\n", "0\n", False),
            ("-5 12\n", "7\n", False),
            ("999999 1\n", "1000000\n", False),
            ("-1000000 -1\n", "-1000001\n", False),
            ("42 -42\n", "0\n", False),
            ("123456 654321\n", "777777\n", False),
            ("-700000 300000\n", "-400000\n", False),
            ("1000000 1000000\n", "2000000\n", False),
        ]
        problem.test_cases = [
            CodingTestCase(
                input_data=input_data,
                expected_output=expected_output,
                is_visible=is_visible,
                sort_order=index,
            )
            for index, (input_data, expected_output, is_visible) in enumerate(cases, start=1)
        ]
        contest.problems = [problem]
        db.add(contest)
        await db.commit()


async def _seed_super_admin_and_institutes() -> None:
    from app.core.security import hash_secret
    async with AsyncSessionLocal() as db:
        admin_username = settings.ADMIN_USERNAME.strip()
        admin_email = "piyushbarnwal811@gmail.com"

        # 1. Ensure Super Admin account is seeded safely in the database
        existing_admin = await db.execute(
            select(Institute).where(
                or_(
                    func.lower(Institute.username) == admin_username.lower(),
                    func.lower(Institute.email) == admin_email.lower(),
                    func.lower(Institute.code) == "SUPER-ADMIN",
                )
            )
        )
        if not existing_admin.scalar_one_or_none():
            super_admin = Institute(
                name="Master Administration",
                code="SUPER-ADMIN",
                username=admin_username,
                password_hash=hash_secret(settings.ADMIN_PASSWORD),
                contact_person="Piyush Barnwal",
                phone="9876543210",
                email=admin_email,
                is_active=True,
            )
            db.add(super_admin)
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()

        # 2. Ensure Seed Coaching (Target Topper Classes) is seeded safely
        existing_topper = await db.execute(
            select(Institute).where(
                or_(
                    func.lower(Institute.username) == "targettopper",
                    func.lower(Institute.code) == "TARGET-TOPPER",
                )
            )
        )
        if not existing_topper.scalar_one_or_none():
            target_topper = Institute(
                name="Target Topper Classes",
                code="TARGET-TOPPER",
                username="targettopper",
                password_hash=hash_secret("topper123"),
                contact_person="Director",
                phone="9876543210",
                email="targettopper@example.com",
                is_active=True,
            )
            db.add(target_topper)
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_student_invite_columns)
        await conn.run_sync(_ensure_exam_log_session_column)
        await conn.run_sync(_ensure_coding_problem_language_column)
    await _seed_questions()
    await _seed_coding_contest()
    await _seed_super_admin_and_institutes()


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise
