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

## YOLO Person Import

YOLOv8 person datasets can be converted into Aegis labels with:

```bash
./scripts/import_yolo_person_benchmark.sh "/path/to/yolo_dataset"
```

By default this writes:

```text
datasets/benchmarks/people/sard_labels.csv
```

Output columns:

```csv
image_path,expected_match,label
```

Rules:

- at least one person annotation: `expected_match=true`, `label=positive`
- no person annotation, empty label file, or missing label file: `expected_match=false`, `label=negative`

The default YOLO person class id is `0`. Use `--person-class-id` for datasets with a different class map.

## YOLO OBB Vehicle Import

YOLO OBB vehicle datasets can be converted into Aegis labels with:

```bash
./scripts/import_yolo_obb_vehicle_benchmark.sh "/path/to/yolo_obb_vehicle_dataset"
```

By default this writes:

```text
datasets/benchmarks/vehicles/vehicle_labels.csv
datasets/benchmarks/vehicles/vehicle_labels_stats.json
```

The importer reads `data.yaml` first and treats classes with vehicle names as positive target classes. For the DroneVehicle Dataset YOLOv11 OBB export, the class list is:

```text
0: small-vehicle
1: large-vehicle
```

OBB coordinates and rotation are ignored for benchmark label generation. The benchmark label only asks whether the image contains at least one vehicle annotation.

## DroneVehicle RGB/Infrared Import

The DroneVehicle RGB/infrared dataset can be analyzed with:

```bash
./scripts/analyze_dronevehicle_benchmark.sh "/path/to/VisDrone-DroneVehicle"
```

It can be converted into separate Aegis RGB and infrared labels with:

```bash
./scripts/import_dronevehicle_vehicle_benchmark.sh "/path/to/VisDrone-DroneVehicle"
```

By default this writes:

```text
datasets/benchmarks/vehicles/dronevehicle_rgb_labels.csv
datasets/benchmarks/vehicles/dronevehicle_ir_labels.csv
datasets/benchmarks/vehicles/dronevehicle_stats.json
docs/DRONEVEHICLE_BENCHMARK_ANALYSIS.md
```

Output columns:

```csv
image_path,expected_match,label,modality,source_dataset
```

The importer supports Pascal/VOC-style XML annotations with oriented polygon points. For benchmark labels, polygon geometry and rotation are ignored; any target vehicle annotation makes the image a positive match.

Target vehicle classes:

- `car`
- `truck`
- `bus`
- `van`
- `freight car`
- `small-vehicle`
- `large-vehicle`

## Full Local / Small API Workflow

Run the full dataset with the local scorer first:

```bash
./scripts/run_mission_evaluation.sh \
  "/path/to/yolo_dataset/train/images" \
  "/path/to/yolo_dataset/valid/images" \
  "/path/to/yolo_dataset/test/images" \
  --mission-request "Search aerial imagery for people who may need rescue" \
  --labels-csv datasets/benchmarks/people/sard_labels.csv \
  --semantic-vision local \
  --save-all-debug-images
```

Create a balanced 100-image sample for API review:

```bash
./scripts/create_benchmark_sample.sh "/path/to/yolo_dataset" \
  --labels-csv datasets/benchmarks/people/sard_labels.csv \
  --output-dir logs/benchmark_samples/sard_api_sample_100 \
  --max-images 100
```

Then run the API scorer on that sample:

```bash
./scripts/run_mission_evaluation.sh \
  logs/benchmark_samples/sard_api_sample_100/images \
  --mission-request "Search aerial imagery for people who may need rescue" \
  --labels-csv logs/benchmark_samples/sard_api_sample_100/labels.csv \
  --semantic-vision openai \
  --openai-detail high \
  --full-frame-semantic misses
```

After a full local run, create a smaller API-review sample from the most useful cases:

```bash
./scripts/create_benchmark_sample.sh "/path/to/yolo_dataset" \
  --labels-csv datasets/benchmarks/people/sard_labels.csv \
  --from-local-report logs/mission_evaluations/YYYYMMDDTHHMMSSZ/mission_evaluation_report.json \
  --output-dir logs/benchmark_samples/sard_api_review_sample_200 \
  --max-images 200
```

This policy samples from:

- top review priority
- high uncertainty
- local misses or rejects
- a balanced benchmark sample

Then run the API scorer only on that smaller sample:

```bash
./scripts/run_mission_evaluation.sh \
  logs/benchmark_samples/sard_api_review_sample_200/images \
  --mission-request "Search aerial imagery for people who may need rescue" \
  --labels-csv logs/benchmark_samples/sard_api_review_sample_200/labels.csv \
  --semantic-vision openai \
  --openai-detail high \
  --full-frame-semantic misses \
  --max-saved-candidates 200
```

## DroneVehicle Local RGB/IR Baselines

Create 500-image local subsets:

```bash
./scripts/create_benchmark_sample.sh "/path/to/VisDrone-DroneVehicle" \
  --labels-csv datasets/benchmarks/vehicles/dronevehicle_rgb_labels.csv \
  --output-dir logs/benchmark_samples/dronevehicle_rgb_local_500 \
  --max-images 500 \
  --seed 21

./scripts/create_benchmark_sample.sh "/path/to/VisDrone-DroneVehicle" \
  --labels-csv datasets/benchmarks/vehicles/dronevehicle_ir_labels.csv \
  --output-dir logs/benchmark_samples/dronevehicle_ir_local_500 \
  --max-images 500 \
  --seed 22
```

Run local-only RGB and IR evaluations:

```bash
./scripts/run_mission_evaluation.sh \
  logs/benchmark_samples/dronevehicle_rgb_local_500/images \
  --mission-request "Search aerial RGB imagery for vehicles relevant to incident response" \
  --labels-csv logs/benchmark_samples/dronevehicle_rgb_local_500/labels.csv \
  --semantic-vision local \
  --proposal-mode vehicle \
  --full-frame-semantic misses \
  --max-saved-candidates 500

./scripts/run_mission_evaluation.sh \
  logs/benchmark_samples/dronevehicle_ir_local_500/images \
  --mission-request "Search infrared aerial imagery for vehicles relevant to incident response" \
  --labels-csv logs/benchmark_samples/dronevehicle_ir_local_500/labels.csv \
  --semantic-vision local \
  --proposal-mode vehicle \
  --full-frame-semantic misses \
  --max-saved-candidates 500
```

The vehicle proposal mode is local-only. It uses RGB contour/objectness proposals, infrared hot-blob proposals, and a low-confidence full-frame fallback so uncertain vehicle evidence remains reviewable.

Do not run OpenAI/API review on the full DroneVehicle dataset. If API review is needed, create a 100-250 image sample first.
