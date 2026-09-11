#!/usr/bin/env bash
# List stack resources so you can confirm what the test account is running.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
need_cmd aws

echo "region=${AWS_REGION} stack=${STACK_NAME}"
aws sts get-caller-identity --region "${AWS_REGION}" --output table

if aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1; then
  aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query "Stacks[0].{Status:StackStatus,Outputs:Outputs}" \
    --output json
  echo
  aws cloudformation list-stack-resources \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query "StackResourceSummaries[].{Type:ResourceType,Logical:LogicalResourceId,Physical:PhysicalResourceId,Status:ResourceStatus}" \
    --output table
else
  echo "stack ${STACK_NAME} is not present"
fi

echo
echo "tagged leftovers (Project=${STACK_NAME}):"
aws resourcegroupstaggingapi get-resources \
  --region "${AWS_REGION}" \
  --tag-filters "Key=Project,Values=${STACK_NAME}" \
  --query "ResourceTagMappingList[].ResourceARN" \
  --output text || true
