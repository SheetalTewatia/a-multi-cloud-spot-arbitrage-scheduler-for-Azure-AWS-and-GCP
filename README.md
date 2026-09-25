# Tide

Multi-cloud spot arbitrage scheduler. Tide treats AWS and Azure as one pool of compute,
places each workload on the cheapest spot vCPU-hour that can still meet its deadline,
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
tide prices                  # latest prices, cheapest per vCPU-hour first
tide prices --spot-only --cloud azure --region eastus
```

Sources:

| Cloud | Spot | On-demand | Auth |
| --- | --- | --- | --- |
| AWS | EC2 `DescribeSpotPriceHistory` (per availability zone) | Price List API | read-only IAM, see [docs/permissions.md](docs/permissions.md) |
| Azure | Retail Prices API, `... Spot` meters (per region) | Retail Prices API, pay-as-you-go meters | none (public API) |

Every price is normalized to **USD per vCPU-hour** and **USD per GB-RAM-hour** using the
vCPU and memory sizes in [`catalog.yaml`](catalog.yaml), a hand-picked list of comparable
general-purpose Linux types (AWS m5/t3, Azure Dsv5/Dasv5) in Mumbai/Central India and
N. Virginia/East US. Each collection appends rows to the `prices` table, so it doubles as
price history.

Known limitations:
- Azure Spot prices from the Retail Prices API are list prices that Azure updates
  periodically, not a live per-zone market like AWS.
- Azure B-series is excluded because it has no Spot pricing.

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
