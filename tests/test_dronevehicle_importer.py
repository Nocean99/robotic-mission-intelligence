from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonomy.dronevehicle_benchmark_analysis import import_dronevehicle_vehicle_benchmark


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


def make_dronevehicle_fixture(root: Path) -> Path:
    dataset = root / "DroneVehicle"
    for split in ("train", "val", "test"):
        for folder in (f"{split}img", f"{split}imgr", f"{split}label", f"{split}labelr"):
            (dataset / split / folder).mkdir(parents=True)
    (dataset / "train" / "trainimg" / "0001.jpg").write_bytes(b"rgb")
    (dataset / "train" / "trainimgr" / "0001.jpg").write_bytes(b"ir")
    write_xml(dataset / "train" / "trainlabel" / "0001.xml", ["car"])
    write_xml(dataset / "train" / "trainlabelr" / "0001.xml", ["truck"])
    (dataset / "val" / "valimg" / "0002.jpg").write_bytes(b"rgb")
    (dataset / "val" / "valimgr" / "0002.jpg").write_bytes(b"ir")
    write_xml(dataset / "val" / "vallabel" / "0002.xml", [])
    write_xml(dataset / "val" / "vallabelr" / "0002.xml", ["tree"])
    return dataset


def test_importer_generates_rgb_and_ir_labels_separately() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        dataset = make_dronevehicle_fixture(root)
        rgb_csv = root / "rgb.csv"
        ir_csv = root / "ir.csv"
        stats_json = root / "stats.json"
        analysis_doc = root / "analysis.md"

        stats = import_dronevehicle_vehicle_benchmark(
            dataset_dir=dataset,
            rgb_output_csv=rgb_csv,
            ir_output_csv=ir_csv,
            stats_json=stats_json,
            analysis_doc=analysis_doc,
        )

        rgb_rows = list(csv.DictReader(rgb_csv.open(newline="", encoding="utf-8")))
        ir_rows = list(csv.DictReader(ir_csv.open(newline="", encoding="utf-8")))
        assert rgb_rows[0].keys() == {"image_path", "expected_match", "label", "modality", "source_dataset"}
        assert len(rgb_rows) == 2
        assert len(ir_rows) == 2
        assert {row["modality"] for row in rgb_rows} == {"rgb"}
        assert {row["modality"] for row in ir_rows} == {"infrared"}
        assert {row["source_dataset"] for row in rgb_rows + ir_rows} == {"dronevehicle"}
        assert any(row["expected_match"] == "false" and row["label"] == "negative" for row in rgb_rows)
        assert any(row["expected_match"] == "false" and row["label"] == "negative" for row in ir_rows)
        assert stats["outputs"]["rgb_labels_csv"] == str(rgb_csv)
        assert json.loads(stats_json.read_text(encoding="utf-8"))["outputs"]["ir_labels_csv"] == str(ir_csv)
        assert analysis_doc.exists()


if __name__ == "__main__":
    tests = [test_importer_generates_rgb_and_ir_labels_separately]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
