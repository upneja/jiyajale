# Jiyajale

Turn any song into a karaoke track. Paste a YouTube URL, type a song name, or drop in a local file — Jiyajale strips the vocals using Meta's Demucs AI and hands you a studio-quality instrumental.

Built for my mom's YouTube singing channel so she can sing over clean instrumentals of her favorite ghazals and Bollywood songs.

---

## What it does

Jiyajale runs a two-stage pipeline:

1. **Acquire** — download from YouTube via yt-dlp (search by name or URL), or convert a local file (iTunes/ALAC) via ffmpeg
2. **Separate** — run [Demucs htdemucs_ft](https://github.com/facebookresearch/demucs) (Meta's fine-tuned 4-model ensemble) to split the audio into `no_vocals.wav` and `vocals.wav`

Everything stays lossless WAV throughout — no lossy compression at any stage.

```
output/kisi-ranjish/
  original.wav                          — downloaded/converted source
  stems/htdemucs_ft/original/
    no_vocals.wav                       — instrumental  (sing over this)
    vocals.wav                          — isolated vocals  (use as reference)
```

Processing takes ~6–7 minutes per song on an M4 Mac (Apple Silicon MPS acceleration).

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                       Input                             │
│   YouTube URL / Search Query      Local File (ALAC/MP3) │
└────────────────┬────────────────────────────┬───────────┘
                 │                            │
           yt-dlp download             ffmpeg convert
                 │                            │
                 └────────────┬───────────────┘
                              │
                         original.wav
                              │
                   Demucs htdemucs_ft
                   (4 neural networks)
                   MPS GPU on Apple Silicon
                              │
               ┌──────────────┴──────────────┐
               │                             │
        no_vocals.wav                    vocals.wav
        (Instrumental)               (Isolated vocals)
```

**Phase 2 — Web UI** (fully implemented, ships in Docker):

```
React (Vite) → FastAPI → Demucs pipeline
                  ↓
           WebSocket progress updates
           Pitch-shift export (librosa)
           Song library browser
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI separation | [Demucs](https://github.com/facebookresearch/demucs) `htdemucs_ft` — fine-tuned 4-model ensemble |
| GPU acceleration | PyTorch 2.10 + MPS (Apple Silicon) / CPU (Docker/Railway) |
| YouTube download | [yt-dlp](https://github.com/yt-dlp/yt-dlp) — search-by-name or direct URL |
| Audio conversion | ffmpeg |
| Pitch shifting | librosa |
| Backend API | FastAPI + WebSocket progress streaming |
| Frontend | React 19, Vite, Tone.js |
| Container | Docker (CPU PyTorch build for deployment) |
| Deploy target | Railway |

---

## Quick Start — CLI

### Prerequisites

- Python 3.13+
- ffmpeg — `brew install ffmpeg`
- ~2 GB disk for PyTorch + Demucs models (downloaded on first run)

### Setup

```bash
git clone https://github.com/upneja/jiyajale.git
cd jiyajale
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run

```bash
# By song name (yt-dlp searches YouTube for the top result)
./separate.sh "Chupke Chupke Raat Din Ghulam Ali" "chupke-chupke"

# By YouTube URL
./separate.sh "https://youtube.com/watch?v=..." "song-name"
```

---

## Quick Start — Web UI

### Local development

```bash
# Backend (from repo root, venv active)
uvicorn backend.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev        # → http://localhost:5173
```

### Docker (production)

```bash
docker build -t jiyajale .
docker run -p 8000:8000 jiyajale
# → http://localhost:8000
```

The Docker build uses a CPU-only PyTorch image to keep the container lean. Set `DEMUCS_MODEL=htdemucs` (env var) for the faster single-model variant if processing time is a constraint.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/songs` | List all processed songs |
| `POST` | `/api/process` | Submit a song (form: `query` or file upload + optional `song_name`) |
| `GET` | `/api/jobs/{song_name}` | Poll processing status |
| `GET` | `/api/audio/{song_name}/{track}` | Stream audio (`original` \| `instrumental` \| `vocals`) |
| `POST` | `/api/pitch-shift` | Export pitch-shifted track (form: `song_name`, `track`, `semitones`) |
| `WS` | `/ws/status/{song_name}` | WebSocket — real-time progress during separation |

---

## Key Design Decisions

**`htdemucs_ft` over `htdemucs`** — The fine-tuned variant runs 4 neural network passes instead of 1, which is ~4× slower but produces audibly cleaner vocal removal. The residual bleed on the standard model was noticeable when singing over it; `_ft` is not.

**WAV throughout** — Lossless at every stage. Lossy intermediate formats would degrade the separation quality and the final output.

**`--two-stems vocals`** — Only splits into vocals + everything-else. The full four-stem output (drums / bass / vocals / other) isn't needed here and would be slower.

**`ytsearch1:` prefix** — Lets yt-dlp accept both a raw search query and a direct URL through the same code path.

**MPS on Apple Silicon, CPU in Docker** — The local workflow uses PyTorch MPS for GPU acceleration. The Docker build installs the smaller CPU-only wheel to keep image size manageable and avoid CUDA dependencies on the deploy target.

---

## Project Structure

```
jiyajale/
├── separate.sh          — CLI entry point (download + separate)
├── requirements.txt     — Python dependencies (pip freeze)
├── Dockerfile           — Multi-stage build: Python + Node + ffmpeg
├── railway.json         — Railway deploy config
├── backend/
│   ├── main.py          — FastAPI app, endpoints, WebSocket
│   ├── processing.py    — yt-dlp download + Demucs separation pipeline
│   ├── pitch.py         — Pitch-shift via librosa
│   └── test_*.py        — pytest test suite
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── components/
│   │       ├── SongInput.jsx   — URL / search / file upload
│   │       └── AudioPlayer.jsx — Playback with pitch slider
│   └── package.json
├── docs/plans/          — Design docs and implementation plans
├── PROCESS.md           — Technical one-pager
└── WALKTHROUGH.md       — How this was built with Claude Code
```

---

## Background

Built in ~15 minutes using [Claude Code](https://claude.com/claude-code). See [WALKTHROUGH.md](WALKTHROUGH.md) for the full build story — every prompt, every error, everything Claude did autonomously. See [PROCESS.md](PROCESS.md) for technical details.

---

## License

MIT
