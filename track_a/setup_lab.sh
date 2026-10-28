#!/usr/bin/env bash
# Run once on the lab machine, from inside the fir_lab folder:  bash setup_lab.sh
set -e

echo "== GPU check =="
nvidia-smi || { echo "nvidia-smi failed: no NVIDIA driver/GPU visible. Tell the lab admin."; exit 1; }

echo "== Creating virtual environment =="
python3 -m venv fir_env
source fir_env/bin/activate
pip install --upgrade pip

echo "== Installing PyTorch (CUDA build) =="
# cu121 works for most drivers from 2023 onward. If this fails or torch.cuda is False afterwards,
# get the exact command for the lab's CUDA version from https://pytorch.org/get-started/locally/
pip install torch --index-url https://download.pytorch.org/whl/cu121

echo "== Installing the rest =="
pip install -r requirements.txt || {
  echo "Full install failed. Retrying without the optional explainability package..."
  grep -v transformers-interpret requirements.txt > /tmp/req_core.txt
  pip install -r /tmp/req_core.txt
}

echo "== Verifying =="
python - <<'PY'
import torch
print("torch", torch.__version__, "| cuda available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
PY
echo "Done. Next:  source fir_env/bin/activate && jupyter lab"
