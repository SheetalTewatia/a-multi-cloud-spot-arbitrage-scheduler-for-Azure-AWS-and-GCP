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

## Layout

```
tide/
  api/          FastAPI app
  collectors/   price + eviction-risk feeds (Phase 2)
  scorer/       effective-cost model (Phase 3)
  scheduler/    placement + migration loop
  executor/     launch/terminate on each cloud
  checkpoint/   save/restore workload state
  billing/      real-cost reconciliation
  exporter/     Prometheus metrics
alembic/        database migrations
infra/terraform one module per cloud (empty until Phase 5)
```

## CI

GitHub Actions runs on every push and PR: ruff lint, pytest (against a Postgres service),
Docker build + Trivy scan, and `terraform fmt` / `validate`.
