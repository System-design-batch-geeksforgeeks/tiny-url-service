# URL shortener (standalone)

Separate project from the interview-prep `lld/` catalog. Backend only: local HLD demo now, AWS later when a test account is available, then tear everything down.

Talk track: [PLAN.md](PLAN.md). Design (HLD + LLD + AWS + distributed): [DESIGN.md](DESIGN.md).

```
Client → HTTP API → Write Lambda (POST /urls)
                 → Read  Lambda (GET /{code} 302)
                      ↓
              DynamoDB urls + atomic counter
              (process cache on the read Lambda)
```

No VPC, NAT, RDS, ALB, or ElastiCache — idle cost is about **$0**. `./scripts/cost-estimate.sh`.

## Layout

```
url-shortener/
  PLAN.md                 how to present the HLD
  DESIGN.md               HLD, LLD, AWS mapping
  template.yaml           SAM / CloudFormation
  src/url_shortener/      domain + HTTP + Lambda
  tests/
  scripts/
    00-prereqs.sh
    test.sh
    local-demo.sh         HLD demo, no AWS
    serve.sh              leave local API up for curl
    01-deploy.sh          you run this to bring AWS up
    02-demo.sh            same HLD script on the live API
    03-smoke.sh
    04-print-resources.sh
    05-aws-talk.sh        console stops + curl cheatsheet
    99-destroy.sh         you run this after the demo
    cost-estimate.sh
```

## Local (no AWS)

Python 3.11+.

```bash
cd url-shortener
./scripts/00-prereqs.sh
./scripts/test.sh                # creates .venv and installs pytest if needed
./scripts/local-demo.sh          # scripted HLD walkthrough
./scripts/serve.sh               # optional: curl against http://127.0.0.1:8080
```

```bash
curl -sS -X POST http://127.0.0.1:8080/urls \
  -H 'content-type: application/json' \
  -d '{"long_url":"https://example.com/very/long","custom_alias":"my-talk"}'

curl -sS -D - -o /dev/null http://127.0.0.1:8080/my-talk
```

Expect **302** (not 301) and `Location: https://example.com/very/long`.

## AWS demo (bring up yourself; destroy after)

AWS CLI is enough. SAM CLI is optional. Use whatever profile you already log in with (`AWS_PROFILE`); this repo does not store account ids or keys.

`samconfig.toml.example` is **not** required to run locally or to deploy via `./scripts/01-deploy.sh`. Copy it to `samconfig.toml` only if you want SAM CLI defaults (stack name + region). `samconfig.toml` is gitignored so a real deploy never commits bucket names.

```bash
export AWS_PROFILE=your-profile        # or rely on the default AWS CLI chain
export AWS_REGION=us-east-1
aws sso login --profile "$AWS_PROFILE"  # if you use SSO
./scripts/01-deploy.sh                 # you run this when the demo starts
./scripts/05-aws-talk.sh               # what to show + curl with the live URL
# …console + curl (see PLAN.md §6)…
./scripts/99-destroy.sh                # you run this when the demo ends
```

Hands-off API check: `./scripts/02-demo.sh && ./scripts/03-smoke.sh`.

Override stack name with `STACK_NAME=url-shortener-demo-alice ./scripts/01-deploy.sh`. Destroy deletes that stack, its log groups, and the `url-shortener-demo-<account>-<region>` artifact bucket only.

## API

| Method | Path | Result |
|---|---|---|
| `POST` | `/urls` | `201 { short_url, short_code }` |
| `GET` | `/{short_code}` | `302` / `404` / `410` |
| `GET` | `/health` | `200 { ok: true }` |

`POST /urls` body:

```json
{
  "long_url": "https://www.example.com/some/very/long/url",
  "custom_alias": "optional_custom_alias",
  "expiration_date": "2026-12-31T00:00:00Z"
}
```
