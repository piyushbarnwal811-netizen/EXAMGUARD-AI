import asyncio
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DB_PATH = BACKEND_DIR / "test_examguard_api.db"

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["SECRET_KEY"] = "examguard-test-secret"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"
os.environ["ALLOWED_IP_RANGES"] = "127.0.0.1/32,::1/128"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.models import Base  # noqa: E402
from app.db.session import engine, init_db  # noqa: E402
from app.main import app  # noqa: E402


async def _reset_database() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await init_db()


@pytest.fixture()
def client() -> TestClient:
    asyncio.run(_reset_database())
    with TestClient(app) as test_client:
        yield test_client
