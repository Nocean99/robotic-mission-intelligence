# SARD People Benchmark Results

Milestone summary:

Aegis was evaluated on 5,712 annotated search-and-rescue images, then tested with two smaller OpenAI API-review strategies. The smarter review-priority sample improved analyst-capture precision from 70.31% to 90.97% while keeping capture recall near 90%.

This report compares three Aegis runs on the search-and-rescue people dataset:

- a full local run across the complete dataset
- a 100-image OpenAI semantic-vision sample
- a 200-image OpenAI review-priority sample

The goal was to validate a practical operating pattern: use the local layer for broad, low-cost triage, then use the API layer on a smaller set where semantic judgment matters most.

## Dataset

The imported YOLO dataset contains 5,712 images:

- 4,885 images with at least one person annotation
- 827 images without a person annotation

The Aegis labels file is:

```text
datasets/benchmarks/people/sard_labels.csv
```

## Full Local Run

Report:

```text
logs/mission_evaluations/20260605T180730Z/mission_evaluation_report.html
```

Configuration:

- images processed: 5,712
- scorer: `local-semantic-placeholder-v1`
- API usage: none
- local detections: 4,074
- shortlist size: 100
- semantic errors: 0

Confirmed-match metrics:

| Metric | Result |
|---|---:|
| Precision | 0.8289 |
| Recall | 0.2280 |
| F1 | 0.3577 |
| Accuracy | 0.2995 |

Analyst-capture metrics:

| Metric | Result |
|---|---:|
| Capture precision | 0.8373 |
| Capture recall | 0.6983 |
| Capture F1 | 0.7615 |
| Capture accuracy | 0.6259 |

Interpretation:

The local layer is useful as a broad first pass. It preserved roughly 70% of true person images for analyst review while keeping capture precision above 83%. However, it is not strong enough to be the final semantic judge. Confirmed recall was only 22.8%, which means many true people were not confidently identified by the local layer.

This is acceptable for a cheap triage stage, but not for final mission confidence.

## 100-Image OpenAI Sample

Report:

```text
logs/mission_evaluations/20260605T181140Z/mission_evaluation_report.html
```

Configuration:

- images processed: 100
- sample balance: 50 positive, 50 negative
- scorer: `gpt-4o`
- full-frame semantic mode: `misses`
- local detections: 64
- shortlist size: 65
- semantic/API errors: 2

Confirmed-match metrics:

| Metric | Result |
|---|---:|
| Precision | 1.0000 |
| Recall | 0.8000 |
| F1 | 0.8889 |
| Accuracy | 0.9000 |

Analyst-capture metrics:

| Metric | Result |
|---|---:|
| Capture precision | 0.7031 |
| Capture recall | 0.9000 |
| Capture F1 | 0.7895 |
| Capture accuracy | 0.7600 |

Interpretation:

The API semantic layer performed much better as a mission-relevance judge. On the balanced sample, every confirmed positive was correct, and the system preserved 90% of true person images for review. The tradeoff was a larger review queue: 19 negative images were still captured for analyst review.

That is the right failure mode for search-and-rescue style missions. It is better to keep uncertain evidence than to silently drop a possible person.

## Comparison

| Run | Scope | Scorer | Confirmed F1 | Capture Recall | Capture Precision |
|---|---:|---|---:|---:|---:|
| Full local | 5,712 images | local | 0.3577 | 0.6983 | 0.8373 |
| API sample | 100 images | OpenAI | 0.8889 | 0.9000 | 0.7031 |

The local layer is cost-effective and useful for reducing the search space. The API layer is much stronger at semantic judgment and should be used for high-priority, uncertain, or sampled candidates.

## 200-Image API Review Sample

Report:

```text
logs/mission_evaluations/20260605T184354Z/mission_evaluation_report.html
```

Sample:

```text
logs/benchmark_samples/sard_api_review_sample_200
```

Configuration:

- images processed: 200
- scorer: `gpt-4o`
- full-frame semantic mode: `misses`
- local detections: 134
- shortlist size: 149
- semantic/API errors: 0

The sample was selected from four buckets:

| Selection bucket | Count |
|---|---:|
| Top review priority | 50 |
| High uncertainty | 50 |
| Local misses or rejects | 50 |
| Balanced benchmark sample | 50 |

Confirmed-match metrics:

| Metric | Result |
|---|---:|
| Precision | 1.0000 |
| Recall | 0.7329 |
| F1 | 0.8458 |
| Accuracy | 0.8050 |

Analyst-capture metrics:

| Metric | Result |
|---|---:|
| Capture precision | 0.9097 |
| Capture recall | 0.8973 |
| Capture F1 | 0.9034 |
| Capture accuracy | 0.8600 |

Interpretation:

This was a harder sample than the first API run because it intentionally included uncertain cases and local misses. Even with that harder mix, the system preserved almost 90% of true person images for analyst review and sharply reduced review noise. Capture precision improved from 70.31% on the first API sample to 90.97% on the review-priority sample.

This is the strongest current evidence for the two-stage strategy: the local layer should not try to be perfect. It should surface likely, uncertain, and suspicious evidence. The API layer should then make a more exact semantic judgment on that smaller set.

## API Sample Comparison

| Run | Images | Confirmed Precision | Confirmed Recall | Confirmed F1 | Capture Precision | Capture Recall | Capture F1 | API Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced API sample | 100 | 1.0000 | 0.8000 | 0.8889 | 0.7031 | 0.9000 | 0.7895 | 2 |
| Review-priority API sample | 200 | 1.0000 | 0.7329 | 0.8458 | 0.9097 | 0.8973 | 0.9034 | 0 |

The second API run had slightly lower confirmed recall because it was deliberately harder. That is acceptable. The more important operational result is that capture recall stayed essentially the same while capture precision and capture F1 improved substantially.

## Recommended Operating Pattern

Use Aegis in two stages:

```text
Full dataset
  -> local proposal and ranking pass
  -> shortlist / uncertain candidates / balanced sample
  -> API semantic review
  -> analyst queue
  -> mission report
```

This gives the system a practical balance:

- low cost on large datasets
- stronger semantic judgment where it matters
- preserved uncertain evidence
- measurable benchmark results

## Changes Made From These Results

Mission Memory was updated to ignore dataset filename artifacts such as Roboflow hashes and `gss####` image IDs. Those names are useful as file identifiers, but they are not meaningful operational failure patterns.

This prevents Aegis from reporting fake lessons such as a hash string or image ID as a recurring miss pattern. Mission Memory should focus on human-meaningful review reasons and dataset labels, not file naming artifacts.

The benchmark sampler now supports an API-review selection policy. Instead of sending the whole dataset to the API, Aegis can create a smaller review set from:

- highest review priority
- high uncertainty
- local misses or rejects
- a balanced benchmark sample

Analyst review now also supports reason tags:

- `person visible`
- `too small`
- `vegetation`
- `shadow`
- `debris`
- `false alarm`

These tags make review decisions easier to analyze later and give Mission Memory better raw material than free text alone.

## Next Improvements

1. Improve the local proposal layer for small distant people.

2. Run more category-specific API samples for vehicles, boats, debris, smoke, fire, and structure damage.

3. Use analyst reason tags as first-class Mission Memory signals.

4. Track cost, runtime, and API error rate in benchmark comparisons.

5. Add a recurring benchmark command that compares the latest run against the previous best result.
