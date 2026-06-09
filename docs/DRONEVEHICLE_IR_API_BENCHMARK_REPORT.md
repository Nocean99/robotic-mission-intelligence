# DroneVehicle IR API Review Benchmark

Status: completed.

## Scope

This benchmark is intentionally limited to a 100-image review-priority sample. It does not run OpenAI/API review on the full DroneVehicle dataset.

Sample:

```text
logs/benchmark_samples/dronevehicle_ir_api_review_sample_100
```

Sample composition:

| Metric | Result |
|---|---:|
| Images | 100 |
| Positives | 55 |
| Negatives | 45 |

Selection policy:

| Selection reason | Count |
|---|---:|
| top_review_priority | 20 |
| high_uncertainty | 20 |
| local_false_positive | 20 |
| balanced_benchmark_sample | 44 |

There were no local misses or local rejects in the IR local baseline because the vehicle proposal layer captured every positive case.

## API Run Status

Valid report:

```text
logs/mission_evaluations/dronevehicle_ir_api_review_sample_100_auto/20260608T193702Z/mission_evaluation_report.html
```

The completed run used `--openai-detail auto` after a 10-image smoke test confirmed the IR API path was working.

## API Results

| Metric | Result |
|---|---:|
| Images processed | 100 |
| Positives | 55 |
| Negatives | 45 |
| Detections | 100 |
| API / semantic errors | 1 |
| Shortlist size | 90 |

Confirmed-match metrics:

| Metric | Result |
|---|---:|
| Precision | 77.8% |
| Recall | 76.4% |
| F1 | 77.1% |

Analyst-capture metrics:

| Metric | Result |
|---|---:|
| Capture precision | 61.1% |
| Capture recall | 100.0% |
| Capture F1 | 75.9% |

## Valid Local Comparison

Compared with the local-only IR subset baseline:

| IR Benchmark | Capture Precision | Capture Recall | Capture F1 |
|---|---:|---:|---:|
| Local only | 89.4% | 100.0% | 94.4% |
| API review sample | 61.1% | 100.0% | 75.9% |

## Safe Rerun Command

```bash
./scripts/run_mission_evaluation.sh \
  logs/benchmark_samples/dronevehicle_ir_api_review_sample_100/images \
  --mission-request "Search these infrared aerial images for vehicles including cars, trucks, vans, buses, and freight vehicles." \
  --labels-csv logs/benchmark_samples/dronevehicle_ir_api_review_sample_100/labels.csv \
  --semantic-vision openai \
  --openai-detail high \
  --proposal-mode vehicle \
  --full-frame-semantic misses \
  --max-saved-candidates 100 \
  --output-dir logs/mission_evaluations/dronevehicle_ir_api_review_sample_100
```

## Interpretation

The IR API benchmark preserved recall, but it did not improve the analyst queue. Local hot-blob triage remains the better IR vehicle strategy for now: it had higher capture precision and higher capture F1.

The likely issue is that the semantic API treated many ambiguous thermal negatives as `NEEDS_REVIEW`. API thermal review may need a stricter prompt or a stricter `NEEDS_REVIEW` threshold before it beats local triage.
