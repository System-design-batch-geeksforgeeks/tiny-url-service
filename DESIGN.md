# URL shortener — HLD, LLD, AWS

Backend-only design of the Hello Interview Bit.ly problem. Local process and AWS share one domain layer; only the stores change.

---

## 1. Functional requirements

| # | Capability |
|---|---|
| F1 | Submit a long URL, get a short URL |
| F2 | Optional custom alias (`/my-custom-alias`) |
| F3 | Optional expiration |
| F4 | `GET` short URL → original |

**Below the line:** auth, accounts, click analytics, spam/malware filtering.

## 2. Non-functional requirements

| # | Requirement | Design consequence |
|---|---|---|
| N1 | Short codes unique | Atomic counter + conditional insert |
| N2 | Redirect &lt; 100 ms | PK lookup + cache-aside; 302 |
| N3 | Availability &gt; consistency | Fail open on cache; never 301 |
| N4 | Headroom to 1B URLs / 100M DAU | Read/write split; on-demand table |

Read:write is about **1000:1**. Cache, DB choice, and two services all follow from that.

---

## 3. Core entities

| Entity | Identity | Notes |
|---|---|---|
| **UrlMapping** | `short_code` | The only persisted entity. Holds `long_url`, `created_at`, `expires_at?`, `is_custom` |
| Original URL | value | Not its own row — two users may shorten the same link |
| User | out of scope | `createdBy` omitted |

Custom alias and generated code share one namespace (one table, one PK). Collision = 409 for aliases, retry for generated codes.

---

## 4. API

```
POST /urls
{
  "long_url": "https://www.example.com/some/very/long/url",
  "custom_alias": "optional_custom_alias",
  "expiration_date": "2026-12-31T00:00:00Z"
}
→ 201
{
  "short_url": "https://{host}/{code}",
  "short_code": "baaaaa"
}

GET /{short_code}  → 302 Location: <long_url>   (Cache-Control: no-store)
                   → 404 if unknown
                   → 410 if expired

GET /health        → 200 {"ok": true}
```

**302 Found**, not 301. Browsers cache 301 and would skip our server on the next click — expiry, retarget, and (later) analytics all break.

---

## 5. High-level design

Hello Interview boxes, mapped to this repo:

```
                    ┌─────────────────────────────────────────┐
   Client  ────────►│  API Gateway HTTP API  ($default stage) │
                    └───────────────┬─────────────────────────┘
                                    │
                 POST /urls         │           GET /{code}
                 GET  /health       │
                          ▼         ▼
                   ┌────────────┐  ┌────────────┐
                   │   Write    │  │    Read    │
                   │  service   │  │  service   │
                   └─────┬──────┘  └─────┬──────┘
                         │               │
            next batch   │               │  cache-aside
                         ▼               ▼
                   ┌────────────┐  ┌────────────┐
                   │  Counter   │  │   Cache    │
                   │ (atomic)   │  │ (hot keys) │
                   └─────┬──────┘  └─────┬──────┘
                         │               │
                         ▼               ▼
                   ┌─────────────────────────────────────────┐
                   │              Urls table                  │
                   │  PK short_code → long_url, expires_at    │
                   └─────────────────────────────────────────┘
```

### 5.1 Write path (F1–F3)

1. Validate `long_url` (`http`/`https`, length cap). Validate alias charset / reserved words. Parse expiry (must be in the future).
2. **Custom alias:** use it as `short_code`.
   **Generated:** `base62(counter.next() + 62^5)` so codes are 6+ characters.
3. Conditional insert (`attribute_not_exists(short_code)`). Alias conflict → 409. Generated conflict → take the next id (should not happen).
4. Return `{short_url, short_code}`. Do **not** fold duplicate long URLs into one code (separate expiry / alias / future analytics).

### 5.2 Read path (F4)

1. Cache get by `short_code`.
2. Miss → DynamoDB `GetItem` (consistent read — a click can follow a create immediately).
3. Missing → 404. `now >= expires_at` → 410.
4. 302 + fill cache. TTL = min(300s, remaining life) so we never serve a live redirect after expiry.

Expired rows are also marked with DynamoDB **TTL** (`ttl` epoch). TTL is a best-effort sweeper (hours, not seconds). Correctness is the read-path check, not the sweeper.

### 5.3 Why two services

Writes are rare and heavier (validate, counter, conditional put). Reads must be tiny and independently scaled. An API Gateway route is the “API Gateway / microservice split” from the original design.

---

## 6. Short-code generation (LLD)

**Chosen: global monotonic counter → base62.** Same as the interview “pick”.

| Option | Pros | Cons |
|---|---|---|
| Base62(counter) | Unique, short, cheap | Predictable; needs a single source of truth |
| Hash(long URL) | No counter | Collisions; same URL cannot have two codes |
| Random + retry | Unpredictable | Extra reads; retry storms at high fill factor |

Alphabet: `0-9a-zA-Z` (62 symbols). Offset `62^5` so generated codes are at least 6 chars (`100000`, `100001`, …). Custom aliases are 3–32 of `[A-Za-z0-9_-]` and cannot be reserved (`urls`, `health`).

**Counter batching** (the original Redis trick):

1. Write instance calls `ADD current_value :batch_size` once.
2. It owns `[new-batch, new)` locally (mutex in-process).
3. Next 99 creates are free of a network hop.
4. If the process dies, unused ids in the batch are skipped. **Uniqueness holds; density does not matter.**

**Horizontal write scale:** every Lambda container is a writer. They do not share memory. They share the counter item. DynamoDB `ADD` is atomic (same contract as Redis `INCR`).

**Safety net:** table PK + `attribute_not_exists`. Two custom-alias requests for `my-talk` — one wins, one 409. No read-then-write.

**Multi-region (not in the demo):** give each region a disjoint counter range (region A: `0–1e12`, region B: `1e12–2e12`). No cross-region increment. Reads can use replicated cache; writes stay regional.

---

## 7. Low-level design

### 7.1 Module map

```
handlers / http_app     transport (API Gateway v2 or stdlib HTTP)
        │
        ▼
   UrlShortener         one use-case class: shorten() / resolve()
        │
        ├── UrlRepository     put_if_absent / get
        ├── Counter           next_id()  (batched in front)
        ├── Cache             get / put with TTL
        └── Clock             now() for expiry and tests
```

`memory.py` is the local demo. `aws_stores.py` is DynamoDB. Tests inject fakes. Nothing in `UrlShortener` imports boto3.

### 7.2 Persistence

**Urls** (PK `short_code`)

| Attribute | Type | |
|---|---|---|
| `short_code` | S | PK |
| `long_url` | S | |
| `created_at` | N | unix seconds |
| `expires_at` | N | optional |
| `is_custom` | BOOL | |
| `ttl` | N | DynamoDB TTL, only if expiry set |

**Counters** (PK `counter_id`)

| Attribute | Type | |
|---|---|---|
| `counter_id` | S | `"global"` |
| `current_value` | N | last exclusive end of allocated range |

~200–500 bytes/row. 1B rows ≈ 500 GB — one table, no shard for the demo or for the original scale number.

### 7.3 Redirect cache

Production: Redis, key = `short_code`, value = JSON mapping, TTL as above.

Demo: in-process dict on the **read** Lambda. Warm containers keep hits; cold start is a DynamoDB get (~single-digit ms in-region). Skipping ElastiCache avoids VPC + NAT (~$45/month idle).

### 7.4 Failure modes

| Failure | Behaviour |
|---|---|
| Counter `ADD` fails | 503; no partial row |
| Conditional put fails (alias) | 409 |
| Conditional put fails (generated) | retry next id |
| DynamoDB read fails, cache hit | serve cache (availability) |
| DynamoDB read fails, cache miss | 503 |
| Lambda / AZ loss | API Gateway → other AZ; DynamoDB is regional multi-AZ |
| Counter “goes backwards” after a rare replica blip | conditional put rejects duplicates |

We accept a brief window where a just-written URL is not in the process cache on **another** read instance. Consistent `GetItem` fills it.

---

## 8. AWS mapping (demo vs production)

| Hello Interview | This demo (cost floor) | Production-shaped |
|---|---|---|
| API Gateway | HTTP API, `$default` stage, no extra prefix | Same, plus custom domain |
| Write / Read services | Two ARM64 Python 3.12 Lambdas, 128 MB | Same, or ECS if you need always-on |
| Postgres | DynamoDB on-demand (PK lookup, no RDS idle) | DynamoDB or Aurora; Postgres is fine at 1 row/s writes |
| Redis cache | Process TTL cache | ElastiCache Redis (then you pay VPC/NAT or PrivateLink) |
| Redis counter | DynamoDB `ADD` + batching | Redis `INCR` or the same DynamoDB item |
| Replica / backup | DynamoDB is replicated for you; `DeletionPolicy: Delete` for the test account | PITR when this is real data |
| Expired-row janitor | DynamoDB TTL | TTL + a nightly job if you need immediate reclaim |

**Deliberately not used (idle cost):** NAT Gateway, ALB, RDS, ElastiCache, VPC-attached Lambda, provisioned DynamoDB, X-Ray, custom domain, CloudFront (optional later for edge 302).

Idle cost target: **~$0**. Tear-down script deletes the stack, tables, and log groups.

### 8.1 IAM

- Write Lambda: `PutItem` on urls, `UpdateItem` on counters.
- Read Lambda: `GetItem` on urls only.
- No `*`. No VPC, so Lambda uses the public DynamoDB endpoint (still IAM-signed).

### 8.2 Capacity sketch (original numbers)

- 100k new URLs/day ≈ 1 write/s. On-demand DynamoDB and Lambda are fine.
- 1000:1 reads → ~1k redirects/s at that write rate. HTTP API + read Lambda + GetItem + cache handles this without a reserved instance.
- 100M DAU is a later problem of **read** concurrency and cache hit rate, not of table size.

---

## 9. Local vs AWS

| | Local HLD demo | AWS |
|---|---|---|
| Ingress | `ThreadingHTTPServer` 127.0.0.1 | HTTP API |
| Write/Read | one process, two routes (same split in code) | two Lambdas |
| Urls / counter / cache | in-memory, mutexes | DynamoDB + process cache |
| Clock | injectable for expiry tests | system UTC |

```bash
./scripts/local-demo.sh     # no account
./scripts/01-deploy.sh      # when the test account is ready
./scripts/99-destroy.sh
```
