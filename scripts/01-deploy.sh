#!/usr/bin/env bash
# Package and deploy the stack. Writes .demo-api-url on success.
# Uses SAM if installed; otherwise AWS CLI + a bucket named only for this stack.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
cd "${ROOT}"
ensure_aws

mkdir -p .aws-sam
echo "deploying ${STACK_NAME} in ${AWS_REGION} (on-demand DynamoDB, 128MB ARM Lambda, HTTP API — no VPC/NAT/Redis)"

if command -v sam >/dev/null 2>&1; then
  sam build --template-file template.yaml
  sam deploy \
    --template-file .aws-sam/build/template.yaml \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --resolve-s3 \
    --capabilities CAPABILITY_IAM \
    --no-confirm-changeset \
    --no-fail-on-empty-changeset \
    --parameter-overrides "ProjectName=${STACK_NAME}" \
    --tags "Project=${STACK_NAME}" "Purpose=interview-demo"
else
  BUCKET="$(artifact_bucket)"
  echo "SAM CLI not found; using aws cloudformation package → s3://${BUCKET}"
  if ! aws s3api head-bucket --bucket "${BUCKET}" 2>/dev/null; then
    if [[ "${AWS_REGION}" == "us-east-1" ]]; then
      aws s3api create-bucket --bucket "${BUCKET}" --region "${AWS_REGION}"
    else
      aws s3api create-bucket --bucket "${BUCKET}" --region "${AWS_REGION}" \
        --create-bucket-configuration LocationConstraint="${AWS_REGION}"
    fi
    aws s3api put-bucket-tagging --bucket "${BUCKET}" \
      --tagging "TagSet=[{Key=Project,Value=${STACK_NAME}},{Key=Purpose,Value=interview-demo}]"
  fi
  aws cloudformation package \
    --template-file template.yaml \
    --s3-bucket "${BUCKET}" \
    --s3-prefix sam-artifacts \
    --output-template-file .aws-sam/packaged.yaml
  aws cloudformation deploy \
    --template-file .aws-sam/packaged.yaml \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
    --parameter-overrides "ProjectName=${STACK_NAME}" \
    --tags "Project=${STACK_NAME}" "Purpose=interview-demo"
fi

# Prefer stack output over a stale .demo-api-url from a previous deploy.
unset API_URL
rm -f "${API_URL_FILE}"
API_URL="$(stack_api_url)"
[[ -n "${API_URL}" && "${API_URL}" != "None" ]] || die "deploy succeeded but ApiUrl output is empty"
echo "${API_URL}" >"${API_URL_FILE}"
echo "ApiUrl: ${API_URL}"
echo "saved to ${API_URL_FILE}"
echo "next: ./scripts/05-aws-talk.sh   # prints what to show + curl"
echo "then: ./scripts/02-demo.sh && ./scripts/03-smoke.sh"
echo "after: ./scripts/99-destroy.sh"
