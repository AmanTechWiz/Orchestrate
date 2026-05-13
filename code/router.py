from __future__ import annotations

from typing import List

from classifier import combined_text
from retriever import max_score
from schemas import Classification, Decision, RequestType, Status, Ticket, RetrievedChunk


TAU_REPLY = 0.52
# Stricter floor for auto-replying on fraud/theft-adjacent Visa tickets (vs generic TAU_REPLY).
TAU_STRONG = 0.68


def decide(ticket: Ticket, classification: Classification, chunks: List[RetrievedChunk]) -> Decision:
    text = combined_text(ticket).lower()
    top_score = max_score(chunks)
    low_evidence = top_score < TAU_REPLY

    if classification.request_type == RequestType.invalid:
        return Decision(status=Status.replied, reason="invalid_or_out_of_scope", low_evidence=False)

    if "outage" in classification.risk_tags:
        return Decision(status=Status.escalated, reason="possible_platform_outage", low_evidence=low_evidence)

    if classification.cross_domain and not classification.company:
        return Decision(status=Status.escalated, reason="unresolved_company", low_evidence=True)

    if "security_vuln" in classification.risk_tags:
        return Decision(status=Status.escalated, reason="security_vulnerability", low_evidence=low_evidence)

    if "account_access" in classification.risk_tags and any(
        phrase in text for phrase in ("restore my access", "not the workspace owner", "removed my seat")
    ):
        return Decision(status=Status.escalated, reason="account_access_requires_admin", low_evidence=low_evidence)

    if "billing_refund" in classification.risk_tags and any(
        phrase in text for phrase in ("refund", "chargeback", "make visa refund", "give me my money")
    ):
        if "bedrock" in text and "non-refundable" in " ".join(chunk.text.lower() for chunk in chunks):
            return Decision(status=Status.replied, reason="grounded_bedrock_refund_policy", low_evidence=low_evidence)
        return Decision(status=Status.escalated, reason="billing_refund_or_chargeback", low_evidence=low_evidence)

    if "legal_privacy" in classification.risk_tags and any(
        phrase in text for phrase in ("stop crawling", "legal", "gdpr")
    ):
        return Decision(status=Status.escalated, reason="legal_or_privacy_sensitive", low_evidence=low_evidence)

    if "fraud_or_theft" in classification.risk_tags:
        if classification.company == "visa" and chunks and top_score >= TAU_STRONG:
            return Decision(status=Status.replied, reason="visa_lost_stolen_or_identity_guidance", low_evidence=low_evidence)
        return Decision(status=Status.escalated, reason="fraud_or_theft_without_grounding", low_evidence=low_evidence)

    if low_evidence:
        return Decision(status=Status.escalated, reason="low_retrieval_evidence", low_evidence=True)

    return Decision(status=Status.replied, reason="grounded_answer_available", low_evidence=False)
