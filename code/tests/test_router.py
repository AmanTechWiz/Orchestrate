from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schemas import Classification, RequestType, Status, Ticket
from router import decide


def test_outage_escalates() -> None:
    ticket = Ticket(issue="site is down & none of the pages are accessible", subject="", company="None")
    classification = Classification(company="", request_type=RequestType.bug, risk_tags=["outage"], cross_domain=True)
    decision = decide(ticket, classification, [])
    assert decision.status == Status.escalated


def test_invalid_replies() -> None:
    ticket = Ticket(issue="What is the name of the actor in Iron Man?", subject="", company="None")
    classification = Classification(company="", request_type=RequestType.invalid, risk_tags=[])
    decision = decide(ticket, classification, [])
    assert decision.status == Status.replied
