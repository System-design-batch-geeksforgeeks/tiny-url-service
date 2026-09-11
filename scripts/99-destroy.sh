#!/usr/bin/env bash
# Delete only this demo: the CloudFormation stack, its log groups, and its artifact bucket.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
ensure_aws

echo "destroying ${STACK_NAME} in ${AWS_REGION}"

if command -v sam >/dev/null 2>&1 && aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1; then
  sam delete --stack-name "${STACK_NAME}" --region "${AWS_REGION}" --no-prompts
elif aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1; then
  aws cloudformation delete-stack --stack-name "${STACK_NAME}" --region "${AWS_REGION}"
  aws cloudformation wait stack-delete-complete --stack-name "${STACK_NAME}" --region "${AWS_REGION}"
else
  echo "stack ${STACK_NAME} already gone"
fi

for group in "/aws/lambda/${STACK_NAME}-write" "/aws/lambda/${STACK_NAME}-read"; do
  if aws logs describe-log-groups --region "${AWS_REGION}" --log-group-name-prefix "${group}" \
      --query "logGroups[?logGroupName=='${group}'].logGroupName" --output text 2>/dev/null | grep -q "${group}"; then
    echo "deleting log group ${group}"
    aws logs delete-log-group --region "${AWS_REGION}" --log-group-name "${group}" || true
  fi
done

BUCKET="$(artifact_bucket)"
if aws s3api head-bucket --bucket "${BUCKET}" 2>/dev/null; then
  echo "emptying and deleting artifact bucket s3://${BUCKET}"
  aws s3 rm "s3://${BUCKET}" --recursive || true
  aws s3api delete-bucket --bucket "${BUCKET}" || true
fi

rm -f "${API_URL_FILE}"
echo "destroy complete. run ./scripts/04-print-resources.sh to confirm only this project is gone."
