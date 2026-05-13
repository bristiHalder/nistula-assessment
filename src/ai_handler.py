"""
Claude AI integration — builds the prompt, calls the API, parses the response.

This module handles the single API call that performs both query
classification and reply drafting. Using one call instead of two keeps
latency low and avoids burning through API credits.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

import anthropic

from src.config import settings
from src.classifier import classify_by_keywords
from src.models import QueryType, UnifiedMessage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Response container
# ---------------------------------------------------------------------------

@dataclass
class AIResult:
    """Parsed result from the Claude API call."""
    query_type: QueryType
    drafted_reply: str
    confidence_score: float
    reasoning: str


# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a guest concierge AI for Nistula, a luxury villa rental company in Goa, India.
You respond to guest messages warmly, professionally, and accurately using only the property context provided below.

PROPERTY CONTEXT:
{property_context}

INSTRUCTIONS:
1. Classify the guest's query into exactly one of these types:
   pre_sales_availability | pre_sales_pricing | post_sales_checkin | special_request | complaint | general_enquiry

2. Draft a reply to the guest. Guidelines:
   - Use the guest's first name naturally
   - Be warm, helpful, and specific — you represent a luxury brand
   - Keep it concise: 2-4 sentences for simple queries, up to 5-6 for complex ones
   - For complaints: acknowledge, apologise, and assure immediate action — do NOT promise refunds or compensation
   - For pricing queries: always show the calculation breakdown
   - Never fabricate information not present in the property context

3. Rate your confidence from 0.0 to 1.0 based on:
   - How clearly the query maps to information in the property context (higher = clearer match)
   - Whether you had to make any assumptions (lower if yes)
   - Whether the query involves subjective judgement, complaints, or refund requests (lower for these)
   - Whether the query is ambiguous or could be interpreted multiple ways (lower if yes)

4. Provide brief reasoning for your confidence score.

You MUST respond in this exact JSON format and nothing else:
{{
  "query_type": "one_of_the_six_types",
  "drafted_reply": "Your reply to the guest",
  "confidence_score": 0.XX,
  "reasoning": "Brief explanation of why you chose this confidence level"
}}"""


# ---------------------------------------------------------------------------
# Valid query types for validation
# ---------------------------------------------------------------------------

VALID_QUERY_TYPES: set[str] = {
    "pre_sales_availability",
    "pre_sales_pricing",
    "post_sales_checkin",
    "special_request",
    "complaint",
    "general_enquiry",
}


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

async def generate_reply(
    message: UnifiedMessage,
    property_context: str,
) -> AIResult:
    """
    Call Claude to classify the query, draft a reply, and score confidence.

    Falls back gracefully if:
    - The API call fails → raises an exception for the endpoint to handle
    - Claude's response isn't valid JSON → uses keyword classifier as fallback
    - Claude returns an invalid query_type → uses keyword classifier
    """
    # Build the user message with all available context
    keyword_hint = classify_by_keywords(message.message_text)
    hint_line = f"\nKeyword hint (for reference only): {keyword_hint}" if keyword_hint else ""

    user_message = (
        f"Guest name: {message.guest_name}\n"
        f"Channel: {message.source}\n"
        f"Booking reference: {message.booking_ref or 'None'}\n"
        f"Message: {message.message_text}"
        f"{hint_line}"
    )

    # Call Claude API
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    response = client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT.format(property_context=property_context),
        messages=[
            {"role": "user", "content": user_message}
        ],
    )

    # Extract text from response
    raw_text = response.content[0].text.strip()
    logger.info("Claude raw response: %s", raw_text)

    # Parse JSON response
    return _parse_ai_response(raw_text, keyword_hint)


def _parse_ai_response(
    raw_text: str,
    keyword_fallback: Optional[QueryType],
) -> AIResult:
    """
    Parse Claude's JSON response with graceful fallbacks.

    If parsing fails entirely, returns a safe fallback that will trigger
    agent review.
    """
    # Try to extract JSON from the response (Claude sometimes wraps in markdown)
    json_text = raw_text
    if "```json" in raw_text:
        json_text = raw_text.split("```json")[1].split("```")[0].strip()
    elif "```" in raw_text:
        json_text = raw_text.split("```")[1].split("```")[0].strip()

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse Claude response as JSON: %s", raw_text)
        return AIResult(
            query_type=keyword_fallback or "general_enquiry",
            drafted_reply=raw_text,  # Use raw text as the reply
            confidence_score=0.4,    # Low confidence — needs review
            reasoning="AI response could not be parsed as JSON; using raw text",
        )

    # Validate query_type
    query_type = data.get("query_type", "")
    if query_type not in VALID_QUERY_TYPES:
        logger.warning("Invalid query_type from Claude: %s", query_type)
        query_type = keyword_fallback or "general_enquiry"

    # Validate confidence_score
    try:
        confidence = float(data.get("confidence_score", 0.5))
        confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
    except (TypeError, ValueError):
        confidence = 0.5

    return AIResult(
        query_type=query_type,
        drafted_reply=data.get("drafted_reply", "I'll connect you with our team shortly."),
        confidence_score=confidence,
        reasoning=data.get("reasoning", "No reasoning provided"),
    )
