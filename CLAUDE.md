# Tide: Multi-Cloud Spot Arbitrage Scheduler

## What this project is

Tide treats AWS and Azure as one pool of compute. GCP is out of scope for now. It handles two kinds of workloads:

- CPU workloads (batch jobs), priced per vCPU-hour.
- GPU / AI workloads (model fine-tuning, batch inference), priced per GPU-hour for a given GPU model.

For each workload it:

1. Finds the cheapest spot vCPU-hour or GPU-hour across the two clouds.
2. Adjusts that price for eviction risk and the workload's deadline.
3. Places the workload on the best option.
4. Migrates it (checkpoint, then restart elsewhere) when prices move or an eviction is signalled.
5. Logs every decision and reconciles it against the real cloud bill, so the savings can be audited.

Repo: https://github.com/SheetalTewatia/a-multi-cloud-spot-arbitrage-scheduler-for-Azure-AWS-and-GCP

This is a portfolio project for a Cloud/DevOps engineer with 1 year of experience. Keep the code simple enough that she can explain every part in an interview. Prefer clear and working over clever and complete.

## Resume claims this project must back up

The finished project must honestly support these bullets:

- Designed a scheduler that places CPU and GPU/AI workloads on the cheapest spot capacity across AWS and Azure.
- Scored placements on price, eviction risk and deadline, cutting compute cost by 60% vs. on-demand.
- Automated migration on price or eviction signals and reconciled savings against real cloud bills.

The 60% figure must come from a real measurement: Tide's actual spot cost compared with the on-demand price for the same vCPU-hours or GPU-hours. That comparison must appear in the savings report. If the measured number is different, report the real number.

## Tech stack

- Language: Python 3.14, using FastAPI for the API and Typer for the CLI.
- Storage: PostgreSQL for prices, decisions, runs and bills. Use SQLAlchemy and Alembic.
- Infrastructure: Terraform, with one module per cloud (small spot VM, network, S3 bucket / Azure Blob container).
- Containers: Docker for the scheduler and for the sample workloads. Use Docker Compose for local development.
- Orchestration: the scheduler itself runs on Kubernetes (kind locally, a Helm chart for any cluster).
- Observability: a Prometheus exporter on the scheduler, plus Grafana dashboards committed as JSON.
- CI: GitHub Actions for lint (ruff), tests (pytest), Docker build and Trivy scan, and terraform fmt/validate.

## Architecture

```
collectors/   price + eviction-risk feeds, one per cloud
scorer/       effective-cost model
scheduler/    placement decisions, migration loop
executor/     launches/terminates workloads on each cloud (Terraform or SDK)
checkpoint/   save/restore workload state to object storage
billing/      pulls real costs, reconciles with decisions
api/          FastAPI: submit workload, list decisions, savings report
exporter/     Prometheus metrics
```

### 1. Price collectors (run every 10 minutes)

- AWS: EC2 `DescribeSpotPriceHistory` (boto3) for the chosen instance types and regions, plus on-demand prices from the Price List API.
- Azure: the Retail Prices API (public, no auth needed). Filter on spot meters (`meterName` contains "Spot") and the matching on-demand meters.
- Normalize everything to USD per vCPU-hour and USD per GB-RAM-hour, and store it with a timestamp.

#### GPU pricing

- Collect spot and on-demand prices for GPU instances through the same APIs:
  - AWS: g4dn (T4), g5 (A10G), g6 (L4), and p-family as reference only.
  - Azure: NCasT4_v3 (T4), NVadsA10_v5 (A10), NC A100 v4 as reference only.
- Normalize GPU prices to USD per GPU-hour, keyed by GPU model (T4, A10/A10G, L4, A100), along with GPU memory (GB), vCPUs and RAM.
- A GPU workload asks for a GPU model or a minimum GPU memory (for example "any GPU with at least 16 GB"). The scorer compares only instances that meet that requirement.
- Also report a cost per unit of work for AI jobs: cost per 1,000 inferences, or cost per training epoch. Use throughput numbers measured in a benchmark run, with a hand-entered table as a fallback.
- GPU spot prices and availability differ a lot by region. Include at least 2 regions per cloud in the GPU catalogue.

Keep the instance catalogue small and hand-curated in `catalog.yaml`: about 3 comparable general-purpose types per cloud (for example t3/m5 on AWS and B/D-series v5 on Azure) across 2–3 regions, such as ap-south-1 / Central India and us-east-1 / East US.

### 2. Eviction risk

- AWS: the Spot Instance Advisor interruption-frequency data (the public JSON feed), or the Spot Placement Score API.
- Azure: spot eviction rates from Azure Resource Graph (`SpotResources`), if accessible. Otherwise use a static table.
- Output: an eviction probability per hour, `p_evict`, for each (cloud, region, type). GPU spot instances are usually evicted more often than CPU ones, and the data should reflect that.

### 3. Scoring model (keep it explainable)

```
expected_restarts = p_evict * runtime_hours
effective_cost    = spot_price * runtime_hours
                  + expected_restarts * restart_overhead_hours * spot_price
feasible          = expected finish time (including restart overhead) <= deadline
choose            = feasible option with the lowest effective_cost
fallback          = on-demand if no spot option meets the deadline
```

The same formula applies to GPU workloads, using price per GPU-hour. For GPU jobs, `restart_overhead_hours` should include model and checkpoint reload time, which can be several minutes.

Log every candidate and its score, not just the winner. This log is the audit trail.

### 4. Workloads, checkpointing and migration

- CPU sample workload: a containerized batch job (for example a long CPU-bound computation or a video transcode) that saves progress to object storage every N minutes and resumes from the last checkpoint.
- GPU sample workload: a small PyTorch job, either fine-tuning a small model (for example DistilBERT on a public dataset) or batch inference over a dataset. It saves model and optimizer state (or the last processed batch index) to S3 / Azure Blob every N steps, and resumes from there on any GPU instance. Use an official CUDA/PyTorch base image.
- Migrate when a cheaper feasible option beats the current one by more than a threshold (default 20%, which prevents flapping), or when an eviction notice arrives:
  - AWS: the 2-minute notice from instance metadata.
  - Azure: Scheduled Events.
- Migration steps: checkpoint, launch on the new target, resume, terminate the old instance, and record a decision event.

### 5. Billing reconciliation

- AWS: Cost Explorer, filtered by a `tide-run-id` tag.
- Azure: the Cost Management Query API, filtered by the same tag.
- Bills lag by 24–48 hours. Show "estimated" costs until the real bill arrives, then "reconciled".
- Savings report per run: actual spot cost, on-demand equivalent, % saved, number of migrations and number of evictions. For GPU runs, also include cost per GPU-hour and cost per 1,000 inferences or per epoch.

## Cost guardrails (important)

- Never create cloud resources without asking first. Always show the Terraform plan before applying.
- Use the smallest instance types, and at most 1–2 VMs running at any time.
- Every resource gets `project=tide` and `tide-run-id` tags, and an auto-terminate TTL (default 2 hours).
- Add `tide destroy-all` to clean up everything tagged `project=tide`.
- GPU quota: new AWS and Azure accounts usually have a spot GPU quota of 0. AWS needs a quota increase for "All G and VT Spot Instance Requests"; Azure needs one for the spot vCPU family. Request a small increase (4 vCPUs is enough for one T4) and wait for approval. Until then, GPU work runs in pricing, planning and simulation mode only.
- For real GPU runs, use only the smallest T4 instances (AWS g4dn.xlarge, Azure NC4as_T4_v3), one at a time, with a 1-hour TTL. Never launch A100/H100 instances. Those are for price comparison only.
- Build a `--dry-run` / simulation mode first. It runs the full scheduler against live prices but uses a fake executor, so most development costs $0.

## Security

- No credentials in code or git. Read them from environment variables or local cloud CLI profiles, and commit a `.env.example`.
- Use least-privilege access: an IAM role/user on AWS and a service principal on Azure. Document the exact permissions needed in `docs/permissions.md`.

## Build order (one phase at a time; confirm each works before moving on)

1. Repo scaffold, Docker Compose (Postgres), and CI pipeline.
2. Price collectors for AWS and Azure (CPU and GPU), `catalog.yaml`, and the `tide prices` CLI command (with a `--gpu` filter).
3. Scorer with unit tests (including GPU requirement matching), and the `tide plan <workload.yaml>` command showing the ranked options.
4. Simulation mode: replay stored prices with simulated evictions, and produce a savings report.
5. Executor for one cloud (start with AWS), plus the CPU checkpointing sample workload.
6. Executor for Azure, and migration between AWS and Azure.
7. GPU sample workload and a real T4 spot run (only once the quota is approved).
8. Billing reconciliation, Prometheus exporter and Grafana dashboards, including a GPU price comparison panel.
9. Helm chart, deployment to kind, and final README.

## Definition of done

- The README includes an architecture diagram, setup steps, a demo GIF or screenshots, the scoring formula, and the known limitations.
- There is at least one real AWS + Azure run with a reconciled savings report committed to `docs/results/`.
- There is a GPU price comparison report (T4/A10/L4/A100, spot vs. on-demand, AWS vs. Azure) in `docs/results/`. It includes a real GPU run if the quota was approved; otherwise it is clearly marked as simulated.
- CI is green, and the tests cover the scorer and the collectors' normalization.
- Commits are small and meaningful. Don't dump the whole project in one commit.