# Performance Testing — ShopMate AI

Load and stress tests for the Django REST API using Locust against a
dedicated PostgreSQL database (`chatbot_perf`) on the same Supabase
project as development.

## Environment

| Item | Value |
|---|---|
| App server | uvicorn 0.54 (ASGI), 2 workers, `performance/run_server.py` |
| Database | Supabase PostgreSQL, **transaction-mode pooler (port 6543)** |
| DB connections | `DB_CONN_MAX_AGE=0` (close at request end) |
| Dataset | 1 store, 25 active products, 50 customer accounts, owner account |
| User mix | 55% anonymous shoppers, 20% store owner, 25% customers |
| Think time | 0.5–2.0 s between tasks |
| Client | Locust 2.47, headless mode, run from repo root |

## Why transaction pooler (6543)

The Supabase **session-mode pooler (port 5432) caps clients at
`pool_size: 15`**. With Django's per-thread connections this produced
`EMAXCONNSESSION` 500s at just 10 concurrent users. The transaction
pooler multiplexes connections (client cap 200) and is the supported
mode for multi-worker Django. `settings.py` sets
`prepare_threshold=None` in `DATABASES["default"]["OPTIONS"]`, which is
required for transaction pooling (psycopg3 prepared statements are
session-scoped).

## Setup

```powershell
# 1. Create + migrate + seed the perf database (drops/recreates it)
uv run python performance/setup_perf_db.py

# 2. Start the app against chatbot_perf (terminal 1)
uv run python performance/run_server.py

# 3. Run load tests (terminal 2)
uv run locust -f performance/locustfile.py --host http://127.0.0.1:8000 --headless -u 100 -r 10 -t 120s --csv performance/reports/users_100

# 4. Resource monitor (optional, terminal 3)
uv run python performance/monitor.py --tag users_100 --seconds 200

# 5. Summarize CSVs
uv run python performance/summarize.py
```

Test accounts (perf DB only, never production):

- Owner: `perf_owner` / `PerfOwner123!`
- Customers: `perf_cust_01` … `perf_cust_50` / `PerfCustomer123!`

## Scenarios covered

- Anonymous: product browse/search, inventory list, price list,
  price calculation.
- Owner: management product/inventory/price lists, price history.
- Customer: cart view/add/update/remove, order history,
  confirm→cancel cycle (cancel releases reservations so the scenario
  is repeatable without draining stock).

Response policy: HTTP 5xx, 401, 403 count as failures; other 4xx are
business rejections (e.g. insufficient stock, cart races between users
sharing an account) and are recorded as successful.

## Results (2026-11-15, remote Supabase ap-southeast-2)

| Users | Requests | Failures | RPS | P50 | P95 | P99 | Max |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10  | 192  | 0    (0.00%) | 2.2  | 2.8s  | 7.6s  | 8.6s  | 8.7s  |
| 50  | 972  | 1    (0.10%) | 8.2  | 2.6s  | 7.4s  | 8.8s  | 13.3s |
| 100 | 2531 | 2    (0.08%) | 21.3 | 2.6s  | 7.2s  | 8.9s  | 13.9s |
| 250 | 5194 | 27   (0.52%) | 43.7 | 3.4s  | 9.6s  | 16.0s | 21.3s |
| 500 | 6657 | 594  (8.92%) | 44.5 | 5.4s  | 24.0s | 39.0s | 56.1s |

Stress-test outcome at 500 users: throughput plateaued (~44 RPS, same
as 250), latency degraded sharply, and ~9% of requests failed with
500s caused by the pooler's 200-client connection cap
(`EMAXCONN`). Recovery after load removal was verified (endpoints
returned 200 immediately).

Raw data: `reports/users_*_stats.csv`, `*_failures.csv`,
`resources_*.csv`.
