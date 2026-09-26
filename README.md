# Tide

Multi-cloud spot arbitrage scheduler. Tide treats AWS and Azure as one pool of compute,
places each CPU or GPU/AI workload on the cheapest spot vCPU-hour or GPU-hour that can
still meet its deadline, migrates it when prices move or an eviction is signalled, and
reconciles every decision against the real cloud bill.

> Status: **Phase 4**: live CPU + GPU prices, eviction risk, a scorer that ranks
> placements (`tide plan`), and a simulation mode that runs the full scheduler on replayed
> prices (`tide simulate`). See `CLAUDE.md` for the full design and build order.

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
tide collect                 # fetch prices + eviction risks once and store them
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

Reference-only types are priced for comparison but never placed or launched. Each
collection appends rows to the `prices` table, so it doubles as price history.

## Eviction risk

Each spot option gets `p_evict`, an eviction probability per hour:

| Cloud | Source |
| --- | --- |
| AWS | The public [Spot Instance Advisor](https://aws.amazon.com/ec2/spot/instance-advisor/) feed: a monthly "frequency of interruption" bucket (`<5%`, `5-10%`, ... `>20%`) per type and region. |
| Azure | A static table in `catalog.yaml`. These values are **assumed**, not measured: the real data (Azure Resource Graph `SpotResources`) needs credentials. GPU sizes are assumed one bucket riskier than CPU sizes. |

The bucket becomes an hourly probability by taking its middle and spreading it over the
730 hours in a month (`5-10%` becomes 0.075 / 730 = 0.0001 per hour). If a source has no
data for a type, Tide assumes the worst bucket (`>20%`), never zero.

## Scoring (`tide plan`)

```bash
tide plan workloads/cpu-batch.yaml          # 6h CPU job, 10h deadline
tide plan workloads/cpu-no-slack.yaml       # deadline = runtime: falls back to on-demand
tide plan workloads/gpu-finetune.yaml       # any GPU with >= 16 GB memory
tide plan workloads/gpu-inference-t4.yaml   # pinned to a T4
tide plan workloads/gpu-finetune.yaml --show-rejected   # every candidate, with the reason
```

A workload file gives the runtime, deadline, restart overhead and minimum hardware
(vCPUs and RAM, or a GPU model and/or minimum GPU memory). Tide scores every priced option
with:

```
expected_restarts = p_evict * runtime_hours
effective_cost    = spot_price * runtime_hours
                  + expected_restarts * restart_overhead_hours * spot_price
feasible          = runtime_hours + expected_restarts * restart_overhead_hours <= deadline
choose            = feasible spot option with the lowest effective_cost
fallback          = cheapest feasible on-demand option if no spot option is feasible
```

Prices are for the whole instance, since that is what you pay for. Options that can't run
the workload are kept in the output with the reason (too small, wrong GPU, reference-only)
so every decision can be audited. The result also shows the saving against on-demand for
the same instance type and region.

## Simulation (`tide simulate`)

```bash
tide simulate workloads/cpu-batch.yaml                        # one run, savings report
tide simulate workloads/gpu-finetune.yaml --trials 20         # 20 runs with different seeds
tide simulate workloads/cpu-batch.yaml --trials 20 --eviction-multiplier 500   # stress test
tide simulate workloads/cpu-batch.yaml --markdown docs/results/my-report.md
tide runs                                                      # recent runs
tide report <run-id>                                           # one run's report + decisions
```

Simulation runs the real scheduler loop against **stored price history** with a
**fake executor**, so it costs nothing. Every 10 simulated minutes the loop:

1. places the workload if it isn't running (first start, or after an eviction);
2. otherwise migrates if a feasible option is **more than 20% cheaper** for the remaining
   work (the threshold stops it flapping between near-equal prices);
3. runs for 10 minutes at the current price, then checks for an eviction notice. The fake
   executor draws evictions at random from each option's `p_evict` (scaled by
   `--eviction-multiplier`).

Each eviction or migration costs `restart_overhead_hours` of paid time with no progress.
If an eviction makes the deadline impossible, the job finishes late on on-demand and the
report shows the deadline as missed. Every decision is saved with the full list of scored
candidates (the `decisions` table), and each run's totals go in the `runs` table.

The savings report compares Tide's actual cost with two baselines:

| Baseline | Meaning |
| --- | --- |
| On-demand, same instance-hours | The same instance types, regions and hours, at on-demand prices. This is the headline "% saved". |
| Cheapest on-demand for the job | Running the whole job once, with no restarts, on the cheapest on-demand option across both clouds. Stricter: eviction overhead counts against Tide. |

Reports so far are in [docs/results/](docs/results/). They are simulations, and they are
only as good as the stored history: run `tide collect --watch` for a few days before
drawing conclusions.

## Known limitations

- Azure Spot prices from the Retail Prices API are list prices that Azure updates
  periodically, not a live per-zone market like AWS.
- Azure B-series is excluded because it has no Spot pricing.
- The per-GPU-hour price divides the whole VM price by its GPU count, so it includes the
  bundled vCPUs and RAM (Azure's NV36ads_A10_v5 bundles 36 vCPUs with one A10, for example).
- AWS only publishes eviction risk as monthly buckets, so the hourly `p_evict` values are
  small (0.00003 to 0.0003). For jobs of a few hours, eviction risk rarely changes the
  ranking; it matters for long jobs, large restart overheads and deadlines with little
  slack. Simulation mode (Phase 4) will test how sensitive savings are to this assumption.
- Azure eviction rates are assumed values until Resource Graph access is set up.
- Simulated savings replay real prices but not real capacity: the fake executor always
  gets the instance it asks for, and evictions are random draws from `p_evict`.
- Azure spot list prices rarely change, and AWS spot prices move slowly, so with short
  history the simulator seldom sees a price gap above the 20% migration threshold.
- A GPU workload has one runtime for every GPU model, so a faster GPU (A10 vs T4) gets no
  credit for finishing sooner. Per-GPU throughput from a benchmark run comes in Phase 7.

## Layout

```
tide/
  api/          FastAPI app
  collectors/   price + eviction-risk feeds per cloud
  scorer/       workload definitions, effective-cost model, candidate loading
  scheduler/    placement + migration loop, fake executor, replay, savings reports
  executor/     launch/terminate on each cloud
  checkpoint/   save/restore workload state
  billing/      real-cost reconciliation
  exporter/     Prometheus metrics
alembic/        database migrations
catalog.yaml    instance types, regions, Azure static eviction table
workloads/      example workload files for `tide plan` and `tide simulate`
docs/results/   savings reports (simulated for now)
infra/terraform one module per cloud (empty until Phases 5-6)
```

## CI

GitHub Actions runs on every push and PR: ruff lint, pytest (against a Postgres service),
Docker build + Trivy scan, and `terraform fmt` / `validate`.
