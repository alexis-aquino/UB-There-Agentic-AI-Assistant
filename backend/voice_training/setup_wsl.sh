#!/usr/bin/env bash
# One-time setup for training your Piper voice. Runs inside WSL (Ubuntu), because Piper's
# trainer builds Linux-only extensions. From PowerShell, in the backend folder:
#
#   wsl bash voice_training/setup_wsl.sh
#
# Installs build tools, clones the Piper trainer into ~/piper-voice, and downloads the
# Lessac medium checkpoint (~850 MB) that your voice is fine-tuned from. Safe to re-run.
set -euo pipefail

WORK="${PIPER_WORK:-$HOME/piper-voice}"
REPO="$WORK/piper1-gpl"
CHECKPOINT="$WORK/lessac-medium.ckpt"
CHECKPOINT_URL="https://huggingface.co/datasets/rhasspy/piper-checkpoints/resolve/main/en/en_US/lessac/medium/epoch%3D2164-step%3D1355540.ckpt"

echo "==> Checking the GPU is visible from WSL"
if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "nvidia-smi not found. Update the NVIDIA driver on Windows (WSL uses the Windows driver)." >&2
    exit 1
fi
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

echo "==> Installing build tools (asks for your WSL password)"
sudo apt-get update
sudo apt-get install -y build-essential cmake ninja-build git wget python3-venv python3-dev

mkdir -p "$WORK"
if [ ! -d "$REPO" ]; then
    echo "==> Cloning the Piper trainer"
    git clone https://github.com/OHF-voice/piper1-gpl.git "$REPO"
fi

cd "$REPO"
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing the trainer (pulls PyTorch, several GB)"
python3 -m pip install --upgrade pip
python3 -m pip install -e '.[train]'
./build_monotonic_align.sh
python3 setup.py build_ext --inplace

echo "==> Checking PyTorch can use the GPU"
python3 - <<'PY'
import torch
if not torch.cuda.is_available():
    raise SystemExit("PyTorch cannot see the GPU — training on CPU would take days.")
print("GPU:", torch.cuda.get_device_name(0))
PY

if [ ! -s "$CHECKPOINT" ]; then
    echo "==> Downloading the Lessac medium checkpoint (~850 MB)"
    wget -c -O "$CHECKPOINT.part" "$CHECKPOINT_URL"
    mv "$CHECKPOINT.part" "$CHECKPOINT"
fi

echo
echo "Setup complete. Record your clips in the app, then run:"
echo "  wsl bash voice_training/train.sh"
