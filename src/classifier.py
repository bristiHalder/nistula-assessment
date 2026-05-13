"""
Keyword-based query classifier — provides a fast initial hint.

This is NOT the authoritative classifier. The final query_type comes from
Claude's response. This module provides a keyword hint that is included in
the prompt to help guide Claude, and serves as a fallback if the AI
response cannot be parsed.
"""

import re
from typing import Optional

from src.models import QueryType

# ---------------------------------------------------------------------------
# Keyword patterns for each query type, ordered by specificity
# ---------------------------------------------------------------------------

KEYWORD_PATTERNS: list[tuple[QueryType, list[str]]] = [
    ("complaint", [
        "not working", "broken", "unacceptable", "unhappy", "not happy",
        "refund", "terrible", "disgusting", "worst", "disappointed",
        "complaint", "horrible", "filthy", "dirty", "damaged",
    ]),
    ("special_request", [
        "early check-in", "early checkin", "late check-out", "late checkout",
        "airport transfer", "airport pickup", "arrange", "special request",
        "birthday", "anniversary", "decoration", "surprise",
    ]),
    ("post_sales_checkin", [
        "check-in time", "checkin time", "check in time",
        "check-out time", "checkout time", "check out time",
        "wifi password", "wi-fi password", "wifi", "directions",
        "how to reach", "caretaker", "key", "lock",
    ]),
    ("pre_sales_pricing", [
        "rate", "price", "pricing", "cost", "how much", "tariff",
        "charges", "per night", "total cost", "quote",
    ]),
    ("pre_sales_availability", [
        "available", "availability", "dates", "vacancy", "book",
        "reserve", "open dates", "free dates",
    ]),
    ("general_enquiry", [
        "pet", "pets", "parking", "pool", "amenities", "facilities",
        "restaurant", "nearby", "location", "address",
    ]),
]


def classify_by_keywords(message_text: str) -> Optional[QueryType]:
    """
    Scan the message for keyword matches and return the first matching type.

    Returns None if no keywords match — the AI handler will classify it.
    """
    text_lower = message_text.lower()

    for query_type, keywords in KEYWORD_PATTERNS:
        for keyword in keywords:
            if keyword in text_lower:
                return query_type

    return None
