"""
Pydantic models for request validation and response serialisation.

Three models define the data flow:
  InboundMessage  →  UnifiedMessage  →  WebhookResponse
"""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Allowed values
# ---------------------------------------------------------------------------

SourceChannel = Literal["whatsapp", "booking_com", "airbnb", "instagram", "direct"]

QueryType = Literal[
    "pre_sales_availability",
    "pre_sales_pricing",
    "post_sales_checkin",
    "special_request",
    "complaint",
    "general_enquiry",
]

ActionType = Literal["auto_send", "agent_review", "escalate"]


# ---------------------------------------------------------------------------
# Inbound webhook payload — what the caller sends us
# ---------------------------------------------------------------------------

class InboundMessage(BaseModel):
    """Raw message payload received from any channel webhook."""

    source: SourceChannel
    guest_name: str
    message: str
    timestamp: datetime
    booking_ref: Optional[str] = None
    property_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Unified internal schema — normalised before AI processing
# ---------------------------------------------------------------------------

class UnifiedMessage(BaseModel):
    """
    Channel-agnostic message representation.

    Every inbound message is converted into this schema before being
    passed to the AI handler. The query_type field is populated after
    classification.
    """

    message_id: UUID = Field(default_factory=uuid4)
    source: SourceChannel
    guest_name: str
    message_text: str
    timestamp: datetime
    booking_ref: Optional[str] = None
    property_id: Optional[str] = None
    query_type: Optional[QueryType] = None


# ---------------------------------------------------------------------------
# Webhook response — returned to the caller
# ---------------------------------------------------------------------------

class WebhookResponse(BaseModel):
    """Final response returned by the /webhook/message endpoint."""

    message_id: UUID
    query_type: QueryType
    drafted_reply: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    action: ActionType
