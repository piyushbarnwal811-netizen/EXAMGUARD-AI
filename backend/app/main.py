from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api import admin, auth, contest, exam, questions, tracking
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log exc here if needed
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/api/health")
async def api_health_check() -> dict[str, str]:
    return {"status": "ok"}


frontend_dir = PROJECT_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/frontend", StaticFiles(directory=frontend_dir, html=True), name="frontend")

# Safe browser download endpoint
@app.get("/api/download/safe-browser")
async def download_safe_browser():
    file_path = PROJECT_DIR / "assets" / "ExamGuardSafeBrowser.exe"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Safe browser installer not found")
    return FileResponse(path=file_path, filename="ExamGuardSafeBrowser.exe", media_type="application/octet-stream")

# SEB config download endpoint
@app.get("/api/download/seb-config")
async def download_seb_config():
    file_path = PROJECT_DIR / "assets" / "ExamConfig.seb"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="SEB config not found")
    return FileResponse(path=file_path, filename="ExamConfig.seb", media_type="application/octet-stream")

app.include_router(auth.router, prefix="/api")
app.include_router(contest.router, prefix="/api")
app.include_router(exam.router, prefix="/api")
app.include_router(questions.router, prefix="/api")
app.include_router(tracking.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
