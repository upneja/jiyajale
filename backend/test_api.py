"""Tests for the FastAPI endpoints in backend/main.py."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_app(output_dir: Path):
    """Import (or reload) backend.main with OUTPUT_DIR patched to *output_dir*."""
    # Remove cached module so we can patch the module-level OUTPUT_DIR
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("backend.main"):
            del sys.modules[mod_name]

    import backend.main as main_mod
    main_mod.OUTPUT_DIR = output_dir
    return main_mod.app


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_ok(self, tmp_path: Path) -> None:
        app = _get_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# /api/songs
# ---------------------------------------------------------------------------


class TestListSongs:
    def test_empty_output_dir(self, tmp_path: Path) -> None:
        app = _get_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/songs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_song_with_no_stems(self, tmp_path: Path) -> None:
        song_dir = tmp_path / "bare-song"
        song_dir.mkdir()
        (song_dir / "original.wav").write_bytes(b"RIFF")

        app = _get_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/songs")
        data = resp.json()

        assert resp.status_code == 200
        assert len(data) == 1
        song = data[0]
        assert song["name"] == "bare-song"
        assert song["has_original"] is True
        assert song["has_instrumental"] is False
        assert song["has_vocals"] is False

    def test_fully_processed_song(self, tmp_path: Path) -> None:
        song_dir = tmp_path / "full-song"
        song_dir.mkdir()
        (song_dir / "original.wav").write_bytes(b"RIFF")
        stems = song_dir / "stems" / "htdemucs_ft" / "original"
        stems.mkdir(parents=True)
        (stems / "no_vocals.wav").write_bytes(b"RIFF")
        (stems / "vocals.wav").write_bytes(b"RIFF")

        app = _get_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/songs")
        data = resp.json()

        assert resp.status_code == 200
        assert len(data) == 1
        song = data[0]
        assert song["name"] == "full-song"
        assert song["has_original"] is True
        assert song["has_instrumental"] is True
        assert song["has_vocals"] is True

    def test_multiple_songs(self, tmp_path: Path) -> None:
        for name in ["alpha-song", "beta-song"]:
            (tmp_path / name).mkdir()
            (tmp_path / name / "original.wav").write_bytes(b"RIFF")

        app = _get_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/songs")
        names = [s["name"] for s in resp.json()]
        assert "alpha-song" in names
        assert "beta-song" in names


# ---------------------------------------------------------------------------
# /api/audio
# ---------------------------------------------------------------------------


class TestGetAudio:
    def _make_song(self, output_dir: Path) -> None:
        song_dir = output_dir / "test-song"
        song_dir.mkdir(parents=True)
        (song_dir / "original.wav").write_bytes(b"RIFF" + b"\x00" * 44)
        stems = song_dir / "stems" / "htdemucs_ft" / "original"
        stems.mkdir(parents=True)
        (stems / "no_vocals.wav").write_bytes(b"RIFF" + b"\x00" * 44)
        (stems / "vocals.wav").write_bytes(b"RIFF" + b"\x00" * 44)

    def test_serve_original(self, tmp_path: Path) -> None:
        self._make_song(tmp_path)
        app = _get_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/audio/test-song/original")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/wav"

    def test_serve_instrumental(self, tmp_path: Path) -> None:
        self._make_song(tmp_path)
        app = _get_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/audio/test-song/instrumental")
        assert resp.status_code == 200

    def test_serve_vocals(self, tmp_path: Path) -> None:
        self._make_song(tmp_path)
        app = _get_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/audio/test-song/vocals")
        assert resp.status_code == 200

    def test_unknown_track_returns_400(self, tmp_path: Path) -> None:
        self._make_song(tmp_path)
        app = _get_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/audio/test-song/drums")
        assert resp.status_code == 400

    def test_missing_song_returns_404(self, tmp_path: Path) -> None:
        app = _get_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/audio/nonexistent/original")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /api/process
# ---------------------------------------------------------------------------


class TestProcess:
    def _mock_process_song(self, song_dir: Path, song_name: str):
        from backend.processing import SongResult

        stems = song_dir / "stems" / "htdemucs_ft" / "original"
        stems.mkdir(parents=True, exist_ok=True)
        original = song_dir / "original.wav"
        original.write_bytes(b"RIFF")
        instrumental = stems / "no_vocals.wav"
        instrumental.write_bytes(b"RIFF")
        vocals = stems / "vocals.wav"
        vocals.write_bytes(b"RIFF")

        return SongResult(
            name=song_name,
            original=original,
            instrumental=instrumental,
            vocals=vocals,
        )

    def test_process_with_query(self, tmp_path: Path) -> None:
        app = _get_app(tmp_path)
        client = TestClient(app)
        song_name = "test-query-song"

        with patch("backend.main.process_song") as mock_ps:
            mock_ps.return_value = self._mock_process_song(
                tmp_path / song_name, song_name
            )
            resp = client.post(
                "/api/process",
                data={"query": "some song", "song_name": song_name},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == song_name
        assert "original" in data
        assert "instrumental" in data
        assert "vocals" in data

    def test_process_no_query_no_file_returns_400(self, tmp_path: Path) -> None:
        app = _get_app(tmp_path)
        client = TestClient(app)
        resp = client.post("/api/process", data={})
        assert resp.status_code == 400

    def test_process_slugifies_song_name(self, tmp_path: Path) -> None:
        app = _get_app(tmp_path)
        client = TestClient(app)

        with patch("backend.main.process_song") as mock_ps:
            mock_ps.return_value = self._mock_process_song(
                tmp_path / "my-song", "my-song"
            )
            resp = client.post(
                "/api/process",
                data={"query": "test", "song_name": "My Song!!"},
            )

        assert resp.status_code == 200
        # Verify slugified name was passed
        call_kwargs = mock_ps.call_args
        assert call_kwargs.kwargs["song_name"] == "my-song"


# ---------------------------------------------------------------------------
# Slugify helper
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_basic(self) -> None:
        from backend.main import slugify
        assert slugify("Hello World") == "hello-world"

    def test_special_chars(self) -> None:
        from backend.main import slugify
        assert slugify("Kisi Ranjish!!  Ko") == "kisi-ranjish-ko"

    def test_already_slug(self) -> None:
        from backend.main import slugify
        assert slugify("already-slug") == "already-slug"

    def test_numbers(self) -> None:
        from backend.main import slugify
        assert slugify("Track 01") == "track-01"
