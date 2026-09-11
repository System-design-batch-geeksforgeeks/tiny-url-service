#!/usr/bin/env bash
# Extra e2e checks (health, create, 302, 404) with curl — useful after 02-demo.sh.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
need_cmd curl
need_cmd aws

API_URL="$(stack_api_url)"
[[ -n "${API_URL}" && "${API_URL}" != "None" ]] || die "no API URL. Run 01-deploy.sh or export API_URL="
API_URL="${API_URL%/}"

echo "GET ${API_URL}/health"
health="$(curl -sS -f "${API_URL}/health")"
echo "${health}" | grep -q '"ok"' || die "health failed: ${health}"

echo "POST ${API_URL}/urls"
create="$(curl -sS -f -X POST "${API_URL}/urls" \
  -H "content-type: application/json" \
  -d '{"long_url":"https://example.com/smoke"}')"
echo "${create}"
code="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["short_code"])' "${create}")"
[[ -n "${code}" ]] || die "no short_code in ${create}"

echo "GET ${API_URL}/${code} (expect 302)"
headers="$(mktemp)"
curl -sS -D "${headers}" -o /dev/null "${API_URL}/${code}"
grep -qE "^HTTP/.* 302" "${headers}" || { cat "${headers}"; die "expected 302"; }
grep -qiE "^Location: https://example.com/smoke" "${headers}" || { cat "${headers}"; die "missing Location"; }
rm -f "${headers}"

echo "GET ${API_URL}/no-such-code-xyz (expect 404)"
code_404="$(curl -sS -o /dev/null -w "%{http_code}" "${API_URL}/no-such-code-xyz")"
[[ "${code_404}" == "404" ]] || die "expected 404, got ${code_404}"

echo "smoke ok"
