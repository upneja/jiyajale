"""Pitch-shifting utility using librosa + soundfile."""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np
import soundfile as sf


def pitch_shift_audio(
    input_path: Path,
    output_path: Path,
    semitones: float,
    sr: int = 44100,
) -> None:
    """Load *input_path*, shift pitch by *semitones*, write to *output_path*.

    Supports mono and stereo audio.  For stereo each channel is shifted
    independently so that phase relationships are preserved.

    Parameters
    ----------
    input_path:
        Source WAV file.
    output_path:
        Destination WAV file (will be created/overwritten).
    semitones:
        Number of semitones to shift (positive = up, negative = down).
    sr:
        Sample rate to use when loading the audio.  Librosa will resample
        to this rate if the file has a different native rate.
    """
    # Load audio – librosa returns (samples, sr) for mono, shape (samples,)
    # Use mono=False to preserve stereo as shape (channels, samples).
    audio, file_sr = librosa.load(str(input_path), sr=sr, mono=False)

    if audio.ndim == 1:
        # Mono: shift directly
        shifted = librosa.effects.pitch_shift(audio, sr=sr, n_steps=semitones)
    else:
        # Stereo (or multi-channel): shift each channel independently
        shifted_channels = [
            librosa.effects.pitch_shift(channel, sr=sr, n_steps=semitones)
            for channel in audio
        ]
        shifted = np.stack(shifted_channels, axis=0)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # soundfile expects shape (samples,) for mono or (samples, channels) for stereo
    if shifted.ndim == 1:
        sf.write(str(output_path), shifted, sr, subtype="PCM_16")
    else:
        # Transpose from (channels, samples) -> (samples, channels)
        sf.write(str(output_path), shifted.T, sr, subtype="PCM_16")
