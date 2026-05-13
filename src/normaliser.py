"""
Message normaliser — converts channel-specific payloads into the unified schema.

Currently all channels share the same payload shape, so normalisation is
straightforward. This module exists as the extension point for when
different channels start sending different payload formats (e.g., Airbnb
includes a thread_id, Booking.com nests guest info differently).
"""

from src.models import InboundMessage, UnifiedMessage


def normalise_message(payload: InboundMessage) -> UnifiedMessage:
    """
    Convert an inbound channel message into the unified internal schema.

    Mapping:
      - payload.message  →  unified.message_text
      - A new UUID is auto-generated for message_id
      - All other fields pass through unchanged
    """
    return UnifiedMessage(
        source=payload.source,
        guest_name=payload.guest_name,
        message_text=payload.message,       # key rename: message → message_text
        timestamp=payload.timestamp,
        booking_ref=payload.booking_ref,
        property_id=payload.property_id,
    )
