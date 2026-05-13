from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from schemas import PRODUCT_AREAS
from utils.text import normalize_text, slugify, tokenize


DATA_COMPANIES = ("hackerrank", "claude", "visa")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class ChunkRecord:
    chunk_id: str
    text: str
    source_path: str
    company: str
    product_area: str
    heading_path: str
    tokens: List[str]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def data_root() -> Path:
    return repo_root() / "data"


def cache_dir() -> Path:
    return Path(__file__).resolve().parent / ".cache"


def normalize_company(value: str) -> str:
    normalized = slugify(value)
    if normalized in {"none", "null", "nan"}:
        return ""
    if normalized == "hacker_rank":
        return "hackerrank"
    return normalized if normalized in DATA_COMPANIES else ""


def product_area_for_path(company: str, relative_path: Path, text: str = "") -> str:
    parts = [part for part in relative_path.parts if part != "index.md"]
    joined = "/".join(parts).lower()
    lowered = text.lower()

    if company == "hackerrank":
        first = parts[0] if parts else "uncategorized"
        if first == "hackerrank_community":
            return "community"
        if first == "general-help":
            return "general_help"
        return slugify(first) or "uncategorized"

    if company == "claude":
        if joined.startswith("amazon-bedrock"):
            return "amazon_bedrock"
        if joined.startswith("claude/account-management"):
            return "account_management"
        if joined.startswith("claude/conversation-management"):
            if any(term in lowered for term in ("private", "delete", "temporary", "incognito")):
                return "privacy"
            return "conversation_management"
        if joined.startswith("claude/features-and-capabilities"):
            return "features_and_capabilities"
        if joined.startswith("claude/get-started-with-claude"):
            return "get_started_with_claude"
        if joined.startswith("claude/personalization-and-settings"):
            return "personalization_and_settings"
        if joined.startswith("claude/troubleshooting"):
            return "troubleshooting"
        if joined.startswith("claude/usage-and-limits"):
            return "usage_and_limits"
        if joined.startswith("claude-api-and-console/api-faq"):
            return "api_faq"
        if joined.startswith("claude-api-and-console/api-prompt-design"):
            return "api_prompt_design"
        if joined.startswith("claude-api-and-console/claude-api-usage-and-best-practices"):
            return "api_usage_and_best_practices"
        if joined.startswith("claude-api-and-console/pricing-and-billing"):
            return "api_pricing_and_billing"
        if joined.startswith("claude-api-and-console/troubleshooting"):
            return "api_troubleshooting"
        if joined.startswith("claude-api-and-console"):
            return "api_console"
        if joined.startswith("claude-code"):
            return "claude_code"
        if joined.startswith("claude-desktop"):
            return "claude_desktop"
        if joined.startswith("claude-mobile-apps"):
            return "claude_mobile_apps"
        if joined.startswith("claude-for-education"):
            return "claude_for_education"
        if joined.startswith("claude-for-government"):
            return "claude_for_government"
        if joined.startswith("claude-for-nonprofits"):
            return "claude_for_nonprofits"
        if joined.startswith("claude-in-chrome"):
            return "claude_in_chrome"
        if joined.startswith("identity-management"):
            return "identity_management"
        if joined.startswith("privacy-and-legal"):
            return "privacy_and_legal"
        if joined.startswith("pro-and-max-plans"):
            return "pro_and_max_plans"
        if joined.startswith("team-and-enterprise-plans"):
            return "team_and_enterprise_plans"
        first = parts[0] if parts else "claude"
        return slugify(first)

    if company == "visa":
        if "travelers-cheques" in joined or "traveller" in lowered:
            return "travel_support"
        if "travel-support" in joined:
            return "travel_support"
        if "checkout-fees" in joined:
            return "checkout_fees"
        if "visa-rules" in joined:
            return "visa_rules"
        if "data-security" in joined:
            return "data_security"
        if "dispute-resolution" in joined:
            return "dispute_resolution"
        if "fraud-protection" in joined:
            return "fraud_prevention"
        if "regulations-fees" in joined:
            return "regulations_fees"
        if "merchant" in joined:
            return "merchant_support"
        if "small-business" in joined:
            return "small_business"
        if "consumer" in joined:
            return "consumer_support"
        return "general_support"

    return ""


def clean_markdown(text: str) -> str:
    text = re.sub(r"^---.*?---", "", text, flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return normalize_text(text)


def heading_sections(markdown: str) -> Iterable[tuple[str, str]]:
    headings = list(HEADING_RE.finditer(markdown))
    if not headings:
        yield "", markdown
        return
    for idx, match in enumerate(headings):
        start = match.start()
        end = headings[idx + 1].start() if idx + 1 < len(headings) else len(markdown)
        heading = match.group(2).strip()
        yield heading, markdown[start:end].strip()


def sliding_windows(words: Sequence[str], size: int = 620, overlap: int = 90) -> Iterable[str]:
    if len(words) <= size:
        yield " ".join(words)
        return
    step = max(size - overlap, 1)
    for start in range(0, len(words), step):
        window = words[start : start + size]
        if not window:
            continue
        yield " ".join(window)
        if start + size >= len(words):
            break


def build_chunks(root: Path | None = None) -> List[ChunkRecord]:
    root = root or data_root()
    chunks: List[ChunkRecord] = []
    for company in DATA_COMPANIES:
        company_root = root / company
        for path in sorted(company_root.rglob("*.md")):
            if path.name == "index.md":
                continue
            relative = path.relative_to(company_root)
            raw = path.read_text(encoding="utf-8", errors="ignore")
            cleaned = clean_markdown(raw)
            product_area = product_area_for_path(company, relative, cleaned)
            if product_area not in PRODUCT_AREAS[company]:
                product_area = PRODUCT_AREAS[company][0] if PRODUCT_AREAS[company] else ""
            for section_idx, (heading, section_text) in enumerate(heading_sections(cleaned)):
                words = section_text.split()
                for window_idx, window in enumerate(sliding_windows(words)):
                    if len(tokenize(window)) < 8:
                        continue
                    chunk_id = f"{company}:{relative}:{section_idx}:{window_idx}"
                    chunks.append(
                        ChunkRecord(
                            chunk_id=chunk_id,
                            text=window,
                            source_path=str(Path("data") / company / relative),
                            company=company,
                            product_area=product_area,
                            heading_path=heading,
                            tokens=tokenize(window),
                        )
                    )
    return chunks


def data_hash(root: Path | None = None) -> str:
    root = root or data_root()
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.md")):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def write_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def chunks_to_dicts(chunks: Sequence[ChunkRecord]) -> List[Dict[str, object]]:
    return [asdict(chunk) for chunk in chunks]
