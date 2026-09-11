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
    response = JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    return response


@app.get("/")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/api/health")
async def api_health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/ping")
async def ping() -> dict[str, str]:
    return {"status": "ok", "message": "Server is awake"}


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






async def download_seb_config(token: str | None = None):
    from app.config import get_settings
    import re
    settings = get_settings()
    base = getattr(settings, "FRONTEND_URL", "https://examguard-ai.vercel.app").rstrip('/')
    # Token aaya to usi token ke saath StartURL banao
    start_url = f"{base}/exam?token={token}" if token else f"{base}/exam"

    template_path = PROJECT_DIR / "assets" / "ExamConfig.seb"
    if template_path.exists():
        content = template_path.read_text(encoding="utf-8")
        # startURL ko replace karo
        content = re.sub(r'<key name="startURL">.*?</key>', f'<key name="startURL">{start_url}</key>', content, flags=re.DOTALL)
        content = re.sub(r'https://examguard-ai-317p.onrender.com', start_url, content)
    else:
        content = f'<seb><config><key name="startURL">{start_url}</key></config></seb>'

    from fastapi.responses import Response
    return Response(content=content, media_type="application/x-safe-exam-browser-config", headers={"Content-Disposition": 'attachment; filename="ExamConfig.seb"'})
app.include_router(auth.router, prefix="/api")
app.include_router(contest.router, prefix="/api")
app.include_router(exam.router, prefix="/api")
app.include_router(questions.router, prefix="/api")
app.include_router(tracking.router, prefix="/api")
app.include_router(admin.router, prefix="/api")