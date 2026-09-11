#!/usr/bin/env bash
# HLD demo against in-memory stores. No AWS account required.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
cd "${ROOT}"
PY="$(python_bin)"
export PYTHONPATH="${ROOT}/src"
exec "${PY}" -m url_shortener.demo
