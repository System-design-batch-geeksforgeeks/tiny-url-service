#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
cd "${ROOT}"
PY="$(python_bin)"
if ! "${PY}" -c "import pytest" >/dev/null 2>&1; then
  echo "installing pytest into .venv (or: python3 -m pip install -r requirements-dev.txt)"
  if [[ ! -x "${ROOT}/.venv/bin/python" ]]; then
    python3 -m venv "${ROOT}/.venv"
    PY="${ROOT}/.venv/bin/python"
  fi
  "${PY}" -m pip install -q -r "${ROOT}/requirements-dev.txt"
fi
exec "${PY}" -m pytest tests
