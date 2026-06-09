# DroneVehicle RGB API Review Benchmark

Status: completed.

## Scope

This benchmark is intentionally limited to a 100-image review-priority sample. It does not run OpenAI/API review on the full DroneVehicle dataset.

Sample:

```text
logs/benchmark_samples/dronevehicle_rgb_api_review_sample_100
```

Sample composition:

| Metric | Result |
|---|---:|
| Images | 100 |
| Positives | 43 |
| Negatives | 57 |

Selection policy:

| Selection reason | Count |
|---|---:|
| top_review_priority | 20 |
| high_uncertainty | 20 |
| local_false_positive | 20 |
| balanced_benchmark_sample | 52 |

There were no local misses or local rejects in the RGB local baseline because the vehicle proposal layer captured every positive case.

## API Run Status

Valid report:

```text
logs/mission_evaluations/dronevehicle_rgb_api_review_sample_100/20260608T182608Z/mission_evaluation_report.html
```

The first API attempt produced an invalid report because the sample image symlinks were relative and unreadable from the benchmark folder. That run had 100 image-read errors and should not be used as an API benchmark.

The sampler was fixed to write absolute symlink targets, and the 100-image sample was recreated and verified as readable. The completed run processed all 100 images successfully.

## API Results

| Metric | Result |
|---|---:|
| Images processed | 100 |
| Positives | 43 |
| Negatives | 57 |
| Detections | 100 |
| API / semantic errors | 1 |
| Shortlist size | 59 |

Confirmed-match metrics:

| Metric | Result |
|---|---:|
| Precision | 94.6% |
| Recall | 81.4% |
| F1 | 87.5% |

Analyst-capture metrics:

| Metric | Result |
|---|---:|
| Capture precision | 73.2% |
| Capture recall | 95.3% |
| Capture F1 | 82.8% |

## Valid Local Comparison

Compared with the local-only RGB subset baseline:

| RGB Benchmark | Capture Precision | Capture Recall | Capture F1 |
|---|---:|---:|---:|
| Local only | 50.0% | 100.0% | 66.7% |
| API review sample | 73.2% | 95.3% | 82.8% |

## Safe Rerun Command

```bash
./scripts/run_mission_evaluation.sh \
  logs/benchmark_samples/dronevehicle_rgb_api_review_sample_100/images \
  --mission-request "Search these aerial RGB images for vehicles including cars, trucks, vans, buses, and freight vehicles." \
  --labels-csv logs/benchmark_samples/dronevehicle_rgb_api_review_sample_100/labels.csv \
  --semantic-vision openai \
  --openai-detail high \
  --proposal-mode vehicle \
  --full-frame-semantic misses \
  --max-saved-candidates 100 \
  --output-dir logs/mission_evaluations/dronevehicle_rgb_api_review_sample_100
```

## Interpretation

The RGB API review layer cleaned the analyst queue meaningfully. Capture precision improved from 50.0% to 73.2%, while capture recall stayed high at 95.3%.

This supports the intended Aegis design: the cheap local layer preserves likely evidence, and the semantic API layer reduces review noise without collapsing recall.
