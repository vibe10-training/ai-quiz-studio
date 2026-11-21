from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .ai_service import AIServiceError, generate_quiz
from .config import PROJECT_ROOT, get_ai_settings
from .models import QuizGenerateRequest, QuizGenerateResponse


app = FastAPI(title="AI Quiz Studio API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    settings = get_ai_settings()
    return {
        "status": "ok",
        "ai_configured": settings.is_configured,
        "env_file_detected": settings.source_file_found,
        "model": settings.model if settings.is_configured else None,
    }


@app.post("/api/quiz/generate", response_model=QuizGenerateResponse)
async def create_quiz(req: QuizGenerateRequest):
    try:
        return await generate_quiz(req)
    except AIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


# Local execution support: serve static files from public/ when running via uvicorn
PUBLIC_DIR: Path = PROJECT_ROOT / "public"
if PUBLIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(PUBLIC_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(str(PUBLIC_DIR / "index.html"))

    @app.get("/{filename:path}")
    async def serve_public_assets(filename: str):
        if filename.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        target = (PUBLIC_DIR / filename).resolve()
        if target.is_file() and str(target).startswith(str(PUBLIC_DIR.resolve())):
            return FileResponse(str(target))
        return FileResponse(str(PUBLIC_DIR / "index.html"))
