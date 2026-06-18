"""AI Interview Agent System - Startup Script"""
import uvicorn
from app.core.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    port = settings.port
    print(f"[AI Interview] Starting {settings.app_name} v{settings.app_version}")
    print(f"[AI Interview] Admin:  http://localhost:{port}/")
    print(f"[AI Interview] API:    http://localhost:{port}/docs")
    print(f"[AI Interview] Press Ctrl+C to stop")
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=port,
        reload=True,
    )
