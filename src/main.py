"""
FastAPI application — the /webhook/message endpoint.

This is the entry point for all inbound guest messages. The request flows
through four stages:

  1. Validate & normalise the inbound payload
  2. Load property context for the AI prompt
  3. Call Claude to classify, draft a reply, and score confidence
  4. Apply business rules and return the response
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from src.ai_handler import generate_reply
from src.confidence import adjust_confidence, determine_action
from src.config import settings
from src.models import InboundMessage, WebhookResponse
from src.normaliser import normalise_message
from src.property_context import get_property_context

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate configuration on startup."""
    settings.validate()
    logger.info("Configuration validated. Claude model: %s", settings.CLAUDE_MODEL)
    yield


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Nistula Guest Message Handler",
    description="Webhook endpoint for processing guest messages across channels",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "service": "nistula-message-handler"}


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------

@app.post("/webhook/message", response_model=WebhookResponse)
async def handle_message(payload: InboundMessage) -> WebhookResponse:
    """
    Process an inbound guest message and return a drafted AI reply.

    Flow:
      1. Normalise the inbound payload into the unified schema
      2. Load the relevant property context
      3. Send to Claude for classification + reply drafting
      4. Adjust confidence with business rules
      5. Determine action (auto_send / agent_review / escalate)
      6. Return the complete response
    """
    logger.info(
        "Received message from %s via %s (property: %s)",
        payload.guest_name,
        payload.source,
        payload.property_id,
    )

    # Step 1: Normalise
    unified = normalise_message(payload)
    logger.info("Normalised message — ID: %s", unified.message_id)

    # Step 2: Load property context
    context = get_property_context(unified.property_id)

    # Step 3: Call Claude
    try:
        ai_result = await generate_reply(unified, context)
        logger.info(
            "Claude response — type: %s, raw_confidence: %.2f, reasoning: %s",
            ai_result.query_type,
            ai_result.confidence_score,
            ai_result.reasoning,
        )
    except Exception as e:
        logger.error("Claude API call failed: %s", str(e))
        raise HTTPException(
            status_code=503,
            detail={
                "error": "AI service temporarily unavailable",
                "message": "The AI service could not process your request. Please retry in a moment.",
                "technical_detail": str(e),
            },
        )

    # Step 4: Adjust confidence
    final_confidence = adjust_confidence(ai_result, unified)
    logger.info(
        "Confidence adjusted: %.2f → %.2f",
        ai_result.confidence_score,
        final_confidence,
    )

    # Step 5: Determine action
    action = determine_action(final_confidence, ai_result.query_type)
    logger.info("Action determined: %s", action)

    # Step 6: Build response
    response = WebhookResponse(
        message_id=unified.message_id,
        query_type=ai_result.query_type,
        drafted_reply=ai_result.drafted_reply,
        confidence_score=final_confidence,
        action=action,
    )

    return response


# ---------------------------------------------------------------------------
# Global exception handler for unexpected errors
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Catch-all for unhandled exceptions — returns a clean 500 response."""
    logger.exception("Unhandled exception: %s", str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again.",
        },
    )
