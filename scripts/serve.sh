#!/usr/bin/env bash
# Keep the local API up for manual curl during the HLD talk.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
cd "${ROOT}"
PY="$(python_bin)"
export PYTHONPATH="${ROOT}/src"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8080}"
echo "curl examples:"
echo "  curl -sS -X POST http://${HOST}:${PORT}/urls -H 'content-type: application/json' -d '{\"long_url\":\"https://example.com/long\"}'"
echo "  curl -sS -D - -o /dev/null http://${HOST}:${PORT}/<code>"
exec "${PY}" -m url_shortener.server --host "${HOST}" --port "${PORT}"
