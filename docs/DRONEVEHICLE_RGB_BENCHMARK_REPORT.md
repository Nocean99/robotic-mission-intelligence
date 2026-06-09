# DroneVehicle RGB Local Benchmark Report

This is a local-only baseline for the DroneVehicle RGB vehicle benchmark. No OpenAI/API evaluation was used.

## Dataset

Full labels:

```text
datasets/benchmarks/vehicles/dronevehicle_rgb_labels.csv
```

Local subset:

```text
logs/benchmark_samples/dronevehicle_rgb_local_500
```

The full RGB label file contains 28,439 RGB images. For this baseline, Aegis used a 500-image subset because the full dataset is large:

- 250 positive vehicle images
- 250 negative images

## Run

Report:

```text
logs/mission_evaluations/dronevehicle_rgb_vehicle_proposals/20260608T165935Z/mission_evaluation_report.html
```

Command:

```bash
./scripts/run_mission_evaluation.sh \
  logs/benchmark_samples/dronevehicle_rgb_local_500/images \
  --mission-request "Search aerial RGB imagery for vehicles relevant to incident response" \
  --labels-csv logs/benchmark_samples/dronevehicle_rgb_local_500/labels.csv \
  --semantic-vision local \
  --full-frame-semantic misses \
  --max-saved-candidates 500
```

## Results

| Metric | Result |
|---|---:|
| Images processed | 500 |
| Positive images | 250 |
| Negative images | 250 |
| Local detections | 500 |
| Semantic errors | 0 |

Confirmed-match metrics:

| Metric | Result |
|---|---:|
| Precision | 0.6158 |
| Recall | 1.0000 |
| F1 | 0.7622 |

Analyst-capture metrics:

| Metric | Result |
|---|---:|
| Capture precision | 0.5000 |
| Capture recall | 1.0000 |
| Capture F1 | 0.6667 |

Stage health:

| Stage | Status |
|---|---|
| Mission command | ok |
| Vision plan | ok |
| Contextual search plan | ok |
| Evidence collection | ok |
| Vision benchmark | ok |

## Interpretation

The mission pipeline ran successfully, and the vehicle-specific proposal layer moved the RGB benchmark from zero detections to full capture recall on this subset.

This is an important improvement. Aegis now preserves RGB vehicle evidence for review instead of silently missing every positive image.

Proposal reasons:

- rectangle-like aerial object: 383
- full-frame fallback: 71
- small high-contrast object: 46

Remaining weakness:

RGB capture precision is still only 50.00%, because the fallback policy intentionally keeps uncertain frames reviewable. The next improvement should reduce false positives in the review queue while keeping recall high.
