from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.dronevehicle_benchmark_analysis import analyze_dronevehicle_benchmark
from autonomy.dronevehicle_benchmark_analysis import normalize_vehicle_class
from autonomy.dronevehicle_benchmark_analysis import parse_dronevehicle_annotation


def write_xml(path: Path, names: list[str]) -> None:
    objects = "\n".join(
        f"""
  <object>
    <name>{name}</name>
    <polygon>
      <x1>1</x1><y1>2</y1><x2>3</x2><y2>4</y2>
      <x3>5</x3><y3>6</y3><x4>7</x4><y4>8</y4>
    </polygon>
  </object>"""
        for name in names
    )
    path.write_text(f"<annotation>{objects}\n</annotation>\n", encoding="utf-8")


def make_dronevehicle_fixture(root: Path, *, include_negative: bool = True) -> Path:
    dataset = root / "DroneVehicle"
    for split in ("train", "val", "test"):
        for folder in (f"{split}img", f"{split}imgr", f"{split}label", f"{split}labelr"):
            (dataset / split / folder).mkdir(parents=True)
    (dataset / "train" / "trainimg" / "0001.jpg").write_bytes(b"rgb")
    (dataset / "train" / "trainimgr" / "0001.jpg").write_bytes(b"ir")
    write_xml(dataset / "train" / "trainlabel" / "0001.xml", ["car", "feright car"])
    write_xml(dataset / "train" / "trainlabelr" / "0001.xml", ["truck"])

    if include_negative:
        (dataset / "val" / "valimg" / "0002.jpg").write_bytes(b"rgb")
        (dataset / "val" / "valimgr" / "0002.jpg").write_bytes(b"ir")
        write_xml(dataset / "val" / "vallabel" / "0002.xml", [])
        write_xml(dataset / "val" / "vallabelr" / "0002.xml", ["tree"])
    return dataset


def test_analysis_counts_rgb_ir_pairs_classes_and_negatives() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        dataset = make_dronevehicle_fixture(root, include_negative=True)
        stats_path = root / "stats.json"
        doc_path = root / "analysis.md"

        stats = analyze_dronevehicle_benchmark(dataset_dir=dataset, stats_json=stats_path, analysis_doc=doc_path)

        assert stats["total_rgb_images"] == 2
        assert stats["total_ir_images"] == 2
        assert stats["total_annotations"] == 4
        assert stats["class_distribution"]["car"] == 1
        assert stats["class_distribution"]["freight car"] == 1
        assert stats["class_distribution"]["truck"] == 1
        assert stats["positive_images"] == 2
        assert stats["negative_images"] == 2
        assert stats["precision_can_be_measured_directly"] is True
        assert stats["recall_focused_benchmark"] is False
        assert stats["rgb_ir_pair_counts"]["train"]["paired_images"] == 1
        assert stats_path.exists()
        assert doc_path.exists()
        assert "_label_rows" not in json.loads(stats_path.read_text(encoding="utf-8"))


def test_analysis_flags_all_positive_dataset_as_recall_only() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        dataset = make_dronevehicle_fixture(root, include_negative=False)
        stats = analyze_dronevehicle_benchmark(dataset_dir=dataset, stats_json=root / "stats.json", analysis_doc=root / "analysis.md")
        assert stats["negative_images"] == 0
        assert stats["precision_can_be_measured_directly"] is False
        assert stats["recall_focused_benchmark"] is True


def test_obb_polygon_annotations_do_not_break_parsing() -> None:
    with TemporaryDirectory() as tmp:
        annotation = Path(tmp) / "sample.xml"
        write_xml(annotation, ["van", "bus"])
        parsed = parse_dronevehicle_annotation(annotation)
        assert parsed["annotation_count"] == 2
        assert parsed["vehicle_annotation_count"] == 2


def test_class_mapping_normalizes_vehicle_names() -> None:
    assert normalize_vehicle_class("feright car") == "freight car"
    assert normalize_vehicle_class("small-vehicle") == "small vehicle"
    assert normalize_vehicle_class("large_vehicle") == "large vehicle"


if __name__ == "__main__":
    tests = [
        test_analysis_counts_rgb_ir_pairs_classes_and_negatives,
        test_analysis_flags_all_positive_dataset_as_recall_only,
        test_obb_polygon_annotations_do_not_break_parsing,
        test_class_mapping_normalizes_vehicle_names,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
