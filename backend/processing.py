"""Song processing pipeline: download via yt-dlp and separate with Demucs."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class SongResult:
    """Paths for the three output tracks produced by the pipeline."""

    name: str
    original: Path
    instrumental: Path
    vocals: Path


# ---------------------------------------------------------------------------
# Step helpers
# ---------------------------------------------------------------------------


def run_ytdlp(query: str, song_dir: Path) -> Path:
    """Download the best audio matching *query* as WAV into *song_dir*.

    Returns the path to the downloaded ``original.wav``.
    """
    song_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(song_dir / "original.%(ext)s")
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-x",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "-o", output_template,
        f"ytsearch1:{query}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"yt-dlp failed (exit {result.returncode}):\n{result.stderr}"
        )
    wav_path = song_dir / "original.wav"
    if not wav_path.exists():
        raise FileNotFoundError(
            f"yt-dlp did not produce {wav_path}. stdout:\n{result.stdout}"
        )
    return wav_path


def convert_to_wav(local_file: Path, song_dir: Path) -> Path:
    """Convert *local_file* to ``original.wav`` inside *song_dir* via ffmpeg.

    Returns the path to the converted ``original.wav``.
    """
    song_dir.mkdir(parents=True, exist_ok=True)
    wav_path = song_dir / "original.wav"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(local_file),
        "-ar", "44100",
        "-ac", "2",
        str(wav_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit {result.returncode}):\n{result.stderr}"
        )
    if not wav_path.exists():
        raise FileNotFoundError(f"ffmpeg did not produce {wav_path}")
    return wav_path


def run_demucs(
    wav_path: Path,
    song_name: str,
    song_dir: Path,
    on_progress: Optional[Callable[[str, float], None]] = None,
) -> tuple[Path, Path]:
    """Run Demucs ``htdemucs_ft`` two-stem separation on *wav_path*.

    Demucs writes stems to::

        {song_dir}/stems/htdemucs_ft/{wav_stem}/no_vocals.wav
        {song_dir}/stems/htdemucs_ft/{wav_stem}/vocals.wav

    Because the input file is always saved as ``original.wav`` the stem
    sub-directory is always named ``original``.

    Returns ``(instrumental_path, vocals_path)``.
    """
    stems_dir = song_dir / "stems"
    stems_dir.mkdir(parents=True, exist_ok=True)

    if on_progress:
        on_progress("separating", 0.0)

    cmd = [
        sys.executable, "-m", "demucs",
        "--two-stems", "vocals",
        "-n", "htdemucs_ft",
        "-o", str(stems_dir),
        str(wav_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"demucs failed (exit {result.returncode}):\n{result.stderr}"
        )

    stem = wav_path.stem  # "original"
    base = stems_dir / "htdemucs_ft" / stem
    instrumental = base / "no_vocals.wav"
    vocals = base / "vocals.wav"

    for path in (instrumental, vocals):
        if not path.exists():
            raise FileNotFoundError(f"Demucs did not produce {path}")

    if on_progress:
        on_progress("separating", 100.0)

    return instrumental, vocals


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


def process_song(
    query: Optional[str],
    local_file: Optional[Path],
    song_name: str,
    output_dir: Path,
    on_progress: Optional[Callable[[str, float], None]] = None,
) -> SongResult:
    """Run the full download + separation pipeline for a song.

    If the instrumental track already exists the function returns immediately
    without re-downloading or re-separating (idempotent).

    Priority: if *local_file* is provided it is used; otherwise *query* is
    used to search YouTube via yt-dlp.
    """
    song_dir = output_dir / song_name
    original_wav = song_dir / "original.wav"
    instrumental_path = (
        song_dir / "stems" / "htdemucs_ft" / "original" / "no_vocals.wav"
    )
    vocals_path = song_dir / "stems" / "htdemucs_ft" / "original" / "vocals.wav"

    # Early exit if already processed
    if instrumental_path.exists() and vocals_path.exists():
        if on_progress:
            on_progress("done", 100.0)
        return SongResult(
            name=song_name,
            original=original_wav,
            instrumental=instrumental_path,
            vocals=vocals_path,
        )

    # Step 1: acquire the WAV source
    if local_file is not None:
        if on_progress:
            on_progress("converting", 10.0)
        wav = convert_to_wav(local_file, song_dir)
    elif query:
        if on_progress:
            on_progress("downloading", 10.0)
        wav = run_ytdlp(query, song_dir)
    else:
        raise ValueError("Either 'query' or 'local_file' must be provided.")

    if on_progress:
        on_progress("downloaded", 40.0)

    # Step 2: run Demucs
    instrumental, vocals = run_demucs(wav, song_name, song_dir, on_progress)

    return SongResult(
        name=song_name,
        original=wav,
        instrumental=instrumental,
        vocals=vocals,
    )
