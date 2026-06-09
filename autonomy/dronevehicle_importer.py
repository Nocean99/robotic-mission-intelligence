from __future__ import annotations

import argparse
import json

from autonomy.dronevehicle_benchmark_analysis import DEFAULT_ANALYSIS_DOC
from autonomy.dronevehicle_benchmark_analysis import DEFAULT_IR_LABELS
from autonomy.dronevehicle_benchmark_analysis import DEFAULT_RGB_LABELS
from autonomy.dronevehicle_benchmark_analysis import DEFAULT_STATS_JSON
from autonomy.dronevehicle_benchmark_analysis import import_dronevehicle_vehicle_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description="Import DroneVehicle RGB/infrared labels into Aegis benchmark CSVs.")
    parser.add_argument("dataset_dir", help="DroneVehicle dataset folder")
    parser.add_argument("--rgb-output-csv", default=DEFAULT_RGB_LABELS)
    parser.add_argument("--ir-output-csv", default=DEFAULT_IR_LABELS)
    parser.add_argument("--stats-json", default=DEFAULT_STATS_JSON)
    parser.add_argument("--analysis-doc", default=DEFAULT_ANALYSIS_DOC)
    args = parser.parse_args()
    stats = import_dronevehicle_vehicle_benchmark(
        dataset_dir=args.dataset_dir,
        rgb_output_csv=args.rgb_output_csv,
        ir_output_csv=args.ir_output_csv,
        stats_json=args.stats_json,
        analysis_doc=args.analysis_doc,
    )
    print(f"DroneVehicle RGB labels saved: {args.rgb_output_csv}")
    print(f"DroneVehicle IR labels saved: {args.ir_output_csv}")
    print(f"DroneVehicle stats saved: {args.stats_json}")
    print(f"DroneVehicle analysis saved: {args.analysis_doc}")
    print(
        json.dumps(
            {
                "total_rgb_images": stats["total_rgb_images"],
                "total_ir_images": stats["total_ir_images"],
                "total_annotations": stats["total_annotations"],
                "positive_images": stats["positive_images"],
                "negative_images": stats["negative_images"],
                "precision_can_be_measured_directly": stats["precision_can_be_measured_directly"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
