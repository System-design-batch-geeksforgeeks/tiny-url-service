# shellcheck shell=bash
# Shared by every script in this directory. Do not execute directly.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STACK_NAME="${STACK_NAME:-url-shortener-demo}"
AWS_REGION="${AWS_REGION:-us-east-1}"
API_URL_FILE="${ROOT}/.demo-api-url"
export AWS_REGION
export AWS_DEFAULT_REGION="${AWS_REGION}"

die() {
  echo "error: $*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing command: $1"
}

python_bin() {
  if [[ -x "${ROOT}/.venv/bin/python" ]]; then
    echo "${ROOT}/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    echo python3
  else
    die "python3 is required"
  fi
}

artifact_bucket() {
  local account
  account="$(aws sts get-caller-identity --query Account --output text)"
  echo "${STACK_NAME}-${account}-${AWS_REGION}"
}

ensure_aws() {
  need_cmd aws
  aws sts get-caller-identity --region "${AWS_REGION}" >/dev/null 2>&1 \
    || die "AWS credentials failed. Log in with the AWS CLI (SSO or keys in the shared credentials file), then export AWS_PROFILE and AWS_REGION=${AWS_REGION}"
}

stack_api_url() {
  if [[ -n "${API_URL:-}" ]]; then
    echo "${API_URL%/}"
    return
  fi
  if [[ -f "${API_URL_FILE}" ]]; then
    tr -d '[:space:]' <"${API_URL_FILE}"
    return
  fi
  aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
    --output text
}
