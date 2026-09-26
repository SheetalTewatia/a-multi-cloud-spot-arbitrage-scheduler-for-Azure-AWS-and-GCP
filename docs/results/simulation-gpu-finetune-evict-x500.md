# Simulated savings report: gpu-finetune

> SIMULATED: stored prices replayed with a fake executor and random evictions. No cloud resources were used.
> Replayed 4 price snapshot(s) from 2026-09-26 07:10 UTC. Stored history ends 2026-09-26 08:31 UTC; after that, prices are held constant.
> Eviction multiplier 500, migration threshold 20%, seeds 0..19.

| | |
| --- | --- |
| Trials | 20 |
| Mean saved vs on-demand | 71.6% |
| Worst / best trial | 71.6% / 71.6% |
| Mean saved vs cheapest on-demand | 70.1% |
| Worst / best trial (cheapest) | 66.9% / 71.6% |
| Mean Tide cost | $0.4718 |
| Mean on-demand, same instance-hours | $1.6635 |
| Total evictions | 13 |
| Total migrations | 0 |
| Failed runs | 0 of 20 |
| Deadlines missed | 0 of 20 |

## Trials

| Run | Cost | On-demand | Saved | Saved (cheapest) | Evictions | Migrations | Hours | Deadline |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sim-20260926-083841-952588b4 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083841-08249c95 | $0.5221 | $1.8410 | 71.6% | 66.9% | 2 | 0 | 3.50 | met |
| sim-20260926-083841-a77f3222 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083841-c1d94be5 | $0.4848 | $1.7095 | 71.6% | 69.3% | 1 | 0 | 3.25 | met |
| sim-20260926-083841-2bf34f68 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083841-a3eb468a | $0.5221 | $1.8410 | 71.6% | 66.9% | 2 | 0 | 3.50 | met |
| sim-20260926-083841-879f363c | $0.4848 | $1.7095 | 71.6% | 69.3% | 1 | 0 | 3.25 | met |
| sim-20260926-083841-b2028940 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083841-17339b36 | $0.4848 | $1.7095 | 71.6% | 69.3% | 1 | 0 | 3.25 | met |
| sim-20260926-083841-a7084f3b | $0.4848 | $1.7095 | 71.6% | 69.3% | 1 | 0 | 3.25 | met |
| sim-20260926-083841-8bef94de | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083841-e60e2fc1 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083841-f6e04ac9 | $0.4848 | $1.7095 | 71.6% | 69.3% | 1 | 0 | 3.25 | met |
| sim-20260926-083841-04cc2d4d | $0.4848 | $1.7095 | 71.6% | 69.3% | 1 | 0 | 3.25 | met |
| sim-20260926-083841-74546ce0 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083841-3ad0371e | $0.4848 | $1.7095 | 71.6% | 69.3% | 1 | 0 | 3.25 | met |
| sim-20260926-083841-b46af1c4 | $0.4848 | $1.7095 | 71.6% | 69.3% | 1 | 0 | 3.25 | met |
| sim-20260926-083841-f9c1bada | $0.4848 | $1.7095 | 71.6% | 69.3% | 1 | 0 | 3.25 | met |
| sim-20260926-083841-2eadbb15 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083841-70f00601 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |

## Decisions in sim-20260926-083841-08249c95

| At (h) | Event | Where | USD/hr | Reason |
| --- | --- | --- | --- | --- |
| 0.00 | place | azure eastus Standard_NC4as_T4_v3 spot | 0.1492 | initial placement |
| 1.67 | evicted | azure eastus Standard_NC4as_T4_v3 spot | 0.1492 | eviction notice |
| 1.67 | place | azure eastus Standard_NC4as_T4_v3 spot | 0.1492 | replacement after eviction |
| 2.33 | evicted | azure eastus Standard_NC4as_T4_v3 spot | 0.1492 | eviction notice |
| 2.33 | place | azure eastus Standard_NC4as_T4_v3 spot | 0.1492 | replacement after eviction |
| 3.50 | finish | azure eastus Standard_NC4as_T4_v3 spot | 0.1492 | finished after 3.50h |
