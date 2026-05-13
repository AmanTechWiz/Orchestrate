from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field, field_validator
except Exception:  # pragma: no cover - fallback keeps the CLI usable offline.
    class BaseModel:  # type: ignore[no-redef]
        def __init__(self, **kwargs: Any) -> None:
            annotations = getattr(self, "__annotations__", {})
            for key, default in self.__class__.__dict__.items():
                if key.startswith("_") or callable(default):
                    continue
                if key not in annotations:
                    continue
                setattr(self, key, kwargs.pop(key, default))
            for key in annotations:
                if not hasattr(self, key):
                    setattr(self, key, kwargs.pop(key, None))
            for key, value in kwargs.items():
                setattr(self, key, value)

        def model_dump(self) -> Dict[str, Any]:
            return dict(self.__dict__)

    def Field(default: Any = None, **kwargs: Any) -> Any:
        if "default_factory" in kwargs:
            return kwargs["default_factory"]()
        return default

    def field_validator(*_: Any, **__: Any):  # type: ignore[no-untyped-def]
        def decorator(fn):
            return fn

        return decorator


class Status(str, Enum):
    replied = "replied"
    escalated = "escalated"


class RequestType(str, Enum):
    product_issue = "product_issue"
    feature_request = "feature_request"
    bug = "bug"
    invalid = "invalid"


CANONICAL_COMPANIES = ("hackerrank", "claude", "visa")

PRODUCT_AREAS: Dict[str, List[str]] = {
    "hackerrank": [
        "chakra",
        "community",
        "engage",
        "general_help",
        "integrations",
        "interviews",
        "library",
        "screen",
        "settings",
        "skillup",
        "uncategorized",
    ],
    "claude": [
        "amazon_bedrock",
        "account_management",
        "conversation_management",
        "features_and_capabilities",
        "get_started_with_claude",
        "personalization_and_settings",
        "troubleshooting",
        "usage_and_limits",
        "api_faq",
        "api_prompt_design",
        "api_usage_and_best_practices",
        "api_pricing_and_billing",
        "api_troubleshooting",
        "api_console",
        "claude_code",
        "claude_desktop",
        "claude_mobile_apps",
        "claude_for_education",
        "claude_for_government",
        "claude_for_nonprofits",
        "claude_in_chrome",
        "connectors",
        "identity_management",
        "privacy",
        "privacy_and_legal",
        "pro_and_max_plans",
        "safeguards",
        "team_and_enterprise_plans",
    ],
    "visa": [
        "general_support",
        "consumer_support",
        "travel_support",
        "travellers_cheques",
        "merchant_support",
        "small_business",
        "checkout_fees",
        "visa_rules",
        "data_security",
        "dispute_resolution",
        "fraud_prevention",
        "regulations_fees",
    ],
}

OUTPUT_COLUMNS = [
    "issue",
    "subject",
    "company",
    "response",
    "product_area",
    "status",
    "request_type",
    "justification",
]

ESCALATION_RESPONSE = "Escalate to a human"


class RetrievedChunk(BaseModel):
    text: str
    source_path: str
    company: str
    product_area: str
    heading_path: str = ""
    score: float = 0.0
    bm25_score: float = 0.0
    vector_score: float = 0.0


class Ticket(BaseModel):
    issue: str = ""
    subject: str = ""
    company: str = ""


class Classification(BaseModel):
    company: str = ""
    request_type: RequestType = RequestType.product_issue
    risk_tags: List[str] = Field(default_factory=list)  # type: ignore[arg-type]
    cross_domain: bool = False
    low_confidence: bool = False


class Decision(BaseModel):
    status: Status
    reason: str
    low_evidence: bool = False


class OutputRow(BaseModel):
    issue: str
    subject: str
    company: str
    response: str
    product_area: str
    status: Status
    request_type: RequestType
    justification: str

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value: Any) -> str:
        return str(value).strip().lower()

    @field_validator("request_type", mode="before")
    @classmethod
    def normalize_request_type(cls, value: Any) -> str:
        return str(value).strip().lower()


def model_to_dict(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    return dict(model.__dict__)
