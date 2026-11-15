Baseline: `baseline` (git 252e078, seed 42) · PoC: `poc` (git 252e078, seed 42)

| Metric (unit) | Slice | Baseline | PoC | Δ abs | Δ rel | Better | N |
|---|---|---|---|---|---|---|---|
| **Defect Recall@B** (GT defects in top-B / GT defects) | all | 0.4545 | 0.7727 | 0.3182 | +70.0% | higher | 40 |
| Precision@B (GT defects in top-B / B) | all | 0.5000 | 0.8500 | 0.3500 | +70.0% | higher | 40 |
| False alarm in top-B (clean in top-B / clean) | light=day | 0.3333 | 0.3333 | 0.0000 | +0.0% | lower | 20 |
| False alarm in top-B (clean in top-B / clean) | light=dusk | 1.0000 | 0.0000 | -1.0000 | -100.0% | lower | 4 |
| False alarm in top-B (clean in top-B / clean) | light=night | 0.7143 | 0.0000 | -0.7143 | -100.0% | lower | 16 |
| Runtime / 100 items (s) | all | 0.0928 | 0.8583 | | | lower | |
