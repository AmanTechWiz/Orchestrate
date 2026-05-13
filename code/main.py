from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Dict, List

from build_index import build_index
from classifier import classify_ticket, combined_text
from providers import LLMProvider
from responder import build_response
from retriever import Retriever
from router import decide
from schemas import Ticket, model_to_dict
from utils.csv_io import read_tickets, write_output
from utils.logging import configure_logging
from validator import best_area_from_chunks, validate_row


def load_env() -> None:
    for env_path in (Path(".env"), Path(__file__).resolve().parent / ".env"):
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.__setitem__(key.strip(), value.strip().strip('"').strip("'"))


def select_provider(use_llm: bool = False) -> LLMProvider | None:
    if os.getenv("GROQ_API_KEY", "").strip() or use_llm:
        return LLMProvider()
    return None


def process_ticket(raw: Dict[str, str], retriever: Retriever, provider: LLMProvider | None = None) -> Dict[str, str]:
    ticket = Ticket(issue=raw.get("issue", ""), subject=raw.get("subject", ""), company=raw.get("company", ""))
    classification = classify_ticket(ticket, retriever=retriever)
    query = combined_text(ticket)
    # When company is unresolved, search all corpora (Retriever skips filtering if company is "").
    chunks = retriever.search(query, company=classification.company or "", top_k=5)
    decision = decide(ticket, classification, chunks)
    response = build_response(ticket, classification, decision, chunks, provider=provider)

    row = {
        "issue": ticket.issue,
        "subject": ticket.subject,
        "company": ticket.company.strip(),
        "response": response["response"],
        "product_area": response["product_area"],
        "status": decision.status.value if hasattr(decision.status, "value") else str(decision.status),
        "request_type": classification.request_type.value
        if hasattr(classification.request_type, "value")
        else str(classification.request_type),
        "justification": response["justification"],
    }
    return validate_row(row, fallback_area=best_area_from_chunks(chunks))


def run(input_path: str | Path, output_path: str | Path, use_llm: bool = False) -> List[Dict[str, str]]:
    load_env()
    logger = configure_logging()
    build_index()
    retriever = Retriever()
    provider = select_provider(use_llm=use_llm)
    rows = read_tickets(input_path)
    total = len(rows)
    logger.info("Processing %s rows from %s", total, input_path)
    if provider is not None and os.getenv("GROQ_API_KEY", "").strip():
        logger.info(
            "Groq enabled: one API call per ticket; output CSV is written only after all %s rows finish.",
            total,
        )
    output_rows: List[Dict[str, str]] = []
    for i, row in enumerate(rows, start=1):
        output_rows.append(process_ticket(row, retriever, provider=provider))
        logger.info("Finished row %s/%s", i, total)
    write_output(output_path, output_rows)
    logger.info("Wrote %s rows to %s", len(output_rows), output_path)
    return output_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the support triage agent.")
    parser.add_argument("--in", dest="input_path", required=True, help="Input support tickets CSV.")
    parser.add_argument("--out", dest="output_path", required=True, help="Output predictions CSV.")
    parser.add_argument("--sample", action="store_true", help="Reserved flag for sample-mode runs.")
    parser.add_argument("--use-llm", action="store_true", help="Enable optional configured LLM provider.")
    args = parser.parse_args()
    run(args.input_path, args.output_path, use_llm=args.use_llm)


if __name__ == "__main__":
    main()
