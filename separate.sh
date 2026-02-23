#!/bin/bash
# Usage: ./separate.sh <youtube-url-or-search-term> [song-name]
#
# Examples:
#   ./separate.sh "https://youtube.com/watch?v=..." "kisi-ranjish"
#   ./separate.sh "Kisi Ranjish Ko Hawa Do Jagjit Singh" "kisi-ranjish"

VENV_DIR="$(dirname "$0")/.venv"
OUTPUT_DIR="$(dirname "$0")/output"
source "$VENV_DIR/bin/activate"

QUERY="$1"
SONG_NAME="${2:-output}"

mkdir -p "$OUTPUT_DIR/$SONG_NAME"

# Step 1: Download best audio
echo ">>> Downloading audio..."
yt-dlp -x --audio-format wav --audio-quality 0 \
  -o "$OUTPUT_DIR/$SONG_NAME/original.%(ext)s" \
  "ytsearch1:$QUERY"

# Step 2: Separate stems using Demucs htdemucs_ft (best quality model)
echo ">>> Separating vocals from instrumental..."
python -m demucs --two-stems vocals \
  -n htdemucs_ft \
  -o "$OUTPUT_DIR/$SONG_NAME/stems" \
  "$OUTPUT_DIR/$SONG_NAME/original.wav"

# Step 3: Organize output
echo ">>> Done! Files saved to $OUTPUT_DIR/$SONG_NAME/"
echo "  - Instrumental: stems/htdemucs_ft/original/no_vocals.wav"
echo "  - Vocals only:  stems/htdemucs_ft/original/vocals.wav"
echo "  - Original:     original.wav"
