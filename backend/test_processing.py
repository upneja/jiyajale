"""Tests for backend/processing.py – all subprocess calls are mocked."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.processing import (
    SongResult,
    convert_to_wav,
    process_song,
    run_demucs,
    run_ytdlp,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_completed(returncode: int = 0, stdout: str = "", stderr: str = ""):
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


# ---------------------------------------------------------------------------
# run_ytdlp
# ---------------------------------------------------------------------------


class TestRunYtdlp:
    def test_success(self, tmp_path: Path) -> None:
        song_dir = tmp_path / "my-song"

        def fake_run(cmd, **kwargs):
            # Simulate yt-dlp creating the file
            (song_dir / "original.wav").parent.mkdir(parents=True, exist_ok=True)
            (song_dir / "original.wav").write_bytes(b"RIFF")
            return _fake_completed(0)

        with patch("backend.processing.subprocess.run", side_effect=fake_run):
            result = run_ytdlp("some query", song_dir)

        assert result == song_dir / "original.wav"
        assert result.exists()

    def test_failure_raises(self, tmp_path: Path) -> None:
        song_dir = tmp_path / "my-song"

        with patch(
            "backend.processing.subprocess.run",
            return_value=_fake_completed(1, stderr="yt-dlp error"),
        ):
            with pytest.raises(RuntimeError, match="yt-dlp failed"):
                run_ytdlp("bad query", song_dir)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        song_dir = tmp_path / "my-song"

        with patch(
            "backend.processing.subprocess.run",
            return_value=_fake_completed(0),
        ):
            with pytest.raises(FileNotFoundError):
                run_ytdlp("query", song_dir)


# ---------------------------------------------------------------------------
# convert_to_wav
# ---------------------------------------------------------------------------


class TestConvertToWav:
    def test_success(self, tmp_path: Path) -> None:
        song_dir = tmp_path / "my-song"
        local_file = tmp_path / "song.mp3"
        local_file.write_bytes(b"fake mp3")

        def fake_run(cmd, **kwargs):
            song_dir.mkdir(parents=True, exist_ok=True)
            (song_dir / "original.wav").write_bytes(b"RIFF")
            return _fake_completed(0)

        with patch("backend.processing.subprocess.run", side_effect=fake_run):
            result = convert_to_wav(local_file, song_dir)

        assert result == song_dir / "original.wav"
        assert result.exists()

    def test_ffmpeg_failure_raises(self, tmp_path: Path) -> None:
        song_dir = tmp_path / "my-song"
        local_file = tmp_path / "bad.mp3"
        local_file.write_bytes(b"bad")

        with patch(
            "backend.processing.subprocess.run",
            return_value=_fake_completed(1, stderr="ffmpeg error"),
        ):
            with pytest.raises(RuntimeError, match="ffmpeg failed"):
                convert_to_wav(local_file, song_dir)

    def test_missing_output_raises(self, tmp_path: Path) -> None:
        song_dir = tmp_path / "my-song"
        local_file = tmp_path / "song.mp3"
        local_file.write_bytes(b"data")

        with patch(
            "backend.processing.subprocess.run",
            return_value=_fake_completed(0),
        ):
            with pytest.raises(FileNotFoundError):
                convert_to_wav(local_file, song_dir)


# ---------------------------------------------------------------------------
# run_demucs
# ---------------------------------------------------------------------------


class TestRunDemucs:
    def _make_stems(self, song_dir: Path) -> tuple[Path, Path]:
        stems_base = song_dir / "stems" / "htdemucs_ft" / "original"
        stems_base.mkdir(parents=True, exist_ok=True)
        instrumental = stems_base / "no_vocals.wav"
        vocals = stems_base / "vocals.wav"
        instrumental.write_bytes(b"RIFF")
        vocals.write_bytes(b"RIFF")
        return instrumental, vocals

    def test_success(self, tmp_path: Path) -> None:
        song_dir = tmp_path / "my-song"
        wav_path = song_dir / "original.wav"
        song_dir.mkdir(parents=True)
        wav_path.write_bytes(b"RIFF")

        def fake_run(cmd, **kwargs):
            self._make_stems(song_dir)
            return _fake_completed(0)

        progress_calls: list[tuple] = []
        with patch("backend.processing.subprocess.run", side_effect=fake_run):
            instrumental, vocals = run_demucs(
                wav_path,
                "my-song",
                song_dir,
                on_progress=lambda s, p: progress_calls.append((s, p)),
            )

        assert instrumental.name == "no_vocals.wav"
        assert vocals.name == "vocals.wav"
        assert instrumental.exists()
        assert vocals.exists()
        # progress called at start and end
        assert progress_calls[0] == ("separating", 0.0)
        assert progress_calls[-1] == ("separating", 100.0)

    def test_demucs_failure_raises(self, tmp_path: Path) -> None:
        song_dir = tmp_path / "my-song"
        wav_path = song_dir / "original.wav"
        song_dir.mkdir(parents=True)
        wav_path.write_bytes(b"RIFF")

        with patch(
            "backend.processing.subprocess.run",
            return_value=_fake_completed(1, stderr="GPU error"),
        ):
            with pytest.raises(RuntimeError, match="demucs failed"):
                run_demucs(wav_path, "my-song", song_dir)

    def test_missing_stems_raises(self, tmp_path: Path) -> None:
        song_dir = tmp_path / "my-song"
        wav_path = song_dir / "original.wav"
        song_dir.mkdir(parents=True)
        wav_path.write_bytes(b"RIFF")

        with patch(
            "backend.processing.subprocess.run",
            return_value=_fake_completed(0),
        ):
            with pytest.raises(FileNotFoundError):
                run_demucs(wav_path, "my-song", song_dir)


# ---------------------------------------------------------------------------
# process_song
# ---------------------------------------------------------------------------


class TestProcessSong:
    def _populate(self, song_dir: Path) -> tuple[Path, Path, Path]:
        song_dir.mkdir(parents=True, exist_ok=True)
        original = song_dir / "original.wav"
        original.write_bytes(b"RIFF")
        stems_base = song_dir / "stems" / "htdemucs_ft" / "original"
        stems_base.mkdir(parents=True, exist_ok=True)
        instrumental = stems_base / "no_vocals.wav"
        vocals = stems_base / "vocals.wav"
        instrumental.write_bytes(b"RIFF")
        vocals.write_bytes(b"RIFF")
        return original, instrumental, vocals

    def test_skip_if_already_processed(self, tmp_path: Path) -> None:
        song_dir = tmp_path / "my-song"
        _, instrumental, vocals = self._populate(song_dir)

        progress: list[tuple] = []
        with patch("backend.processing.subprocess.run") as mock_run:
            result = process_song(
                query="anything",
                local_file=None,
                song_name="my-song",
                output_dir=tmp_path,
                on_progress=lambda s, p: progress.append((s, p)),
            )

        # No subprocess calls should have been made
        mock_run.assert_not_called()
        assert result.name == "my-song"
        assert result.instrumental == instrumental
        assert result.vocals == vocals
        assert ("done", 100.0) in progress

    def test_query_path(self, tmp_path: Path) -> None:
        song_dir = tmp_path / "new-song"

        call_count = {"n": 0}

        def fake_run(cmd, **kwargs):
            n = call_count["n"]
            call_count["n"] += 1
            if n == 0:
                # yt-dlp call
                song_dir.mkdir(parents=True, exist_ok=True)
                (song_dir / "original.wav").write_bytes(b"RIFF")
            else:
                # demucs call
                stems_base = song_dir / "stems" / "htdemucs_ft" / "original"
                stems_base.mkdir(parents=True, exist_ok=True)
                (stems_base / "no_vocals.wav").write_bytes(b"RIFF")
                (stems_base / "vocals.wav").write_bytes(b"RIFF")
            return _fake_completed(0)

        with patch("backend.processing.subprocess.run", side_effect=fake_run):
            result = process_song(
                query="some song query",
                local_file=None,
                song_name="new-song",
                output_dir=tmp_path,
            )

        assert isinstance(result, SongResult)
        assert result.name == "new-song"

    def test_local_file_path(self, tmp_path: Path) -> None:
        song_dir = tmp_path / "local-song"
        local_file = tmp_path / "song.mp3"
        local_file.write_bytes(b"fake mp3")

        call_count = {"n": 0}

        def fake_run(cmd, **kwargs):
            n = call_count["n"]
            call_count["n"] += 1
            if n == 0:
                # ffmpeg call
                song_dir.mkdir(parents=True, exist_ok=True)
                (song_dir / "original.wav").write_bytes(b"RIFF")
            else:
                # demucs call
                stems_base = song_dir / "stems" / "htdemucs_ft" / "original"
                stems_base.mkdir(parents=True, exist_ok=True)
                (stems_base / "no_vocals.wav").write_bytes(b"RIFF")
                (stems_base / "vocals.wav").write_bytes(b"RIFF")
            return _fake_completed(0)

        with patch("backend.processing.subprocess.run", side_effect=fake_run):
            result = process_song(
                query=None,
                local_file=local_file,
                song_name="local-song",
                output_dir=tmp_path,
            )

        assert result.name == "local-song"

    def test_no_query_no_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Either"):
            process_song(
                query=None,
                local_file=None,
                song_name="oops",
                output_dir=tmp_path,
            )
