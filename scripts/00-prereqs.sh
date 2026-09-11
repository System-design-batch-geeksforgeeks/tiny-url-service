#!/usr/bin/env bash
# Check local tools. AWS CLI / SAM are optional until you deploy.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

echo "project: ${ROOT}"
need_cmd "$(python_bin)"
PY="$(python_bin)"
echo "python: $("${PY}" --version)"

ver="$("${PY}" -c 'import sys; print(sys.version_info[:2])')"
"${PY}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
  || die "Python 3.11+ required (found ${ver})"

if command -v aws >/dev/null 2>&1; then
  echo "aws: $(aws --version 2>&1 | head -n1)"
else
  echo "aws: not installed (needed for 01-deploy.sh)"
fi

if command -v sam >/dev/null 2>&1; then
  echo "sam: $(sam --version 2>&1 | head -n1)"
else
  echo "sam: not installed (needed for 01-deploy.sh) — brew install aws-sam-cli"
fi

echo "prereqs ok"
