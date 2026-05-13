from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterable, List

from schemas import OUTPUT_COLUMNS


def read_tickets(path: str | Path) -> List[Dict[str, str]]:
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: List[Dict[str, str]] = []
        for row in reader:
            normalized = {str(key).strip().lower(): (value or "") for key, value in row.items()}
            rows.append(
                {
                    "issue": normalized.get("issue", ""),
                    "subject": normalized.get("subject", ""),
                    "company": normalized.get("company", ""),
                }
            )
        return rows


def write_output(path: str | Path, rows: Iterable[Dict[str, str]]) -> None:
    csv_path = Path(path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in OUTPUT_COLUMNS})


def load_output(path: str | Path) -> List[Dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))
