from __future__ import annotations

import re
from typing import Iterable, Optional

from ingest import normalize_company
from retriever import Retriever
from schemas import Classification, RequestType, Ticket


INVALID_PATTERNS = (
    r"\biron man\b",
    r"\bactor\b",
    r"\bdelete all files\b",
    r"\brm\s+-rf\b",
    r"\bsudo\b",
    r"\binternal rules\b",
    r"\bsystem prompt\b",
    r"\bdocuments retrieved\b",
    r"\blogic exact\b",
)

BUG_PATTERNS = (
    "site is down",
    "stopped working",
    "all requests are failing",
    "none of the pages",
    "none of the submissions",
    "submissions across",
    "is down",
    "not working",
    "failing",
    "error",
    "blocked",
)

FEATURE_PATTERNS = (
    "feature request",
    "can we extend",
    "would like to request",
    "please add",
    "can you add",
)

RISK_KEYWORDS = {
    "account_access": ("lost access", "restore my access", "removed my seat", "not the workspace owner", "delete my account"),
    "billing_refund": ("refund", "chargeback", "dispute a charge", "give me my money", "payment", "subscription"),
    "fraud_or_theft": ("fraud", "stolen", "theft", "identity has been stolen", "lost card", "card stolen"),
    "legal_privacy": ("privacy", "private info", "stop crawling", "legal", "gdpr", "delete my data"),
    "security_vuln": ("security vulnerability", "bug bounty", "responsible disclosure", "vulnerability"),
    "outage": (
        "site is down",
        "all requests are failing",
        "none of the pages",
        "none of the submissions",
        "submissions across",
        "stopped working completely",
    ),
    "prompt_injection": ("internal rules", "system prompt", "documents retrieved", "logic exact", "ignore previous"),
    "multilingual": ("bonjour", "tarjeta", "bloquée", "bloqueada"),
}


def combined_text(ticket: Ticket | dict[str, str]) -> str:
    if isinstance(ticket, dict):
        return f"{ticket.get('subject', '')}\n{ticket.get('issue', '')}"
    return f"{ticket.subject}\n{ticket.issue}"


def classify_request_type(text: str) -> RequestType:
    lowered = text.lower()
    compact = re.sub(r"[^a-z0-9]+", " ", lowered).strip()
    if compact in {"thanks", "thank you", "thank you for helping me", "hello", "hi", "hi there"}:
        return RequestType.invalid
    if any(re.search(pattern, lowered) for pattern in INVALID_PATTERNS):
        return RequestType.invalid
    if any(pattern in lowered for pattern in FEATURE_PATTERNS):
        return RequestType.feature_request
    if any(pattern in lowered for pattern in BUG_PATTERNS):
        return RequestType.bug
    return RequestType.product_issue


def detect_risk_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags: list[str] = []
    for tag, keywords in RISK_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            tags.append(tag)
    return tags


def classify_ticket(ticket: Ticket, retriever: Optional[Retriever] = None) -> Classification:
    text = combined_text(ticket)
    company = normalize_company(ticket.company)
    cross_domain = False
    low_confidence = False
    if not company and retriever is not None:
        inferred, gap = retriever.infer_company(text)
        if inferred and gap >= 0.08:
            company = inferred
        else:
            cross_domain = True
            low_confidence = True

    request_type = classify_request_type(text)
    tags = detect_risk_tags(text)
    if request_type == RequestType.invalid and "prompt_injection" in tags and company:
        # A prompt injection attached to an otherwise supportable ticket should not
        # erase the support intent; the router/responder will ignore the injection.
        request_type = RequestType.product_issue

    return Classification(
        company=company,
        request_type=request_type,
        risk_tags=tags,
        cross_domain=cross_domain,
        low_confidence=low_confidence,
    )
