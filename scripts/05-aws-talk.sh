#!/usr/bin/env bash
# Cheatsheet for the AWS HLD demo. Does not create or delete resources.
# Run after 01-deploy.sh. Prints console stops + curl with the live URL.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
ensure_aws
need_cmd curl

API="$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --region "${AWS_REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
  --output text 2>/dev/null || true)"
if [[ -z "${API}" || "${API}" == "None" ]]; then
  die "stack ${STACK_NAME} is not up. Bring it up when you demo: export AWS_PROFILE AWS_REGION=${AWS_REGION} && ./scripts/01-deploy.sh"
fi
API="${API%/}"
REGION="${AWS_REGION}"
STACK="${STACK_NAME}"

cat <<EOF
========================================
AWS URL-shortener demo — what to show
Stack:  ${STACK}
Region: ${REGION}
API:    ${API}
========================================

Talk first, curl second. Do not start with the console dump.

0) One sentence
   "Same design as the whiteboard: HTTP API → write Lambda / read Lambda →
    DynamoDB urls + atomic counter. 302, not 301. Reads 1000:1 writes."

1) Console (2 min) — prove the boxes exist
   CloudFormation → stack "${STACK}" → Resources
     HttpApi, WriteFunction, ReadFunction, UrlsTable, CountersTable
   Lambda → ${STACK}-write  (POST /urls)   and  ${STACK}-read (GET /{code})
   DynamoDB → ${STACK}-urls (PK short_code) and ${STACK}-counters (global ADD)
   API Gateway → HTTP APIs → routes POST /urls, GET /{short_code}, GET /health

2) Live curl (5 min) — one behavior per command
   After each, say which box just ran.

EOF

print_cmd() {
  echo
  echo "----- $1 -----"
  echo "$2"
}

print_cmd "A. Health (API Gateway + write Lambda is reachable)" \
  "curl -sS ${API}/health"

print_cmd "B. Create short URL (WRITE: validate → counter ADD → PutItem)" \
  "curl -sS -X POST ${API}/urls -H 'content-type: application/json' -d '{\"long_url\":\"https://www.example.com/some/very/long/url\"}'"

echo
echo "   Capture short_code from JSON. Then:"
echo "   curl -sS -D - -o /dev/null ${API}/<code>"
echo "   Expect: HTTP 302   Location: https://www.example.com/some/very/long/url"
echo "           Cache-Control: no-store"
echo "   Say: 302 not 301 so browsers do not skip us on the next click."

print_cmd "C. Custom alias (same PK namespace, still WRITE)" \
  "curl -sS -X POST ${API}/urls -H 'content-type: application/json' -d '{\"long_url\":\"https://example.com/talk\",\"custom_alias\":\"my-talk\"}'"
echo "   curl -sS -D - -o /dev/null ${API}/my-talk     # 302"

print_cmd "D. Duplicate alias (conditional PutItem — uniqueness)" \
  "curl -sS -X POST ${API}/urls -H 'content-type: application/json' -d '{\"long_url\":\"https://example.com/other\",\"custom_alias\":\"my-talk\"}'"
echo "   Expect: HTTP 409"

print_cmd "E. Expiration (READ path decides 410; DynamoDB TTL is only GC)" \
  "curl -sS -X POST ${API}/urls -H 'content-type: application/json' -d '{\"long_url\":\"https://example.com/e\",\"custom_alias\":\"temp-link\",\"expiration_date\":\"USE_ISO_8_SECONDS_AHEAD\"}'"
echo "   ISO timestamp: python3 -c 'from datetime import datetime,timedelta,timezone; print((datetime.now(timezone.utc)+timedelta(seconds=8)).strftime(\"%Y-%m-%dT%H:%M:%SZ\"))'"
echo "   GET immediately → 302. Wait ~8s. GET ${API}/temp-link → 410"

print_cmd "F. Unknown code" \
  "curl -sS -D - -o /dev/null ${API}/does-not-exist"
echo "   Expect: HTTP 404"

echo
echo "3) Optional console after a create"
echo "   DynamoDB → ${STACK}-urls → Explore items → the new short_code row"
echo "   Lambda → ${STACK}-read → Monitor (one invocation per GET)"
echo
echo "4) Scripted full pass (same 7 steps, no typing)"
echo "   ./scripts/02-demo.sh && ./scripts/03-smoke.sh"
echo
echo "5) After the talk — this stack only"
echo "   ./scripts/99-destroy.sh && ./scripts/04-print-resources.sh"
echo
echo "Do not show: VPC, Redis, auth, analytics, custom domain."
echo "If asked Redis: production cache + INCR; this demo uses DynamoDB ADD + process cache so idle ≈ \$0."
