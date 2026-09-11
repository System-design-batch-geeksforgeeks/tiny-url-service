# HLD demo plan (backend only)

Standalone project. No frontend. **You** bring AWS up for the talk (`01-deploy.sh`) and tear it down after (`99-destroy.sh`). Nothing should be left running beforehand.

**Target length:** ~20 minutes talking + 5 minutes live `curl`.

---

## 0. Setup before the room (2 min)

```bash
cd url-shortener
./scripts/00-prereqs.sh          # python3.12, optional: aws/sam
./scripts/local-demo.sh          # must pass — this is the HLD demo
```

Keep `DESIGN.md` open on the architecture diagram. Run `./scripts/serve.sh` in a second terminal if you want to type `curl` live instead of the scripted walkthrough.

---

## 1. Requirements (2 min)

**In scope**

- `POST /urls` — long URL → short URL; optional custom alias; optional expiration
- `GET /{code}` — 302 to the original; 404 unknown; 410 expired

**Out of scope (say this out loud)**

- Auth, accounts, click analytics, spam/malware scanning

**Non-functionals to pin**

| NFR | Demo stance |
|---|---|
| Unique short codes | PK + conditional put; counter is uniqueness, not continuity |
| Redirect &lt; 100 ms | Cache-aside; 128 MB Lambda is enough for a demo |
| Availability &gt; consistency | 302 (not 301); stale cache TTL ≤ remaining TTL |
| Scale later | Read/write split already; DynamoDB on-demand; no Redis bill |

Read:write ≈ 1000:1 — that is why two Lambdas, not one.

---

## 2. Entities and API (2 min)

Whiteboard only three things: **original URL**, **short code**, **optional expiry**. User is below the line.

```
POST /urls     { long_url, custom_alias?, expiration_date? }  → { short_url, short_code }
GET  /{code}   → 302 Location: <long_url>
GET  /health   → 200 { ok: true }
```

**302 vs 301:** 301 is cached by browsers, so expiry and “change the target” stop working. 302 keeps the read path on our servers. `Cache-Control: no-store` on the redirect.

---

## 3. High-level design (6 min)

Walk `DESIGN.md` top to bottom, left to right:

1. Client → HTTP API (the API Gateway box)
2. **Write service** — validate, allocate id, persist
3. **Read service** — cache → DB → 302
4. **Urls table** — source of truth, PK = `short_code`
5. **Global counter** — atomic increment + batching (Redis in the original design; DynamoDB `ADD` here so the demo costs ~$0 idle)
6. **Cache** — warm-Lambda LRU in the demo; ElastiCache in production

Then the two sequences:

**Write:** validate → next counter (or custom alias) → `PutItem` if not exists → return short URL.

**Read:** cache hit? else DynamoDB `GetItem` → expired? 410 : 302. Populate cache with TTL = min(5 min, remaining life).

If they ask “why not one Lambda?”: independent scale, blast radius, read path stays tiny.

---

## 4. Live local demo (5 min)

`./scripts/local-demo.sh` (or `curl` against `./scripts/serve.sh`):

| Step | What you show |
|---|---|
| 1 | Create a short URL from a long one |
| 2 | `GET` returns **302**, not 200, `Location` is the original |
| 3 | Custom alias `my-talk` |
| 4 | Same alias again → **409** |
| 5 | Expire in ~8 seconds → **410 Gone** |
| 6 | Unknown code → **404** |
| 7 | Two generated codes are distinct |

Say out loud: the in-memory stores are the same interfaces as DynamoDB (`UrlRepository`, `Counter`, `Cache`). AWS is a swap of adapters, not a rewrite.

---

## 5. Deep dives if they push (5 min, pick 1–2)

**Uniqueness.** Counter in DynamoDB is atomic. Each write-Lambda instance checks out a **batch** of 100 ids so we are not one network hop per URL. Lost batches on crash are fine — we need uniqueness, not a dense integer line. Conditional `PutItem` is the last safety net (custom aliases).

**Fast redirects.** PK lookup is O(1). Cache-aside on the read service. Do not 301.

**Scale to 1B URLs / 100M DAU.** ~500 GB is one DynamoDB table, not a shard event. Writes ~1/sec in the original estimate — any store works. Reads are the problem → more read Lambdas + cache. Multi-region: disjoint counter ranges, local writes, global cached reads.

**Cost.** No VPC, NAT, RDS, ALB, or ElastiCache. Idle ≈ $0. Tear down with `./scripts/99-destroy.sh`.

---

## 6. AWS demo (you bring the stack up)

Do not leave a stack running overnight. Bring it up right before the talk, show the list below, destroy after.

### Bring-up

```bash
cd url-shortener
export AWS_PROFILE=your-profile      # your AWS CLI profile; never commit keys
export AWS_REGION=us-east-1
aws sso login --profile "$AWS_PROFILE"  # if the SSO session expired
./scripts/01-deploy.sh               # ~2 min; SAM optional (falls back to AWS CLI)
./scripts/05-aws-talk.sh             # prints this cheatsheet with the live URL
```

### What to show (in this order)

**A. Whiteboard first (same as sections 1–3).** Then: “this is that design on AWS.”

**B. Console, 2 minutes — the six boxes**

| Console | Resource | Maps to |
|---|---|---|
| CloudFormation → `url-shortener-demo` → Resources | whole stack | HLD diagram |
| Lambda `url-shortener-demo-write` | POST `/urls` | Write service |
| Lambda `url-shortener-demo-read` | GET `/{code}` | Read service |
| DynamoDB `url-shortener-demo-urls` | PK `short_code` | Urls table |
| DynamoDB `url-shortener-demo-counters` | item `global` | Redis INCR stand-in |
| API Gateway HTTP API | routes | API Gateway box |

Do not open VPC, RDS, or ElastiCache — they are not in this design.

**C. Live curl against the execute-api URL (5 minutes)**

| # | Show | Expect | Point at |
|---|---|---|---|
| 1 | `GET /health` | 200 `{"ok":true}` | API Gateway + write Lambda |
| 2 | `POST /urls` with a long URL | 201 + `short_code` | write: counter → PutItem |
| 3 | `GET /{code}` **with `-D -`** | **302**, `Location`, `Cache-Control: no-store` | read Lambda. Say “not 301” |
| 4 | `POST` `custom_alias=my-talk` then GET | 201 then 302 | same table, your key |
| 5 | same alias again | **409** | conditional put / uniqueness |
| 6 | create with expiry ~2s ahead, wait, GET | 302 then **410** | read-path expiry, not a sweeper |
| 7 | `GET /does-not-exist` | **404** | miss |

Exact curls: `./scripts/05-aws-talk.sh` after deploy. Hands-off replay: `./scripts/02-demo.sh`.

**D. Optional one click after a create:** DynamoDB → `url-shortener-demo-urls` → the new item. Lambda → read → Monitor (invocation count).

**E. Tear down (this stack only)**

```bash
./scripts/99-destroy.sh
./scripts/04-print-resources.sh    # no tables, lambdas, APIs, or Project=url-shortener-demo tags
```

### Do not show

Auth, analytics, custom domain, Redis, NAT, “how SAM works.” If asked Redis: production cache + `INCR`; this demo uses DynamoDB `ADD` + process cache so idle ≈ $0.

---

## Talking pitfalls

- Do not invent analytics mid-demo.
- Do not hash the long URL as the code (collisions + “same long URL must get many shorts”).
- Do not use 301.
- If asked about Redis: “Production cache and counter. This demo uses DynamoDB `ADD` + process cache so we can delete every resource for pennies.”
