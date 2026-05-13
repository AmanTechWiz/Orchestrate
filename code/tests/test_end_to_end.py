from __future__ import annotations

import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import run
from schemas import OUTPUT_COLUMNS


ROOT = Path(__file__).resolve().parents[2]


def test_sample_end_to_end(tmp_path: Path) -> None:
    output = tmp_path / "sample_output.csv"
    rows = run(ROOT / "support_tickets" / "sample_support_tickets.csv", output)
    expected_rows = list(csv.DictReader((ROOT / "support_tickets" / "sample_support_tickets.csv").open()))
    assert len(rows) == len(expected_rows)
    assert list(csv.DictReader(output.open()).fieldnames or []) == OUTPUT_COLUMNS

    status_matches = 0
    request_matches = 0
    product_matches = 0
    for actual, expected in zip(rows, expected_rows):
        status_matches += actual["status"].lower() == expected["Status"].lower()
        request_matches += actual["request_type"].lower() == expected["Request Type"].lower()
        product_matches += actual["product_area"].lower() == expected["Product Area"].lower()
        if actual["status"] == "replied":
            assert actual["response"].strip()

    assert status_matches == len(expected_rows)
    assert request_matches >= 9
    assert product_matches >= 8
