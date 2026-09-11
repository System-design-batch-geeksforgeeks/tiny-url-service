#!/usr/bin/env bash
# Same HLD script as local-demo, pointed at the deployed API.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
cd "${ROOT}"
need_cmd aws
PY="$(python_bin)"
export PYTHONPATH="${ROOT}/src"

API_URL="$(stack_api_url)"
[[ -n "${API_URL}" && "${API_URL}" != "None" ]] || die "no API URL. Run 01-deploy.sh or export API_URL="

echo "live HLD demo against ${API_URL}"
exec "${PY}" -m url_shortener.demo "${API_URL}"
