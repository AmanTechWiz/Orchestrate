from __future__ import annotations

import difflib
from typing import Dict, List

from schemas import (
    ESCALATION_RESPONSE,
    OUTPUT_COLUMNS,
    PRODUCT_AREAS,
    OutputRow,
    RequestType,
    Status,
    model_to_dict,
)
from utils.text import strip_csv_hostile


def normalize_product_area(company: str, product_area: str, fallback: str = "") -> str:
    company_key = company.strip().lower()
    if company_key in {"none", "null", "nan"}:
        company_key = ""
    allowed = PRODUCT_AREAS.get(company_key, [])
    product_area = strip_csv_hostile(product_area).lower()
    if not company_key:
        all_areas = {area for areas in PRODUCT_AREAS.values() for area in areas}
        return product_area if product_area in all_areas else ""
    if not product_area:
        return fallback if fallback in allowed else ""
    if product_area in allowed:
        return product_area
    match = difflib.get_close_matches(product_area, allowed, n=1, cutoff=0.55)
    if match:
        return match[0]
    return fallback if fallback in allowed else ""


def validate_row(row: Dict[str, str], fallback_area: str = "") -> Dict[str, str]:
    status = row.get("status", "").strip().lower()
    request_type = row.get("request_type", "").strip().lower()
    company = row.get("company", "").strip()
    company_key = company.lower()

    if status not in {item.value for item in Status}:
        status = Status.escalated.value
    if request_type not in {item.value for item in RequestType}:
        request_type = RequestType.product_issue.value

    product_area = normalize_product_area(company_key, row.get("product_area", ""), fallback_area)
    response = (row.get("response", "") or "").strip()
    justification = strip_csv_hostile(row.get("justification", ""))

    if status == Status.escalated.value:
        response = ESCALATION_RESPONSE
    elif not response:
        response = "I am sorry, this is out of scope from my capabilities"
        request_type = RequestType.invalid.value

    clean = {
        "issue": row.get("issue", ""),
        "subject": row.get("subject", ""),
        "company": company,
        "response": response.strip(),
        "product_area": product_area,
        "status": status,
        "request_type": request_type,
        "justification": justification[:300],
    }
    try:
        model = OutputRow(**clean)
        dumped = model_to_dict(model)
        dumped["status"] = str(dumped["status"].value if hasattr(dumped["status"], "value") else dumped["status"])
        dumped["request_type"] = str(
            dumped["request_type"].value if hasattr(dumped["request_type"], "value") else dumped["request_type"]
        )
        return {column: str(dumped.get(column, "")) for column in OUTPUT_COLUMNS}
    except Exception:
        return {column: str(clean.get(column, "")) for column in OUTPUT_COLUMNS}


def best_area_from_chunks(chunks: List[object]) -> str:
    if not chunks:
        return ""
    first = chunks[0]
    return str(getattr(first, "product_area", "") or "")
