# DroneVehicle Benchmark Analysis

Dataset:

```text
/Users/noah/Downloads/VisDrone-DroneVehicle
```

## Structure

The dataset has `train`, `val`, and `test` splits. Each split contains:

- RGB images: `<split>/<split>img`
- Infrared images: `<split>/<split>imgr`
- RGB annotations: `<split>/<split>label`
- Infrared annotations: `<split>/<split>labelr`

Annotations are Pascal/VOC-style XML files. Vehicle objects use `<object><name>...</name>` and an oriented polygon with four points. Aegis ignores the polygon geometry for benchmark label generation and only uses the object class names.

## Counts

| Split | RGB images | IR images | RGB/IR pairs | RGB annotation files | IR annotation files |
|---|---:|---:|---:|---:|---:|
| test | 8,980 | 8,980 | 8,980 | 8,980 | 8,980 |
| train | 17,990 | 17,990 | 17,990 | 17,990 | 17,990 |
| val | 1,469 | 1,469 | 1,469 | 1,469 | 1,469 |

| Metric | Value |
|---|---:|
| Total RGB images | 28,439 |
| Total IR images | 28,439 |
| RGB/IR pairs | 28,439 |
| Total annotations | 953,164 |
| Images with annotations | 56,040 |
| Images without annotations | 838 |
| Positive images | 56,040 |
| Negative images | 838 |

## Class Distribution

| Class | Annotations |
|---|---:|
| car | 817,926 |
| truck | 48,086 |
| bus | 31,924 |
| freight car | 30,583 |
| van | 24,643 |
| * | 2 |

## Precision And Recall

Precision can be measured directly because the dataset contains negative images.

Because the dataset includes negative image cases, RGB and infrared runs can report both capture recall and capture precision directly.

## Recommended Strategy

- Use RGB and infrared labels as separate recall benchmarks.
- Run local evaluation first; reserve API review for 100-250 selected images.
- Keep RGB and infrared results separate because visible-light and thermal-like imagery fail differently.
- Use negative images in this dataset to measure capture precision directly.
