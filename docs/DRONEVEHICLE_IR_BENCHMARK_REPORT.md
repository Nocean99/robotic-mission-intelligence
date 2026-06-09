# DroneVehicle IR Local Benchmark Report

This is a local-only baseline for the DroneVehicle infrared vehicle benchmark. No OpenAI/API evaluation was used.

## Dataset

Full labels:

```text
datasets/benchmarks/vehicles/dronevehicle_ir_labels.csv
```

Local subset:

```text
logs/benchmark_samples/dronevehicle_ir_local_500
```

The full infrared label file contains 28,439 IR images. For this baseline, Aegis used a 500-image subset because the full dataset is large:

- 447 positive vehicle images
- 53 negative images

This is not perfectly balanced because the full IR label file only contains 53 negative image cases.

## Run

Report:

```text
logs/mission_evaluations/dronevehicle_ir_vehicle_proposals/20260608T165809Z/mission_evaluation_report.html
```

Command:

```bash
./scripts/run_mission_evaluation.sh \
  logs/benchmark_samples/dronevehicle_ir_local_500/images \
  --mission-request "Search infrared aerial imagery for vehicles relevant to incident response" \
  --labels-csv logs/benchmark_samples/dronevehicle_ir_local_500/labels.csv \
  --semantic-vision local \
  --full-frame-semantic misses \
  --max-saved-candidates 500
```

## Results

| Metric | Result |
|---|---:|
| Images processed | 500 |
| Positive images | 447 |
| Negative images | 53 |
| Local detections | 500 |
| Semantic errors | 0 |

Confirmed-match metrics:

| Metric | Result |
|---|---:|
| Precision | 0.8976 |
| Recall | 1.0000 |
| F1 | 0.9460 |

Analyst-capture metrics:

| Metric | Result |
|---|---:|
| Capture precision | 0.8940 |
| Capture recall | 1.0000 |
| Capture F1 | 0.9440 |

Stage health:

| Stage | Status |
|---|---|
| Mission command | ok |
| Vision plan | ok |
| Contextual search plan | ok |
| Evidence collection | ok |
| Vision benchmark | ok |

## Interpretation

The mission pipeline ran successfully, and the new infrared-aware proposal layer moved the IR benchmark from zero detections to full capture recall on this subset.

This is a strong thermal-style local baseline. The hot-blob proposal mode preserved vehicle evidence across the positive IR cases without using OpenAI/API review.

Proposal reasons:

- hot IR blob: 498
- full-frame fallback: 2

Remaining weakness:

The IR local layer is now useful as a triage/proposal stage. The next improvement should tune ranking against the 53 negative cases so the queue stays tighter without sacrificing recall.
