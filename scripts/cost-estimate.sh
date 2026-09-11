#!/usr/bin/env bash
# Idle-cost sketch for this demo. Not a billing API call.
set -euo pipefail
cat <<'EOF'
Cost floor (single region, this template)

Not created on purpose
  NAT Gateway, VPC, ALB, RDS, ElastiCache, custom domain, X-Ray, provisioned DynamoDB

Idle (stack stays up, no traffic)
  Lambda        $0  (no provisioned concurrency)
  HTTP API      $0
  DynamoDB      $0  (on-demand, empty tables)
  CloudWatch    ~$0 (7-day retention, no traffic)
  Total idle    ~$0

Light HLD demo (~1k creates, ~10k redirects)
  HTTP API      < $0.01
  Lambda        free-tier / cents
  DynamoDB      cents
  Total         well under $1

Always run ./scripts/99-destroy.sh when the test account session ends.

Production would add ElastiCache + VPC (or PrivateLink) and that is where the bill jumps —
see DESIGN.md section 8.
EOF
