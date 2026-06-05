# Benchmark Dataset Layout

This folder is reserved for small, curated mission-evaluation datasets.

Each mission category uses the same three-way split:

- `positives`: clear target examples
- `near_misses`: ambiguous or partial evidence that should usually stay in the review queue
- `hard_negatives`: confusing non-targets that should be down-ranked

Configured categories:

- `people`
- `vehicles`
- `boats`
- `debris`
- `markers`
- `smoke`
- `fire`
- `structure_damage`
- `animals`

Examples of good hard negatives include rocks, logs, shadows, waves, shoreline clutter, fog, construction sites, reflections, and ordinary objects that resemble the mission target.

Keep this folder small. Do not commit private, sensitive, or licensed imagery without permission. For public portfolio demos, use open-license data or synthetic test fixtures.
