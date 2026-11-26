#!/usr/bin/env bash
# One-time setup for the reaction-video skill (Linux or macOS).
# Installs Python deps and downloads Piper voices into $RV_HOME/voices.
#   bash setup.sh                 # default English voices
#   bash setup.sh ru              # + Russian voices
set -euo pipefail

RV_HOME="${RV_HOME:-$HOME/.cache/reaction-video}"
VOICES_DIR="$RV_HOME/voices"
mkdir -p "$VOICES_DIR"

command -v ffmpeg >/dev/null || { echo "ffmpeg is required (apt install ffmpeg / brew install ffmpeg)"; exit 1; }

python3 -m pip install -q --disable-pip-version-check piper-tts faster-whisper pillow 2>&1 | grep -v -i "warning" || true

HF="https://huggingface.co/rhasspy/piper-voices/resolve/main"
VOICES=(
  "en/en_US/ryan/high/en_US-ryan-high"          # energetic male
  "en/en_US/amy/medium/en_US-amy-medium"        # female
  "en/en_US/joe/medium/en_US-joe-medium"        # second male
)
if [[ "${1:-}" == "ru" ]]; then
  VOICES+=(
    "ru/ru_RU/dmitri/medium/ru_RU-dmitri-medium"
    "ru/ru_RU/irina/medium/ru_RU-irina-medium"
  )
fi

for v in "${VOICES[@]}"; do
  n="$(basename "$v")"
  if [[ ! -s "$VOICES_DIR/$n.onnx" ]]; then
    echo "downloading voice $n"
    curl -sfL -o "$VOICES_DIR/$n.onnx" "$HF/$v.onnx"
    curl -sfL -o "$VOICES_DIR/$n.onnx.json" "$HF/$v.onnx.json"
  fi
done

echo "OK. Voices in $VOICES_DIR:"
ls "$VOICES_DIR" | grep '\.onnx$'
