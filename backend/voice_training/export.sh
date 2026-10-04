#!/usr/bin/env bash
# Turn the latest training checkpoint into a Piper voice the app can use. From
# PowerShell, in the backend folder:
#
#   wsl bash voice_training/export.sh
#
# Works mid-training too (in a second terminal), so you can listen to progress.
# Pass a checkpoint path to export a specific one instead of the latest.
set -euo pipefail

THIS_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$(cd "$THIS_DIR/.." && pwd)"
WORK="${PIPER_WORK:-$HOME/piper-voice}"
VOICE_NAME="${VOICE_NAME:-myvoice}"
MODEL="en_US-$VOICE_NAME-medium"

CHECKPOINT="${1:-$(ls -t "$WORK"/runs/lightning_logs/version_*/checkpoints/last.ckpt 2>/dev/null | head -n 1 || true)}"
if [ -z "$CHECKPOINT" ] || [ ! -s "$CHECKPOINT" ]; then
    echo "No checkpoint found. Run voice_training/train.sh first." >&2
    exit 1
fi
if [ ! -s "$WORK/config.json" ]; then
    echo "Missing $WORK/config.json — it is written when training starts." >&2
    exit 1
fi

# shellcheck disable=SC1091
source "$WORK/piper1-gpl/.venv/bin/activate"

echo "==> Exporting $CHECKPOINT"
mkdir -p "$WORK/export" "$BACKEND/voice_models"
python3 -m piper.train.export_onnx \
    --checkpoint "$CHECKPOINT" \
    --output-file "$WORK/export/$MODEL.onnx"

cp "$WORK/export/$MODEL.onnx" "$BACKEND/voice_models/$MODEL.onnx"
cp "$WORK/config.json" "$BACKEND/voice_models/$MODEL.onnx.json"

echo
echo "Saved $MODEL to backend/voice_models. To hear it, set in backend/.env:"
echo "  VOICE_PROVIDER=piper"
echo "  PIPER_VOICE=$MODEL"
echo "then restart the backend."
