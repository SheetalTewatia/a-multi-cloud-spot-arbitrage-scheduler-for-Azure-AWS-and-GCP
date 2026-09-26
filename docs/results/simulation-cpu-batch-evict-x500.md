# Simulated savings report: cpu-batch

> SIMULATED: stored prices replayed with a fake executor and random evictions. No cloud resources were used.
> Replayed 1 price snapshot(s) from 2026-09-25 15:29 UTC. Stored history ends 2026-09-26 08:31 UTC; after that, prices are held constant.
> Eviction multiplier 500, migration threshold 20%, seeds 0..19.

| | |
| --- | --- |
| Trials | 20 |
| Mean saved vs on-demand | 81.5% |
| Worst / best trial | 81.5% / 81.5% |
| Mean saved vs cheapest on-demand | 81.1% |
| Worst / best trial (cheapest) | 79.7% / 81.5% |
| Mean Tide cost | $0.0631 |
| Mean on-demand, same instance-hours | $0.3414 |
| Total evictions | 28 |
| Total migrations | 0 |
| Failed runs | 0 of 20 |
| Deadlines missed | 0 of 20 |

## Trials

| Run | Cost | On-demand | Saved | Saved (cheapest) | Evictions | Migrations | Hours | Deadline |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sim-20260926-083830-3dc27f92 | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083830-a469871b | $0.0678 | $0.3670 | 81.5% | 79.7% | 6 | 0 | 6.60 | met |
| sim-20260926-083830-eee44b0f | $0.0637 | $0.3447 | 81.5% | 80.9% | 2 | 0 | 6.20 | met |
| sim-20260926-083830-29ce34eb | $0.0627 | $0.3392 | 81.5% | 81.2% | 1 | 0 | 6.10 | met |
| sim-20260926-083830-d127b010 | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083830-64d020e2 | $0.0647 | $0.3503 | 81.5% | 80.6% | 3 | 0 | 6.30 | met |
| sim-20260926-083830-c275a47c | $0.0627 | $0.3392 | 81.5% | 81.2% | 1 | 0 | 6.10 | met |
| sim-20260926-083830-63f8a425 | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083830-950a198f | $0.0627 | $0.3392 | 81.5% | 81.2% | 1 | 0 | 6.10 | met |
| sim-20260926-083830-06df5fc3 | $0.0627 | $0.3392 | 81.5% | 81.2% | 1 | 0 | 6.10 | met |
| sim-20260926-083830-22f749c7 | $0.0627 | $0.3392 | 81.5% | 81.2% | 1 | 0 | 6.10 | met |
| sim-20260926-083830-b5750fd8 | $0.0637 | $0.3447 | 81.5% | 80.9% | 2 | 0 | 6.20 | met |
| sim-20260926-083830-23b28f46 | $0.0637 | $0.3447 | 81.5% | 80.9% | 2 | 0 | 6.20 | met |
| sim-20260926-083830-4ff613ce | $0.0627 | $0.3392 | 81.5% | 81.2% | 1 | 0 | 6.10 | met |
| sim-20260926-083830-80aaacd0 | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |
| sim-20260926-083830-32303b4e | $0.0647 | $0.3503 | 81.5% | 80.6% | 3 | 0 | 6.30 | met |
| sim-20260926-083830-551b8109 | $0.0637 | $0.3447 | 81.5% | 80.9% | 2 | 0 | 6.20 | met |
| sim-20260926-083830-cf054227 | $0.0627 | $0.3392 | 81.5% | 81.2% | 1 | 0 | 6.10 | met |
| sim-20260926-083830-ed62cbd8 | $0.0627 | $0.3392 | 81.5% | 81.2% | 1 | 0 | 6.10 | met |
| sim-20260926-083830-e4a44c30 | $0.0616 | $0.3336 | 81.5% | 81.5% | 0 | 0 | 6.00 | met |

## Decisions in sim-20260926-083830-a469871b

| At (h) | Event | Where | USD/hr | Reason |
| --- | --- | --- | --- | --- |
| 0.00 | place | azure centralindia Standard_D2as_v5 spot | 0.0103 | initial placement |
| 1.67 | evicted | azure centralindia Standard_D2as_v5 spot | 0.0103 | eviction notice |
| 1.67 | place | azure centralindia Standard_D2as_v5 spot | 0.0103 | replacement after eviction |
| 2.33 | evicted | azure centralindia Standard_D2as_v5 spot | 0.0103 | eviction notice |
| 2.33 | place | azure centralindia Standard_D2as_v5 spot | 0.0103 | replacement after eviction |
| 3.33 | evicted | azure centralindia Standard_D2as_v5 spot | 0.0103 | eviction notice |
| 3.33 | place | azure centralindia Standard_D2as_v5 spot | 0.0103 | replacement after eviction |
| 3.50 | evicted | azure centralindia Standard_D2as_v5 spot | 0.0103 | eviction notice |
| 3.50 | place | azure centralindia Standard_D2as_v5 spot | 0.0103 | replacement after eviction |
| 4.50 | evicted | azure centralindia Standard_D2as_v5 spot | 0.0103 | eviction notice |
| 4.50 | place | azure centralindia Standard_D2as_v5 spot | 0.0103 | replacement after eviction |
| 6.00 | evicted | azure centralindia Standard_D2as_v5 spot | 0.0103 | eviction notice |
| 6.00 | place | azure centralindia Standard_D2as_v5 spot | 0.0103 | replacement after eviction |
| 6.60 | finish | azure centralindia Standard_D2as_v5 spot | 0.0103 | finished after 6.60h |
