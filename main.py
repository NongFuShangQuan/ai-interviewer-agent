"""AI Interview Agent System - Main Application"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from app.core.config import get_settings
from app.core.database import init_db
from app.api.tts import router as tts_router
from app.api.stt import router as stt_router
from app.api.admin import router as admin_router
from app.core.database import async_session_factory
from app.models.models import Interview
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.realtime.socketio_server import create_socketio_server

settings = get_settings()
templates = Jinja2Templates(directory="app/templates")

# Create Socket.IO server
sio = create_socketio_server()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[START] {settings.app_name} v{settings.app_version}")
    await init_db()
    print("[OK] Database initialized")

    # Initialize RAG system
    try:
        from app.rag.manager import get_rag_manager
        rag = await get_rag_manager()
        status = rag.get_status()
        print(f"[OK] RAG initialized: questions={status['question_bank_count']}, "
              f"eval_refs={status['eval_ref_count']}, knowledge={status['knowledge_count']}")
    except Exception as e:
        print(f"[WARN] RAG initialization failed (degraded mode): {e}")

    yield
    print("[STOP] Shutting down")
    try:
        from app.core.cache import get_cache
        get_cache().shutdown()
    except Exception:
        pass


fastapi_app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

async def _get_candidate_name(token: str) -> str:
    """Look up candidate name from interview token"""
    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(Interview).options(selectinload(Interview.candidate)).where(Interview.token == token)
            )
            interview = result.scalar_one_or_none()
            if interview and interview.candidate:
                return interview.candidate.name
    except Exception:
        pass
    return "Candidate"



@fastapi_app.get("/api/cache/stats")
async def cache_stats():
    from app.core.cache import get_cache
    return get_cache().get_stats()


fastapi_app.mount("/static", StaticFiles(directory="app/static"), name="static")
fastapi_app.include_router(admin_router)
fastapi_app.include_router(tts_router)
fastapi_app.include_router(stt_router)


@fastapi_app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "admin.html")


@fastapi_app.get("/interview/{token}", response_class=HTMLResponse)
async def interview_page(request: Request, token: str):
    candidate_name = await _get_candidate_name(token)
    return templates.TemplateResponse(request, "interview.html",
        {"token": token, "ws_url": f"ws://localhost:{settings.port}", "candidate_name": candidate_name})


@fastapi_app.get("/video/{token}", response_class=HTMLResponse)
async def video_interview_page(request: Request, token: str):
    candidate_name = await _get_candidate_name(token)
    return templates.TemplateResponse(request, "video_interview.html",
        {"token": token, "ws_url": f"ws://localhost:{settings.port}", "candidate_name": candidate_name})


@fastapi_app.get("/live/{token}", response_class=HTMLResponse)
async def live_interview_page(request: Request, token: str):
    candidate_name = await _get_candidate_name(token)
    return templates.TemplateResponse(request, "live_interview.html",
        {"token": token, "ws_url": f"ws://localhost:{settings.port}", "candidate_name": candidate_name})


@fastapi_app.get("/result/{token}", response_class=HTMLResponse)
async def result_page(request: Request, token: str):
    return templates.TemplateResponse(request, "result.html", {"token": token})


@fastapi_app.get("/speech-test", response_class=HTMLResponse)
async def speech_test_page(request: Request):
    return templates.TemplateResponse(request, "speech_test.html", {})


@fastapi_app.get("/test-image", response_class=HTMLResponse)
async def test_image_page(request: Request):
    return templates.TemplateResponse(request, "test_image.html")


# Mount Socket.IO ASGI app wrapping FastAPI
import socketio as _sio_lib
app = _sio_lib.ASGIApp(sio, other_asgi_app=fastapi_app)