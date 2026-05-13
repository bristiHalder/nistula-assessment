"""
Confidence scoring and action determination.

The confidence score is a composite of Claude's self-assessment and
rule-based business logic adjustments. This separation ensures that
certain message types (complaints, ambiguous queries) always route
to human agents, regardless of how confident the AI feels.

See README.md for a full explanation of the scoring logic.
"""

from src.ai_handler import AIResult
from src.models import ActionType, QueryType, UnifiedMessage


# ---------------------------------------------------------------------------
# Rule-based adjustments
# ---------------------------------------------------------------------------

# Complaints always need human review — cap the confidence
COMPLAINT_CONFIDENCE_CAP = 0.55

# Boost for returning guests (they have a booking reference)
RETURNING_GUEST_BOOST = 0.05


def adjust_confidence(ai_result: AIResult, message: UnifiedMessage) -> float:
    """
    Apply rule-based adjustments to Claude's raw confidence score.

    Rules applied in order:
    1. Complaints are capped at 0.55 — refund/compensation decisions
       require human judgement.
    2. If a booking_ref is present for a pre-sales query, boost by 0.05 —
       returning guests provide more context for accurate answers.
    3. Final score is clamped to [0.0, 1.0].
    """
    score = ai_result.confidence_score

    # Rule 1: Complaints are always capped
    if ai_result.query_type == "complaint":
        score = min(score, COMPLAINT_CONFIDENCE_CAP)

    # Rule 2: Returning guest boost
    if message.booking_ref and ai_result.query_type in (
        "pre_sales_availability",
        "pre_sales_pricing",
    ):
        score += RETURNING_GUEST_BOOST

    # Clamp to valid range
    return round(max(0.0, min(1.0, score)), 2)


# ---------------------------------------------------------------------------
# Action determination
# ---------------------------------------------------------------------------

def determine_action(confidence_score: float, query_type: QueryType) -> ActionType:
    """
    Determine the action to take based on confidence score and query type.

    Thresholds:
      - > 0.85              → auto_send
      - 0.60 to 0.85        → agent_review
      - < 0.60 OR complaint → escalate
    """
    # Complaints always escalate, regardless of confidence
    if query_type == "complaint":
        return "escalate"

    if confidence_score > 0.85:
        return "auto_send"
    elif confidence_score >= 0.60:
        return "agent_review"
    else:
        return "escalate"
