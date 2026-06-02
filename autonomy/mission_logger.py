from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from autonomy.types import MissionLogRow


class MissionLogger:
    def __init__(self, log_dir: str = "logs") -> None:
        Path(log_dir).mkdir(exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.path = Path(log_dir) / f"mission_{timestamp}.csv"
        self._file = self.path.open("w", newline="", encoding="utf-8")
        self._writer: csv.DictWriter | None = None

    def write(self, row: MissionLogRow) -> None:
        data = row.as_csv_row()
        if self._writer is None:
            self._writer = csv.DictWriter(self._file, fieldnames=list(data.keys()))
            self._writer.writeheader()
        self._writer.writerow(data)
        self._file.flush()

    def close(self) -> None:
        self._file.close()

