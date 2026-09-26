# Tide

Multi-cloud spot arbitrage scheduler. Tide treats AWS and Azure as one pool of compute,
places each CPU or GPU/AI workload on the cheapest spot vCPU-hour or GPU-hour that can
still meet its deadline,
migrates it when prices move or an eviction is signalled, and reconciles every decision
against the real cloud bill.

> Status: **Phase 1** — scaffold, local Postgres, CI. See `CLAUDE.md` for the full design
> and build order.

## Run locally

Requirements: Docker, Python 3.14.

```bash
cp .env.example .env            # then set POSTGRES_PASSWORD and DATABASE_URL
docker compose up -d --build    # starts Postgres + the API
curl localhost:8000/health      # {"status":"ok","db":"ok"}
```

Develop without Docker (Postgres still runs in Compose):

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
docker compose up -d db
alembic upgrade head
tide db-check
pytest
ruff check . && ruff format --check .
```

## Prices

```bash
tide collect                 # fetch current spot + on-demand prices once and store them
tide collect --watch         # keep collecting every 10 minutes (--interval-minutes to change)
tide prices                  # latest CPU prices, cheapest per vCPU-hour first
tide prices --gpu            # GPU types, cheapest per GPU-hour first
tide prices --spot-only --cloud azure --region eastus
```

Sources:

| Cloud | Spot | On-demand | Auth |
| --- | --- | --- | --- |
| AWS | EC2 `DescribeSpotPriceHistory` (per availability zone) | Price List API | read-only IAM, see [docs/permissions.md](docs/permissions.md) |
| Azure | Retail Prices API, `... Spot` meters (per region) | Retail Prices API, pay-as-you-go meters | none (public API) |

Every price is normalized to **USD per vCPU-hour** and **USD per GB-RAM-hour**, and GPU
types also to **USD per GPU-hour**, using the sizes in [`catalog.yaml`](catalog.yaml): a
hand-picked list of comparable Linux types in Mumbai/Central India and N. Virginia/East US.

| | AWS | Azure |
| --- | --- | --- |
| CPU | m5.large, m5.xlarge, t3.large | D2s_v5, D4s_v5, D2as_v5 |
| T4 16 GB | g4dn.xlarge | NC4as_T4_v3 |
| A10 24 GB | g5.xlarge (A10G) | NV36ads_A10_v5 |
| L4 24 GB | g6.xlarge | - |
| A100 (reference only) | p4d.24xlarge (8 GPUs) | NC24ads_A100_v4 |

Reference-only types are priced for comparison but never placed or launched. Each collection appends rows to the `prices` table, so it doubles as
price history.

Known limitations:
- Azure Spot prices from the Retail Prices API are list prices that Azure updates
  periodically, not a live per-zone market like AWS.
- Azure B-series is excluded because it has no Spot pricing.
- The per-GPU-hour price divides the whole VM price by its GPU count, so it includes the
  bundled vCPUs and RAM (Azure's NV36ads_A10_v5 bundles 36 vCPUs with one A10, for example).

## Layout

```
tide/
  api/          FastAPI app
  collectors/   price feeds per cloud (eviction risk arrives with the scorer)
  scorer/       effective-cost model (Phase 3)
  scheduler/    placement + migration loop
  executor/     launch/terminate on each cloud
  checkpoint/   save/restore workload state
  billing/      real-cost reconciliation
  exporter/     Prometheus metrics
alembic/        database migrations
catalog.yaml    instance types + regions Tide prices
infra/terraform one module per cloud (empty until Phases 5-6)
```

## CI

GitHub Actions runs on every push and PR: ruff lint, pytest (against a Postgres service),
Docker build + Trivy scan, and `terraform fmt` / `validate`.
