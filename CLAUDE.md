# Jiyajale - Project Context

## What This Is

A vocal separation tool that turns any song into karaoke tracks. Downloads audio (from YouTube or local files), uses Meta's Demucs AI to split vocals from instrumentals. Built for mom's YouTube singing channel.

## Tech Stack

- **Python 3.13** - Runtime (Homebrew-managed)
- **Demucs 4.0.1 (htdemucs_ft)** - AI music source separation. Fine-tuned variant: slower but best quality
- **PyTorch 2.10 with MPS** - GPU acceleration on Apple Silicon (M4 Mac)
- **yt-dlp** - YouTube audio download (search-by-name or direct URL)
- **ffmpeg** - Audio format conversion (system dependency)
- **FastAPI** - Backend API server (Phase 2)
- **React** - Frontend UI (Phase 2)

## Key Architecture Decisions

- **WAV throughout** - No lossy compression at any stage. CD-quality audio.
- **htdemucs_ft over htdemucs** - ~4x slower but audibly cleaner separation. Worth it for singing.
- **--two-stems vocals** - Only vocals + instrumental split (not full 4-stem). All we need.
- **ytsearch1: prefix** - Lets yt-dlp handle both search queries and direct URLs with one code path.

## Project Structure

```
jiyajale/
  separate.sh          # CLI entry point - downloads and separates a song
  requirements.txt     # Python dependencies (pip freeze)
  PROCESS.md           # Technical one-pager on how the tool works
  WALKTHROUGH.md       # Story of building this with Claude Code
  output/              # Generated audio files (gitignored)
    <song-name>/
      original.wav
      stems/htdemucs_ft/original/
        no_vocals.wav  # Instrumental - sing over this
        vocals.wav     # Isolated vocals
  docs/plans/          # Design docs and implementation plans
```

## Conventions

- Song directories use kebab-case names (e.g., `kisi-ranjish`)
- All audio stored as lossless WAV
- Shell scripts for CLI workflows, Python for processing logic
- Design docs go in `docs/plans/` with date prefix

## Development

```bash
# Activate virtual environment
source .venv/bin/activate

# Process a song (current CLI)
./separate.sh "Song Name or YouTube URL" "short-name"

# Install dependencies
pip install -r requirements.txt
```

## Current Phase

Phase 1 (CLI tool) is complete. Phase 2 (local web app with FastAPI + React) is planned - see `docs/plans/` for the design doc.
