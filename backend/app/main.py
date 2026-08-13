from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import admin, auth, contest, exam, tracking
from app.config import PROJECT_DIR, get_settings
from app.db.session import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="FastAPI backend for ExamGuard AI online exam monitoring.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "app": settings.APP_NAME}


frontend_dir = PROJECT_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")

app.include_router(auth.router, prefix="/api")
app.include_router(contest.router, prefix="/api")
app.include_router(exam.router, prefix="/api")
app.include_router(tracking.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
