"""Tests for backend/pitch.py using synthetic sine-wave audio."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from backend.pitch import pitch_shift_audio


SR = 44100


def _make_sine(path: Path, freq: float = 440.0, duration: float = 0.5, channels: int = 1) -> None:
    """Write a sine-wave WAV file to *path*."""
    t = np.linspace(0, duration, int(SR * duration), endpoint=False)
    wave = (np.sin(2 * np.pi * freq * t) * 0.5).astype(np.float32)
    if channels == 2:
        stereo = np.stack([wave, wave], axis=-1)  # (samples, 2)
        sf.write(str(path), stereo, SR, subtype="PCM_16")
    else:
        sf.write(str(path), wave, SR, subtype="PCM_16")


class TestPitchShiftAudio:
    def test_mono_output_exists(self, tmp_path: Path) -> None:
        src = tmp_path / "mono.wav"
        dst = tmp_path / "mono_shifted.wav"
        _make_sine(src, channels=1)

        pitch_shift_audio(src, dst, semitones=2)

        assert dst.exists()

    def test_mono_same_length(self, tmp_path: Path) -> None:
        src = tmp_path / "mono.wav"
        dst = tmp_path / "mono_shifted.wav"
        _make_sine(src, channels=1)

        pitch_shift_audio(src, dst, semitones=2)

        orig, _ = sf.read(str(src))
        shifted, _ = sf.read(str(dst))
        # librosa may slightly alter length; allow 1% tolerance
        assert abs(len(shifted) - len(orig)) <= max(1, int(len(orig) * 0.01))

    def test_stereo_output_exists(self, tmp_path: Path) -> None:
        src = tmp_path / "stereo.wav"
        dst = tmp_path / "stereo_shifted.wav"
        _make_sine(src, channels=2)

        pitch_shift_audio(src, dst, semitones=-3)

        assert dst.exists()

    def test_stereo_has_two_channels(self, tmp_path: Path) -> None:
        src = tmp_path / "stereo.wav"
        dst = tmp_path / "stereo_shifted.wav"
        _make_sine(src, channels=2)

        pitch_shift_audio(src, dst, semitones=1)

        data, _ = sf.read(str(dst))
        assert data.ndim == 2
        assert data.shape[1] == 2

    def test_zero_semitones_roundtrip(self, tmp_path: Path) -> None:
        """Shifting by 0 semitones should produce audio of the same shape."""
        src = tmp_path / "zero.wav"
        dst = tmp_path / "zero_shifted.wav"
        _make_sine(src, channels=1)

        pitch_shift_audio(src, dst, semitones=0)

        orig, _ = sf.read(str(src))
        shifted, _ = sf.read(str(dst))
        assert shifted.shape == orig.shape

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        src = tmp_path / "mono.wav"
        dst = tmp_path / "deep" / "nested" / "out.wav"
        _make_sine(src, channels=1)

        pitch_shift_audio(src, dst, semitones=1)

        assert dst.exists()

    def test_negative_semitones(self, tmp_path: Path) -> None:
        src = tmp_path / "neg.wav"
        dst = tmp_path / "neg_shifted.wav"
        _make_sine(src, channels=1)

        pitch_shift_audio(src, dst, semitones=-5)

        assert dst.exists()
