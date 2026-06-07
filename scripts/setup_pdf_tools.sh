#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv-pdf"
REQ_FILE="${ROOT_DIR}/scripts/requirements-pdf.txt"

python3 -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "${REQ_FILE}"

echo "PDF toolchain ready: ${VENV_DIR}"
echo "Activate with: source .venv-pdf/bin/activate"
