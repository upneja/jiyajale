"""Jiyajale FastAPI backend – vocal separation web service."""

from __future__ import annotations

import asyncio
import re
import threading
from pathlib import Path
from typing import Optional

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.pitch import pitch_shift_audio
from backend.processing import SongResult, process_song

# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"

app = FastAPI(title="Jiyajale API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Job tracking for WebSocket progress (Task 5)
# ---------------------------------------------------------------------------

_active_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Return a URL/filesystem-safe slug from *text*."""
    return _SLUG_RE.sub("-", text.strip().lower()).strip("-")


TRACK_MAP = {
    "original": "original.wav",
    "instrumental": "stems/htdemucs_ft/original/no_vocals.wav",
    "vocals": "stems/htdemucs_ft/original/vocals.wav",
}


# ---------------------------------------------------------------------------
# Task 1: Health endpoint
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Task 3: Song list & audio serving
# ---------------------------------------------------------------------------


@app.get("/api/songs")
async def list_songs() -> list[dict]:
    """Scan output/ directory and return metadata for every processed song."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    songs: list[dict] = []
    for song_dir in sorted(OUTPUT_DIR.iterdir()):
        if not song_dir.is_dir():
            continue
        original = (song_dir / "original.wav").exists()
        instrumental = (
            song_dir / "stems" / "htdemucs_ft" / "original" / "no_vocals.wav"
        ).exists()
        vocals = (
            song_dir / "stems" / "htdemucs_ft" / "original" / "vocals.wav"
        ).exists()
        songs.append(
            {
                "name": song_dir.name,
                "has_original": original,
                "has_instrumental": instrumental,
                "has_vocals": vocals,
            }
        )
    return songs


@app.get("/api/audio/{song_name}/{track}")
async def get_audio(song_name: str, track: str) -> FileResponse:
    """Serve a WAV file for *song_name* and *track*."""
    if track not in TRACK_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown track '{track}'. Choose from: {', '.join(TRACK_MAP)}",
        )
    wav_path = OUTPUT_DIR / song_name / TRACK_MAP[track]
    if not wav_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(str(wav_path), media_type="audio/wav")


# ---------------------------------------------------------------------------
# Task 3: Process endpoint (updated in Task 5 to write job status)
# ---------------------------------------------------------------------------


@app.post("/api/process")
async def process(
    query: Optional[str] = Form(None),
    song_name: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
) -> dict:
    """Download/convert a song and run Demucs stem separation."""
    if not query and not file:
        raise HTTPException(
            status_code=400, detail="Provide either 'query' or upload a file."
        )

    resolved_name = slugify(song_name) if song_name else None
    if not resolved_name:
        if query:
            resolved_name = slugify(query)[:60]
        elif file:
            resolved_name = slugify(Path(file.filename).stem)[:60]

    local_file: Optional[Path] = None
    if file:
        tmp_dir = OUTPUT_DIR / resolved_name
        tmp_dir.mkdir(parents=True, exist_ok=True)
        local_file = tmp_dir / file.filename
        with open(local_file, "wb") as fh:
            fh.write(await file.read())

    # --- Task 5: progress callback ---
    with _jobs_lock:
        _active_jobs[resolved_name] = {"status": "queued", "progress": 0}

    def on_progress(stage: str, pct: float) -> None:
        with _jobs_lock:
            _active_jobs[resolved_name] = {"status": stage, "progress": pct}

    def _run() -> SongResult:
        return process_song(
            query=query,
            local_file=local_file,
            song_name=resolved_name,
            output_dir=OUTPUT_DIR,
            on_progress=on_progress,
        )

    try:
        result: SongResult = await asyncio.to_thread(_run)
    except Exception as exc:
        with _jobs_lock:
            _active_jobs[resolved_name] = {"status": "error", "progress": 0, "error": str(exc)}
        raise HTTPException(status_code=500, detail=str(exc))

    with _jobs_lock:
        _active_jobs[resolved_name] = {"status": "done", "progress": 100}

    return {
        "name": result.name,
        "original": str(result.original),
        "instrumental": str(result.instrumental),
        "vocals": str(result.vocals),
    }


# ---------------------------------------------------------------------------
# Task 4: Pitch-shift endpoint
# ---------------------------------------------------------------------------


@app.post("/api/pitch-shift")
async def pitch_shift(
    song_name: str = Form(...),
    track: str = Form(...),
    semitones: float = Form(...),
) -> FileResponse:
    """Pitch-shift a track and return the shifted file."""
    if track not in TRACK_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown track '{track}'.")

    source_path = OUTPUT_DIR / song_name / TRACK_MAP[track]
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Source audio not found.")

    exports_dir = OUTPUT_DIR / song_name / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    sign = "+" if semitones >= 0 else ""
    out_filename = f"{track}_pitch{sign}{semitones:g}.wav"
    output_path = exports_dir / out_filename

    await asyncio.to_thread(pitch_shift_audio, source_path, output_path, semitones)

    return FileResponse(str(output_path), media_type="audio/wav", filename=out_filename)


# ---------------------------------------------------------------------------
# Task 5: WebSocket progress endpoint
# ---------------------------------------------------------------------------


@app.websocket("/ws/status/{song_name}")
async def ws_status(websocket: WebSocket, song_name: str) -> None:
    """Stream job progress for *song_name* over WebSocket."""
    await websocket.accept()
    try:
        while True:
            with _jobs_lock:
                status = _active_jobs.get(song_name, {"status": "unknown", "progress": 0})
            await websocket.send_json(status)
            if status.get("status") in ("done", "error"):
                break
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
