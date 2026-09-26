# Results

Savings reports produced by Tide. Every file says whether it is **simulated** or a real
run; nothing here is presented as a real cloud bill unless it says "reconciled".

| Report | Kind | Workload | Eviction risk |
| --- | --- | --- | --- |
| [simulation-cpu-batch-evict-x1.md](simulation-cpu-batch-evict-x1.md) | simulated, 20 trials | 6h CPU batch job | as measured |
| [simulation-cpu-batch-evict-x500.md](simulation-cpu-batch-evict-x500.md) | simulated, 20 trials | 6h CPU batch job | 500x (stress test) |
| [simulation-gpu-finetune-evict-x1.md](simulation-gpu-finetune-evict-x1.md) | simulated, 20 trials | 3h GPU fine-tune, >= 16 GB | as measured |
| [simulation-gpu-finetune-evict-x500.md](simulation-gpu-finetune-evict-x500.md) | simulated, 20 trials | 3h GPU fine-tune, >= 16 GB | 500x (stress test) |

These first reports replay about one day of price history (collected 2026-09-25/26), so
prices barely move within a run. Regenerate them after a few days of `tide collect --watch`:

```bash
tide simulate workloads/cpu-batch.yaml --trials 20 --markdown docs/results/simulation-cpu-batch-evict-x1.md
```
