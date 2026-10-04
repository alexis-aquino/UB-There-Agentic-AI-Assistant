#!/usr/bin/env bash
# Fine-tune the Lessac voice on your recordings. From PowerShell, in the backend folder:
#
#   wsl bash voice_training/train.sh
#
# Resumable: stop any time with Ctrl+C and run it again to continue from the last
# checkpoint. Set FRESH=1 to start over from Lessac.
#
# Settings (prefix the command, e.g. "wsl BATCH_SIZE=4 bash voice_training/train.sh"):
#   BATCH_SIZE  clips per step. 8 suits a 6 GB card; drop to 4 on "CUDA out of memory".
#   EPOCHS      passes over your clips on top of the checkpoint's own. 1000 is a solid
#               fine-tune; you can stop earlier and export to listen.
#   VOICE_NAME  name of the finished voice (default: myvoice).
set -euo pipefail

THIS_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$(cd "$THIS_DIR/.." && pwd)"
DATASET="$BACKEND/voice_dataset"

WORK="${PIPER_WORK:-$HOME/piper-voice}"
VOICE_NAME="${VOICE_NAME:-myvoice}"
BATCH_SIZE="${BATCH_SIZE:-8}"
EPOCHS="${EPOCHS:-1000}"
# The Lessac checkpoint has already trained 2164 epochs; Lightning counts from there.
MAX_EPOCHS=$((2165 + EPOCHS))

if [ ! -d "$WORK/piper1-gpl/.venv" ] || [ ! -s "$WORK/lessac-medium.ckpt" ]; then
    echo "Run setup first: wsl bash voice_training/setup_wsl.sh" >&2
    exit 1
fi
if [ ! -s "$DATASET/metadata.csv" ]; then
    echo "No recordings yet. Record clips in the app (Voice settings -> Train my voice)." >&2
    exit 1
fi

CLIPS=$(grep -c . "$DATASET/metadata.csv")
echo "==> $CLIPS recorded clips"
if [ "$CLIPS" -lt 150 ]; then
    echo "Fewer than 150 clips. Training will run, but expect a voice that sounds only" >&2
    echo "partly like you. 300+ clips (about 25 minutes) gives a much closer match." >&2
fi

# Copy into the Linux filesystem: reading thousands of small files across /mnt/c is slow.
echo "==> Copying recordings into WSL"
mkdir -p "$WORK/dataset"
rm -rf "$WORK/dataset/wavs"
cp -r "$DATASET/wavs" "$WORK/dataset/wavs"
cp "$DATASET/metadata.csv" "$WORK/dataset/metadata.csv"

CHECKPOINT="$WORK/lessac-medium.ckpt"
LAST=$(ls -t "$WORK"/runs/lightning_logs/version_*/checkpoints/last.ckpt 2>/dev/null | head -n 1 || true)
if [ -n "$LAST" ] && [ "${FRESH:-0}" != "1" ]; then
    CHECKPOINT="$LAST"
    echo "==> Resuming from $LAST"
else
    echo "==> Starting from the Lessac checkpoint"
    # Phonemes are cached per dataset; a fresh run must not reuse stale ones.
    rm -rf "$WORK/cache"
fi

# shellcheck disable=SC1091
source "$WORK/piper1-gpl/.venv/bin/activate"

echo "==> Training: batch $BATCH_SIZE, up to epoch $MAX_EPOCHS. Ctrl+C to pause."
python3 -m piper.train fit \
    --data.voice_name "$VOICE_NAME" \
    --data.csv_path "$WORK/dataset/metadata.csv" \
    --data.audio_dir "$WORK/dataset/wavs/" \
    --model.sample_rate 22050 \
    --data.espeak_voice "en-us" \
    --data.cache_dir "$WORK/cache/" \
    --data.config_path "$WORK/config.json" \
    --data.batch_size "$BATCH_SIZE" \
    --trainer.max_epochs "$MAX_EPOCHS" \
    --trainer.precision 32 \
    --trainer.default_root_dir "$WORK/runs" \
    --ckpt_path "$CHECKPOINT"

echo
echo "Training finished. Export it into the app with:"
echo "  wsl bash voice_training/export.sh"
