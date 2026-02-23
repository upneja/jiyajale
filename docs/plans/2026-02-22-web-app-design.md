# Jiyajale Web App - Design Document

**Date:** 2026-02-22
**Status:** Approved

## Goal

Replace the CLI (`separate.sh`) with a local web app that mom can use without touching the terminal. Simple converter UX with real-time pitch control and export.

## Input Sources

1. **YouTube URL or search term** - Same as current CLI
2. **Local file upload** - Drag & drop iTunes purchases (AAC/ALAC/MP3/WAV). ffmpeg converts to WAV if needed. Lossless iTunes files produce better results than YouTube downloads.

## Architecture

```
React Frontend (localhost:3000)
├── Song Input (URL / search / file upload)
├── Processing Status (real-time via WebSocket)
├── Audio Player (Web Audio API with pitch slider)
└── Export Button (download pitch-shifted file)
        │
        │ REST + WebSocket
        ▼
FastAPI Backend (localhost:8000)
├── POST /api/process        ← Accept URL/search/file, start separation
├── GET  /api/songs          ← List all processed songs
├── POST /api/pitch-shift    ← Export file with baked pitch
├── WS   /ws/status          ← Stream processing progress
└── GET  /api/audio/{path}   ← Serve audio files for playback
        │
        ▼
Processing Layer
├── yt-dlp (download from YouTube)
├── ffmpeg (convert local files to WAV)
├── Demucs htdemucs_ft (AI separation)
└── librosa (pitch shifting for export)
```

## Frontend Design

**Simple converter layout:**
1. Input area at top - text field for URL/search, or file drop zone
2. "Process" button → shows progress bar with WebSocket updates
3. Once done: audio player appears with three tracks (original, instrumental, vocals)
4. Pitch slider (-12 to +12 semitones) affects playback in real-time via Web Audio API
5. Export button downloads the instrumental at the current pitch setting

**Tech:** React, Web Audio API for real-time pitch, simple CSS (no heavy UI framework needed)

## Backend Design

**FastAPI** with:
- Background task processing (Demucs runs in a thread/process pool)
- WebSocket endpoint for progress streaming
- File serving for audio playback
- `librosa` for pitch-shifted export (bakes pitch into new WAV/MP3)

**Processing flow:**
1. Receive request (URL, search term, or uploaded file)
2. If YouTube: download via yt-dlp
3. If local file: convert to WAV via ffmpeg if needed
4. Run Demucs separation
5. Stream progress to frontend via WebSocket
6. Save results to `output/<song-name>/`

## Pitch Shifting

- **Real-time preview:** Web Audio API `AudioBufferSourceNode.playbackRate` or `PitchShifter` (Tone.js) in the browser. Zero latency, non-destructive.
- **Export:** `librosa.effects.pitch_shift()` on the backend. Produces a new file at the chosen semitone offset.

## File Storage

Same structure as current CLI:
```
output/<song-name>/
  original.wav
  stems/htdemucs_ft/original/
    no_vocals.wav
    vocals.wav
  exports/                    ← NEW: pitch-shifted exports
    no_vocals_+2.wav
```

## Optimizations

- Skip re-processing if song already exists in output/
- Accept lossless local files for better quality than YouTube
- Background processing so UI stays responsive
- Cache Demucs model in memory between requests

## Out of Scope (for now)

- Queue/batch processing
- User accounts or authentication
- Tempo adjustment
- Lyrics display
- Mobile optimization
