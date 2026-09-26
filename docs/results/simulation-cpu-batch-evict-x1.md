# Simulated savings report: cpu-batch

> SIMULATED: stored prices replayed with a fake executor and random evictions. No cloud resources were used.
> Replayed 1 price snapshot(s) from 2026-09-25 15:29 UTC. Stored history ends 2026-09-26 08:31 UTC; after that, prices are held constant.
> Eviction multiplier 1, migration threshold 20%, seeds 0..19.

| | |
| --- | --- |
| Trials | 20 |
| Mean saved vs on-demand | 81.5% |
| Worst / best trial | 81.5% / 81.5% |
| Mean saved vs cheapest on-demand | 81.5% |
| Worst / best trial (cheapest) | 81.5% / 81.5% |
| Mean Tide cost | $0.0616 |
| Mean on-demand, same instance-hours | $0.3336 |
| Total evictions | 0 |
| Total migrations | 0 |
| Failed runs | 0 of 20 |
| Deadlines missed | 0 of 20 |

## Trials

| Run | Cost | On-demand | Saved | Saved (cheapest) | Evictions | Migrations | Hours | Deadline |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sim-20260926-083824-d7e687fa | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083824-a279cb2d | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083824-061c77a7 | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083824-43b5a8b9 | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083824-360a3dda | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083824-aa96c6a2 | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083824-af90a7f0 | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083824-ceb9302d | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083824-8af7deb2 | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083824-f53bfe28 | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083824-459fec00 | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083824-b59afc53 | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083824-9edb3680 | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083824-ea949a16 | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083824-b8e791c0 | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083824-fb7c4a76 | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083824-44269883 | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083824-ad618a25 | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083824-a1fb003c | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083824-fe74af40 | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |

## Decisions in sim-20260926-083824-d7e687fa

| At (h) | Event | Where | USD/hr | Reason |
| --- | --- | --- | --- | --- |
| 0.00 | place | azure centralindia Standard_D2as_v5 spot | 0.0103 | initial placement |
| 6.00 | finish | azure centralindia Standard_D2as_v5 spot | 0.0103 | finished after 6.00h |
