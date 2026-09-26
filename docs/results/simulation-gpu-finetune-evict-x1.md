# Simulated savings report: gpu-finetune

> SIMULATED: stored prices replayed with a fake executor and random evictions. No cloud resources were used.
> Replayed 4 price snapshot(s) from 2026-09-26 07:10 UTC. Stored history ends 2026-09-26 08:31 UTC; after that, prices are held constant.
> Eviction multiplier 1, migration threshold 20%, seeds 0..19.

| | |
| --- | --- |
| Trials | 20 |
| Mean saved vs on-demand | 71.6% |
| Worst / best trial | 71.6% / 71.6% |
| Mean saved vs cheapest on-demand | 71.6% |
| Worst / best trial (cheapest) | 71.6% / 71.6% |
| Mean Tide cost | $0.4475 |
| Mean on-demand, same instance-hours | $1.5780 |
| Total evictions | 0 |
| Total migrations | 0 |
| Failed runs | 0 of 20 |
| Deadlines missed | 0 of 20 |

## Trials

| Run | Cost | On-demand | Saved | Saved (cheapest) | Evictions | Migrations | Hours | Deadline |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sim-20260926-083835-2b5c59e6 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083835-0215a1b7 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083835-7ac33f94 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083835-6aa1f771 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083835-462f40c1 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083835-2f9ef60c | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083835-45786d59 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083835-ece01b0e | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083835-b42b79b2 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083835-11ae13b8 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083835-c2f429d7 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083835-263a7d6d | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083835-a9b164de | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083835-a028d24c | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083835-229402c3 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083835-e92d01a2 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083835-6aba2369 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083835-d38bfa00 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083835-0034465a | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |
| sim-20260926-083835-974adba6 | $0.4475 | $1.5780 | 71.6% | 71.6% | 0 | 0 | 3.00 | met |

## Decisions in sim-20260926-083835-2b5c59e6

| At (h) | Event | Where | USD/hr | Reason |
| --- | --- | --- | --- | --- |
| 0.00 | place | azure eastus Standard_NC4as_T4_v3 spot | 0.1492 | initial placement |
| 3.00 | finish | azure eastus Standard_NC4as_T4_v3 spot | 0.1492 | finished after 3.00h |
