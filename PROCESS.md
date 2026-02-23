# Jiyajale - Vocal Separation Tool

## What It Does

Takes any song (by name or YouTube URL), downloads it, and splits it into two tracks: an instrumental (karaoke) version and isolated vocals. Built for mom's YouTube singing channel so she can sing over high-quality instrumentals.

## The Stack

- **yt-dlp** - Downloads audio from YouTube (supports search-by-name or direct URLs)
- **Demucs (htdemucs_ft)** - Facebook/Meta's AI model for music source separation. The `_ft` (fine-tuned) variant is slower but produces the cleanest separation
- **PyTorch with MPS** - Runs the AI model on Apple Silicon GPU for faster processing
- **ffmpeg** - Handles audio format conversion under the hood

## Setup (One-Time)

Created a Python virtual environment and installed everything:

```bash
cd ~/Projects/jiyajale
python3.13 -m venv .venv
source .venv/bin/activate
pip install yt-dlp demucs torchcodec
```

`demucs` pulls in PyTorch automatically. `torchcodec` was needed as an extra dependency for newer versions of torchaudio to save WAV files.

## How It Works

Everything is wrapped in `separate.sh`. Running:

```bash
./separate.sh "Kisi Ranjish Ko Hawa Do Keh Main Zinda Hoon Abhi" "kisi-ranjish"
```

Does three things:

1. **Download** - yt-dlp searches YouTube for the query, picks the top result, and downloads it as lossless WAV audio
2. **Separate** - Demucs loads 4 neural network models (htdemucs_ft is a bag of 4), processes the audio in ~6 second chunks, and outputs two stems: vocals and everything else
3. **Save** - Results go into `output/<song-name>/` with the original, instrumental, and vocals all as WAV files

## Output Structure

```
output/kisi-ranjish/
  original.wav                              # Source audio from YouTube
  stems/htdemucs_ft/original/
    no_vocals.wav                           # Instrumental - sing over this
    vocals.wav                              # Isolated vocals - use as reference
```

## Processing a New Song

```bash
# By search term
./separate.sh "Chupke Chupke Raat Din Ghulam Ali" "chupke-chupke"

# By YouTube URL
./separate.sh "https://youtube.com/watch?v=..." "song-name"
```

Takes roughly 6-7 minutes per song on the M4 Mac (most of that is the AI separation, download is seconds).

## Key Decisions

- **WAV throughout** - No lossy compression at any stage. CD-quality instrumentals.
- **htdemucs_ft over htdemucs** - ~4x slower but audibly better vocal removal, worth it for singing tracks.
- **`--two-stems vocals`** - Only splits into vocals + instrumental (not the full 4-stem drums/bass/vocals/other), which is all we need and keeps it simple.
- **ytsearch1:** prefix - Lets yt-dlp accept both search queries and direct URLs seamlessly.
