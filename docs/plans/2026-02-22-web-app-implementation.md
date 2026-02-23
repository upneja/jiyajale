# Jiyajale Web App Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local web app (FastAPI + React) so mom can process songs and play karaoke tracks with pitch control — no terminal needed.

**Architecture:** FastAPI backend wraps the existing yt-dlp + Demucs pipeline, exposes REST + WebSocket APIs. React frontend provides song input (URL/search/file upload), real-time processing status, audio playback with pitch slider (Web Audio API), and pitch-shifted export.

**Tech Stack:** Python 3.13, FastAPI, uvicorn, python-multipart, librosa, soundfile | React 18, Vite, Web Audio API, Tone.js (PitchShift)

---

### Task 1: Backend Project Structure & FastAPI Skeleton

**Files:**
- Create: `backend/main.py`
- Create: `backend/requirements.txt`
- Create: `backend/__init__.py`

**Step 1: Create backend directory and requirements**

```
backend/requirements.txt
```
```txt
fastapi==0.115.0
uvicorn[standard]==0.32.0
python-multipart==0.0.18
websockets==14.2
librosa==0.10.2
soundfile==0.13.1
```

**Step 2: Write the FastAPI app skeleton**

```python
# backend/main.py
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Jiyajale")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

@app.get("/api/health")
def health():
    return {"status": "ok"}
```

```python
# backend/__init__.py
# (empty)
```

**Step 3: Install backend deps and verify server starts**

Run:
```bash
source .venv/bin/activate
pip install fastapi uvicorn python-multipart websockets librosa soundfile
cd /Users/upneja/Projects/jiyajale
python -m uvicorn backend.main:app --reload --port 8000 &
curl http://localhost:8000/api/health
# Expected: {"status":"ok"}
kill %1
```

**Step 4: Commit**

```bash
git add backend/
git commit -m "feat: add FastAPI backend skeleton with health endpoint"
```

---

### Task 2: Song Processing Service (Download + Demucs)

**Files:**
- Create: `backend/processing.py`
- Create: `backend/test_processing.py`

This wraps the logic from `separate.sh` into Python so the backend can call it programmatically and report progress.

**Step 1: Write the failing test**

```python
# backend/test_processing.py
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from backend.processing import process_song, SongResult

def test_process_song_from_url_calls_ytdlp_and_demucs():
    """Verify process_song orchestrates download + separation."""
    with patch("backend.processing.run_ytdlp") as mock_dl, \
         patch("backend.processing.run_demucs") as mock_sep:

        output_dir = Path("/tmp/jiyajale-test")
        mock_dl.return_value = output_dir / "test-song" / "original.wav"
        mock_sep.return_value = SongResult(
            name="test-song",
            original=output_dir / "test-song" / "original.wav",
            instrumental=output_dir / "test-song" / "stems" / "htdemucs_ft" / "original" / "no_vocals.wav",
            vocals=output_dir / "test-song" / "stems" / "htdemucs_ft" / "original" / "vocals.wav",
        )

        result = process_song(
            query="https://youtube.com/watch?v=abc",
            song_name="test-song",
            output_dir=output_dir,
        )

        mock_dl.assert_called_once()
        mock_sep.assert_called_once()
        assert result.name == "test-song"
        assert result.instrumental.name == "no_vocals.wav"


def test_process_song_from_local_file_skips_download():
    """When given a local file path, skip yt-dlp and go straight to demucs."""
    with patch("backend.processing.run_ytdlp") as mock_dl, \
         patch("backend.processing.run_demucs") as mock_sep, \
         patch("backend.processing.convert_to_wav") as mock_conv:

        output_dir = Path("/tmp/jiyajale-test")
        mock_conv.return_value = output_dir / "test-song" / "original.wav"
        mock_sep.return_value = SongResult(
            name="test-song",
            original=output_dir / "test-song" / "original.wav",
            instrumental=output_dir / "test-song" / "stems" / "htdemucs_ft" / "original" / "no_vocals.wav",
            vocals=output_dir / "test-song" / "stems" / "htdemucs_ft" / "original" / "vocals.wav",
        )

        result = process_song(
            local_file=Path("/tmp/song.m4a"),
            song_name="test-song",
            output_dir=output_dir,
        )

        mock_dl.assert_not_called()
        mock_conv.assert_called_once()
        mock_sep.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest backend/test_processing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.processing'`

**Step 3: Implement processing module**

```python
# backend/processing.py
import subprocess
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


@dataclass
class SongResult:
    name: str
    original: Path
    instrumental: Path
    vocals: Path


def run_ytdlp(query: str, song_dir: Path) -> Path:
    """Download audio from YouTube as WAV."""
    song_dir.mkdir(parents=True, exist_ok=True)
    output_path = song_dir / "original.%(ext)s"
    subprocess.run(
        [
            "yt-dlp", "-x",
            "--audio-format", "wav",
            "--audio-quality", "0",
            "-o", str(output_path),
            f"ytsearch1:{query}",
        ],
        check=True,
    )
    return song_dir / "original.wav"


def convert_to_wav(local_file: Path, song_dir: Path) -> Path:
    """Convert a local audio file to WAV using ffmpeg."""
    song_dir.mkdir(parents=True, exist_ok=True)
    dest = song_dir / "original.wav"
    if local_file.suffix.lower() == ".wav":
        shutil.copy2(local_file, dest)
    else:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(local_file), "-ar", "44100", str(dest)],
            check=True,
        )
    return dest


def run_demucs(
    wav_path: Path,
    song_name: str,
    song_dir: Path,
    on_progress: Optional[Callable[[str], None]] = None,
) -> SongResult:
    """Run Demucs htdemucs_ft two-stem separation."""
    stems_dir = song_dir / "stems"
    if on_progress:
        on_progress("Starting AI separation...")

    subprocess.run(
        [
            "python", "-m", "demucs",
            "--two-stems", "vocals",
            "-n", "htdemucs_ft",
            "-o", str(stems_dir),
            str(wav_path),
        ],
        check=True,
    )

    if on_progress:
        on_progress("Separation complete")

    return SongResult(
        name=song_name,
        original=wav_path,
        instrumental=stems_dir / "htdemucs_ft" / "original" / "no_vocals.wav",
        vocals=stems_dir / "htdemucs_ft" / "original" / "vocals.wav",
    )


def process_song(
    query: Optional[str] = None,
    local_file: Optional[Path] = None,
    song_name: str = "output",
    output_dir: Path = Path("output"),
    on_progress: Optional[Callable[[str], None]] = None,
) -> SongResult:
    """Full pipeline: download (or convert) → separate → return paths."""
    song_dir = output_dir / song_name

    # Check if already processed
    expected_instrumental = song_dir / "stems" / "htdemucs_ft" / "original" / "no_vocals.wav"
    if expected_instrumental.exists():
        if on_progress:
            on_progress("Already processed, skipping")
        return SongResult(
            name=song_name,
            original=song_dir / "original.wav",
            instrumental=expected_instrumental,
            vocals=song_dir / "stems" / "htdemucs_ft" / "original" / "vocals.wav",
        )

    # Step 1: Get WAV
    if local_file:
        if on_progress:
            on_progress("Converting local file to WAV...")
        wav_path = convert_to_wav(local_file, song_dir)
    elif query:
        if on_progress:
            on_progress("Downloading from YouTube...")
        wav_path = run_ytdlp(query, song_dir)
    else:
        raise ValueError("Must provide either query or local_file")

    # Step 2: Separate
    return run_demucs(wav_path, song_name, song_dir, on_progress)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/test_processing.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add backend/processing.py backend/test_processing.py
git commit -m "feat: add song processing service wrapping yt-dlp and demucs"
```

---

### Task 3: API Endpoints (Process, List Songs, Serve Audio)

**Files:**
- Modify: `backend/main.py`
- Create: `backend/test_api.py`

**Step 1: Write failing API tests**

```python
# backend/test_api.py
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from pathlib import Path
from backend.main import app
from backend.processing import SongResult

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_songs_empty(tmp_path):
    with patch("backend.main.OUTPUT_DIR", tmp_path):
        r = client.get("/api/songs")
        assert r.status_code == 200
        assert r.json() == []


def test_list_songs_with_processed(tmp_path):
    song_dir = tmp_path / "test-song" / "stems" / "htdemucs_ft" / "original"
    song_dir.mkdir(parents=True)
    (song_dir / "no_vocals.wav").touch()
    (song_dir / "vocals.wav").touch()
    (tmp_path / "test-song" / "original.wav").touch()

    with patch("backend.main.OUTPUT_DIR", tmp_path):
        r = client.get("/api/songs")
        assert r.status_code == 200
        songs = r.json()
        assert len(songs) == 1
        assert songs[0]["name"] == "test-song"
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/test_api.py -v`
Expected: list_songs tests FAIL

**Step 3: Add API endpoints to main.py**

```python
# backend/main.py — replace full contents
import asyncio
import os
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.processing import process_song, SongResult

app = FastAPI(title="Jiyajale")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def slugify(name: str) -> str:
    """Convert song name to kebab-case directory name."""
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/songs")
def list_songs():
    """List all processed songs in output directory."""
    songs = []
    if not OUTPUT_DIR.exists():
        return songs
    for song_dir in sorted(OUTPUT_DIR.iterdir()):
        if not song_dir.is_dir():
            continue
        instrumental = song_dir / "stems" / "htdemucs_ft" / "original" / "no_vocals.wav"
        vocals = song_dir / "stems" / "htdemucs_ft" / "original" / "vocals.wav"
        original = song_dir / "original.wav"
        if instrumental.exists():
            songs.append({
                "name": song_dir.name,
                "has_original": original.exists(),
                "has_instrumental": instrumental.exists(),
                "has_vocals": vocals.exists(),
            })
    return songs


@app.get("/api/audio/{song_name}/{track}")
def serve_audio(song_name: str, track: str):
    """Serve audio files. track is 'original', 'instrumental', or 'vocals'."""
    if track == "original":
        path = OUTPUT_DIR / song_name / "original.wav"
    elif track == "instrumental":
        path = OUTPUT_DIR / song_name / "stems" / "htdemucs_ft" / "original" / "no_vocals.wav"
    elif track == "vocals":
        path = OUTPUT_DIR / song_name / "stems" / "htdemucs_ft" / "original" / "vocals.wav"
    else:
        return {"error": "Invalid track type"}

    if not path.exists():
        return {"error": "File not found"}

    return FileResponse(path, media_type="audio/wav")


@app.post("/api/process")
async def process(
    query: Optional[str] = Form(None),
    song_name: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """Start song processing. Accepts YouTube URL/search or file upload."""
    if not query and not file:
        return {"error": "Provide a YouTube URL/search term or upload a file"}

    # Determine song name
    if not song_name:
        if file:
            song_name = slugify(Path(file.filename).stem)
        elif query:
            song_name = slugify(query[:50])

    local_file = None
    if file:
        # Save uploaded file to temp location
        upload_dir = OUTPUT_DIR / song_name
        upload_dir.mkdir(parents=True, exist_ok=True)
        upload_path = upload_dir / f"upload_{file.filename}"
        with open(upload_path, "wb") as f:
            content = await file.read()
            f.write(content)
        local_file = upload_path

    # Run processing in a thread to avoid blocking
    result = await asyncio.to_thread(
        process_song,
        query=query if not file else None,
        local_file=local_file,
        song_name=song_name,
        output_dir=OUTPUT_DIR,
    )

    return {
        "name": result.name,
        "original": f"/api/audio/{result.name}/original",
        "instrumental": f"/api/audio/{result.name}/instrumental",
        "vocals": f"/api/audio/{result.name}/vocals",
    }
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/test_api.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add backend/main.py backend/test_api.py
git commit -m "feat: add API endpoints for song listing, audio serving, and processing"
```

---

### Task 4: Pitch Shift Endpoint

**Files:**
- Create: `backend/pitch.py`
- Create: `backend/test_pitch.py`
- Modify: `backend/main.py` (add route)

**Step 1: Write failing test**

```python
# backend/test_pitch.py
import numpy as np
from pathlib import Path
from backend.pitch import pitch_shift_audio


def test_pitch_shift_creates_output(tmp_path):
    """Verify pitch shifting produces a valid output file."""
    import soundfile as sf

    # Create a test WAV (1 second of 440Hz sine wave)
    sr = 44100
    t = np.linspace(0, 1, sr, dtype=np.float32)
    audio = np.sin(2 * np.pi * 440 * t)
    input_path = tmp_path / "test.wav"
    sf.write(input_path, audio, sr)

    output_path = tmp_path / "shifted.wav"
    pitch_shift_audio(input_path, output_path, semitones=2)

    assert output_path.exists()
    data, out_sr = sf.read(output_path)
    assert out_sr == sr
    assert len(data) > 0
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest backend/test_pitch.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.pitch'`

**Step 3: Implement pitch shifting**

```python
# backend/pitch.py
from pathlib import Path
import librosa
import soundfile as sf


def pitch_shift_audio(
    input_path: Path,
    output_path: Path,
    semitones: float,
    sr: int = 44100,
) -> Path:
    """Pitch-shift an audio file by N semitones and save to output_path."""
    audio, file_sr = librosa.load(str(input_path), sr=sr, mono=False)

    if semitones != 0:
        # Handle stereo: pitch shift each channel
        if audio.ndim == 2:
            shifted = []
            for ch in audio:
                shifted.append(librosa.effects.pitch_shift(ch, sr=sr, n_steps=semitones))
            import numpy as np
            audio = np.stack(shifted)
        else:
            audio = librosa.effects.pitch_shift(audio, sr=sr, n_steps=semitones)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), audio.T if audio.ndim == 2 else audio, sr)
    return output_path
```

**Step 4: Add endpoint to main.py**

Add this endpoint to `backend/main.py`:

```python
from backend.pitch import pitch_shift_audio

@app.post("/api/pitch-shift")
async def pitch_shift(
    song_name: str = Form(...),
    track: str = Form("instrumental"),
    semitones: float = Form(...),
):
    """Export a pitch-shifted version of a track."""
    if track == "instrumental":
        source = OUTPUT_DIR / song_name / "stems" / "htdemucs_ft" / "original" / "no_vocals.wav"
    elif track == "vocals":
        source = OUTPUT_DIR / song_name / "stems" / "htdemucs_ft" / "original" / "vocals.wav"
    else:
        return {"error": "track must be 'instrumental' or 'vocals'"}

    if not source.exists():
        return {"error": "Source file not found"}

    sign = "+" if semitones >= 0 else ""
    export_dir = OUTPUT_DIR / song_name / "exports"
    export_dir.mkdir(exist_ok=True)
    output_path = export_dir / f"{track}_{sign}{semitones}.wav"

    await asyncio.to_thread(pitch_shift_audio, source, output_path, semitones)

    return FileResponse(output_path, media_type="audio/wav", filename=output_path.name)
```

**Step 5: Run all tests**

Run: `python -m pytest backend/ -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add backend/pitch.py backend/test_pitch.py backend/main.py
git commit -m "feat: add pitch shifting endpoint with librosa"
```

---

### Task 5: WebSocket Progress Streaming

**Files:**
- Modify: `backend/main.py` (add WebSocket endpoint + refactor process to stream)

**Step 1: Add WebSocket status endpoint**

Add to `backend/main.py`:

```python
# In-memory tracking of active jobs
_active_jobs: dict[str, str] = {}  # song_name -> status message


@app.websocket("/ws/status/{song_name}")
async def ws_status(websocket: WebSocket, song_name: str):
    """Stream processing status for a song."""
    await websocket.accept()
    try:
        while True:
            status = _active_jobs.get(song_name)
            if status:
                await websocket.send_json({"status": status})
                if status in ("done", "error"):
                    break
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
```

Update the `/api/process` endpoint to write status:

```python
@app.post("/api/process")
async def process(
    query: Optional[str] = Form(None),
    song_name: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    if not query and not file:
        return {"error": "Provide a YouTube URL/search term or upload a file"}

    if not song_name:
        if file:
            song_name = slugify(Path(file.filename).stem)
        elif query:
            song_name = slugify(query[:50])

    def on_progress(msg: str):
        _active_jobs[song_name] = msg

    local_file = None
    if file:
        upload_dir = OUTPUT_DIR / song_name
        upload_dir.mkdir(parents=True, exist_ok=True)
        upload_path = upload_dir / f"upload_{file.filename}"
        with open(upload_path, "wb") as f:
            content = await file.read()
            f.write(content)
        local_file = upload_path

    on_progress("starting")

    try:
        result = await asyncio.to_thread(
            process_song,
            query=query if not file else None,
            local_file=local_file,
            song_name=song_name,
            output_dir=OUTPUT_DIR,
            on_progress=on_progress,
        )
        on_progress("done")
    except Exception as e:
        on_progress("error")
        return {"error": str(e)}

    return {
        "name": result.name,
        "original": f"/api/audio/{result.name}/original",
        "instrumental": f"/api/audio/{result.name}/instrumental",
        "vocals": f"/api/audio/{result.name}/vocals",
    }
```

**Step 2: Test manually**

Run:
```bash
python -m uvicorn backend.main:app --reload --port 8000
# In another terminal, test WebSocket with websocat or browser console
```

**Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: add WebSocket progress streaming for song processing"
```

---

### Task 6: React Frontend Setup

**Files:**
- Create: `frontend/` (Vite + React project)

**Step 1: Scaffold React app with Vite**

Run:
```bash
cd /Users/upneja/Projects/jiyajale
npm create vite@latest frontend -- --template react
cd frontend
npm install
```

**Step 2: Verify it runs**

Run:
```bash
cd /Users/upneja/Projects/jiyajale/frontend
npm run dev &
curl -s http://localhost:5173 | head -5
kill %1
```

**Step 3: Clean up boilerplate**

- Remove `src/App.css` boilerplate content
- Replace `src/App.jsx` with minimal shell

```jsx
// frontend/src/App.jsx
import { useState } from 'react'
import './App.css'

function App() {
  return (
    <div className="app">
      <h1>Jiyajale</h1>
      <p>Turn any song into karaoke</p>
    </div>
  )
}

export default App
```

**Step 4: Add proxy for API**

```js
// frontend/vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
```

**Step 5: Commit**

```bash
cd /Users/upneja/Projects/jiyajale
git add frontend/
git commit -m "feat: scaffold React frontend with Vite and API proxy"
```

---

### Task 7: Song Input Component

**Files:**
- Create: `frontend/src/components/SongInput.jsx`
- Modify: `frontend/src/App.jsx`

**Step 1: Build SongInput component**

```jsx
// frontend/src/components/SongInput.jsx
import { useState, useRef } from 'react'

export default function SongInput({ onProcess }) {
  const [query, setQuery] = useState('')
  const [songName, setSongName] = useState('')
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const fileRef = useRef()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)

    const formData = new FormData()
    if (file) {
      formData.append('file', file)
    } else {
      formData.append('query', query)
    }
    if (songName) formData.append('song_name', songName)

    try {
      const res = await fetch('/api/process', { method: 'POST', body: formData })
      const data = await res.json()
      if (data.error) {
        alert(data.error)
      } else {
        onProcess(data)
      }
    } catch (err) {
      alert('Processing failed: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    const dropped = e.dataTransfer.files[0]
    if (dropped) {
      setFile(dropped)
      if (!songName) {
        setSongName(dropped.name.replace(/\.[^.]+$/, '').replace(/\s+/g, '-').toLowerCase())
      }
    }
  }

  return (
    <form onSubmit={handleSubmit} className="song-input">
      <div
        className="drop-zone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => fileRef.current?.click()}
      >
        {file ? (
          <p>📁 {file.name}</p>
        ) : (
          <p>Drop an audio file here, or click to browse</p>
        )}
        <input
          ref={fileRef}
          type="file"
          accept="audio/*"
          style={{ display: 'none' }}
          onChange={(e) => {
            setFile(e.target.files[0])
            if (!songName && e.target.files[0]) {
              setSongName(e.target.files[0].name.replace(/\.[^.]+$/, '').replace(/\s+/g, '-').toLowerCase())
            }
          }}
        />
      </div>

      <div className="divider">or</div>

      <input
        type="text"
        placeholder="YouTube URL or song name..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        disabled={!!file}
      />

      <input
        type="text"
        placeholder="Short name (e.g. kisi-ranjish)"
        value={songName}
        onChange={(e) => setSongName(e.target.value)}
      />

      <button type="submit" disabled={loading || (!query && !file)}>
        {loading ? 'Processing...' : 'Separate Vocals'}
      </button>
    </form>
  )
}
```

**Step 2: Wire into App.jsx**

```jsx
// frontend/src/App.jsx
import { useState, useEffect } from 'react'
import SongInput from './components/SongInput'
import './App.css'

function App() {
  const [songs, setSongs] = useState([])
  const [currentSong, setCurrentSong] = useState(null)

  const fetchSongs = async () => {
    const res = await fetch('/api/songs')
    setSongs(await res.json())
  }

  useEffect(() => { fetchSongs() }, [])

  const handleProcess = (result) => {
    setCurrentSong(result)
    fetchSongs()
  }

  return (
    <div className="app">
      <h1>Jiyajale</h1>
      <p className="subtitle">Turn any song into karaoke</p>
      <SongInput onProcess={handleProcess} />

      {songs.length > 0 && (
        <div className="song-library">
          <h2>Processed Songs</h2>
          {songs.map((s) => (
            <button
              key={s.name}
              className="song-item"
              onClick={() => setCurrentSong({
                name: s.name,
                original: `/api/audio/${s.name}/original`,
                instrumental: `/api/audio/${s.name}/instrumental`,
                vocals: `/api/audio/${s.name}/vocals`,
              })}
            >
              {s.name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default App
```

**Step 3: Commit**

```bash
git add frontend/src/
git commit -m "feat: add SongInput component with file upload and YouTube search"
```

---

### Task 8: Audio Player with Pitch Slider

**Files:**
- Create: `frontend/src/components/AudioPlayer.jsx`
- Modify: `frontend/src/App.jsx`

This is the core UX piece. Uses Web Audio API for real-time pitch shifting in the browser.

**Step 1: Install Tone.js for pitch shifting**

Run:
```bash
cd /Users/upneja/Projects/jiyajale/frontend
npm install tone
```

**Step 2: Build AudioPlayer component**

```jsx
// frontend/src/components/AudioPlayer.jsx
import { useState, useRef, useEffect } from 'react'
import * as Tone from 'tone'

export default function AudioPlayer({ song }) {
  const [pitch, setPitch] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [track, setTrack] = useState('instrumental')
  const [exporting, setExporting] = useState(false)
  const playerRef = useRef(null)
  const shifterRef = useRef(null)

  useEffect(() => {
    return () => {
      playerRef.current?.stop()
      playerRef.current?.dispose()
      shifterRef.current?.dispose()
    }
  }, [song, track])

  const getUrl = () => {
    if (track === 'instrumental') return song.instrumental
    if (track === 'vocals') return song.vocals
    return song.original
  }

  const togglePlay = async () => {
    await Tone.start()

    if (playing) {
      playerRef.current?.stop()
      setPlaying(false)
      return
    }

    // Clean up previous
    playerRef.current?.dispose()
    shifterRef.current?.dispose()

    const shifter = new Tone.PitchShift({ pitch }).toDestination()
    const player = new Tone.Player({
      url: getUrl(),
      onload: () => {
        player.start()
        setPlaying(true)
      },
      onstop: () => setPlaying(false),
    }).connect(shifter)

    playerRef.current = player
    shifterRef.current = shifter
  }

  useEffect(() => {
    if (shifterRef.current) {
      shifterRef.current.pitch = pitch
    }
  }, [pitch])

  const handleExport = async () => {
    setExporting(true)
    try {
      const formData = new FormData()
      formData.append('song_name', song.name)
      formData.append('track', track)
      formData.append('semitones', pitch)

      const res = await fetch('/api/pitch-shift', { method: 'POST', body: formData })
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${song.name}_${track}_${pitch >= 0 ? '+' : ''}${pitch}.wav`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="audio-player">
      <h2>{song.name}</h2>

      <div className="track-selector">
        {['instrumental', 'vocals', 'original'].map((t) => (
          <button
            key={t}
            className={track === t ? 'active' : ''}
            onClick={() => {
              setTrack(t)
              if (playing) {
                playerRef.current?.stop()
                setPlaying(false)
              }
            }}
          >
            {t === 'instrumental' ? 'Karaoke' : t === 'vocals' ? 'Vocals Only' : 'Original'}
          </button>
        ))}
      </div>

      <button className="play-btn" onClick={togglePlay}>
        {playing ? 'Stop' : 'Play'}
      </button>

      <div className="pitch-control">
        <label>
          Pitch: {pitch >= 0 ? '+' : ''}{pitch} semitones
        </label>
        <input
          type="range"
          min="-12"
          max="12"
          step="1"
          value={pitch}
          onChange={(e) => setPitch(Number(e.target.value))}
        />
        <button onClick={() => setPitch(0)}>Reset</button>
      </div>

      <button className="export-btn" onClick={handleExport} disabled={exporting}>
        {exporting ? 'Exporting...' : `Export ${track} at ${pitch >= 0 ? '+' : ''}${pitch}`}
      </button>
    </div>
  )
}
```

**Step 3: Wire AudioPlayer into App.jsx**

Add import and render in App.jsx:

```jsx
import AudioPlayer from './components/AudioPlayer'

// In the return, after song library:
{currentSong && <AudioPlayer song={currentSong} />}
```

**Step 4: Commit**

```bash
git add frontend/
git commit -m "feat: add audio player with real-time pitch slider using Tone.js"
```

---

### Task 9: Styling

**Files:**
- Modify: `frontend/src/App.css`
- Modify: `frontend/src/index.css`

**Step 1: Write clean, simple CSS**

```css
/* frontend/src/index.css */
:root {
  --bg: #1a1a2e;
  --surface: #16213e;
  --primary: #e94560;
  --text: #eee;
  --text-muted: #999;
  --border: #333;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
}
```

```css
/* frontend/src/App.css */
.app {
  max-width: 600px;
  margin: 0 auto;
  padding: 2rem 1rem;
}

h1 { font-size: 2rem; }
.subtitle { color: var(--text-muted); margin-bottom: 2rem; }

/* Song Input */
.song-input { display: flex; flex-direction: column; gap: 0.75rem; }
.drop-zone {
  border: 2px dashed var(--border);
  border-radius: 12px;
  padding: 2rem;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s;
}
.drop-zone:hover { border-color: var(--primary); }
.divider { text-align: center; color: var(--text-muted); font-size: 0.85rem; }

input[type="text"] {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.75rem 1rem;
  color: var(--text);
  font-size: 1rem;
}

button {
  background: var(--primary);
  border: none;
  border-radius: 8px;
  padding: 0.75rem 1.5rem;
  color: white;
  font-size: 1rem;
  cursor: pointer;
  transition: opacity 0.2s;
}
button:hover { opacity: 0.9; }
button:disabled { opacity: 0.5; cursor: not-allowed; }

/* Song Library */
.song-library { margin-top: 2rem; }
.song-library h2 { font-size: 1.2rem; margin-bottom: 0.75rem; }
.song-item {
  display: block;
  width: 100%;
  background: var(--surface);
  text-align: left;
  margin-bottom: 0.5rem;
}

/* Audio Player */
.audio-player {
  margin-top: 2rem;
  background: var(--surface);
  border-radius: 12px;
  padding: 1.5rem;
}
.audio-player h2 { margin-bottom: 1rem; }

.track-selector { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
.track-selector button { background: var(--bg); font-size: 0.85rem; }
.track-selector button.active { background: var(--primary); }

.play-btn { width: 100%; font-size: 1.2rem; padding: 1rem; margin-bottom: 1rem; }

.pitch-control {
  display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;
}
.pitch-control label { white-space: nowrap; font-size: 0.9rem; min-width: 160px; }
.pitch-control input[type="range"] { flex: 1; accent-color: var(--primary); }
.pitch-control button { background: var(--bg); font-size: 0.8rem; padding: 0.4rem 0.8rem; }

.export-btn { width: 100%; background: var(--bg); border: 1px solid var(--primary); }
```

**Step 2: Commit**

```bash
git add frontend/src/
git commit -m "feat: add dark theme styling for all components"
```

---

### Task 10: Start Script & Final Integration

**Files:**
- Create: `start.sh`
- Modify: `requirements.txt` (add backend deps)

**Step 1: Create one-command start script**

```bash
#!/bin/bash
# start.sh — Start Jiyajale (backend + frontend)
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

# Backend
source "$DIR/.venv/bin/activate"
echo "Starting backend on http://localhost:8000..."
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Frontend
echo "Starting frontend on http://localhost:3000..."
cd "$DIR/frontend"
npm run dev -- --host --port 3000 &
FRONTEND_PID=$!

echo ""
echo "Jiyajale is running at http://localhost:3000"
echo "Press Ctrl+C to stop"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
```

**Step 2: Update requirements.txt with backend deps**

Append to `requirements.txt`:
```
fastapi==0.115.0
uvicorn[standard]==0.32.0
python-multipart==0.0.18
websockets==14.2
librosa==0.10.2
soundfile==0.13.1
```

**Step 3: Make start.sh executable and test**

Run:
```bash
chmod +x start.sh
./start.sh
# Visit http://localhost:3000 in browser
# Test: type a song name, click process, verify it works
```

**Step 4: Commit**

```bash
git add start.sh requirements.txt
git commit -m "feat: add one-command start script for backend + frontend"
```

---

### Task 11: Final Test & Push

**Step 1: Run all backend tests**

Run: `python -m pytest backend/ -v`
Expected: All pass

**Step 2: Verify frontend builds**

Run:
```bash
cd /Users/upneja/Projects/jiyajale/frontend
npm run build
```
Expected: Build succeeds

**Step 3: Push to GitHub**

```bash
git push origin main
```

---

## Summary

| Task | What | ~Time |
|------|------|-------|
| 1 | FastAPI skeleton | 2 min |
| 2 | Processing service (yt-dlp + Demucs wrapper) | 5 min |
| 3 | API endpoints (process, list, serve audio) | 5 min |
| 4 | Pitch shift endpoint | 3 min |
| 5 | WebSocket progress streaming | 3 min |
| 6 | React frontend scaffold | 2 min |
| 7 | Song input component (URL + file upload) | 5 min |
| 8 | Audio player with pitch slider | 5 min |
| 9 | Styling (dark theme) | 3 min |
| 10 | Start script + integration | 2 min |
| 11 | Final test + push | 2 min |
