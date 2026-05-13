"""
Webhook endpoint integration tests.

These tests hit the /webhook/message endpoint using FastAPI's TestClient.
They make real Claude API calls — ensure ANTHROPIC_API_KEY is set in .env.

Run with: pytest tests/test_webhook.py -v
"""

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test 1: Pre-sales availability query (the example from the brief)
# ---------------------------------------------------------------------------

def test_availability_query():
    """
    Guest asks about villa availability for specific dates.
    Should classify as pre_sales_availability with high confidence.
    """
    payload = {
        "source": "whatsapp",
        "guest_name": "Rahul Sharma",
        "message": "Is the villa available from April 20 to 24? What is the rate for 2 adults?",
        "timestamp": "2026-05-05T10:30:00Z",
        "booking_ref": "NIS-2024-0891",
        "property_id": "villa-b1",
    }

    response = client.post("/webhook/message", json=payload)
    data = response.json()

    assert response.status_code == 200
    assert "message_id" in data
    assert data["query_type"] in ("pre_sales_availability", "pre_sales_pricing")
    assert "drafted_reply" in data
    assert 0.0 <= data["confidence_score"] <= 1.0
    assert data["action"] in ("auto_send", "agent_review", "escalate")
    # Availability info is in context — confidence should be reasonable
    assert data["confidence_score"] >= 0.5

    print(f"\n--- Test 1: Availability Query ---")
    print(f"Query type: {data['query_type']}")
    print(f"Confidence: {data['confidence_score']}")
    print(f"Action: {data['action']}")
    print(f"Reply: {data['drafted_reply']}")


# ---------------------------------------------------------------------------
# Test 2: Complaint — should always escalate
# ---------------------------------------------------------------------------

def test_complaint_escalates():
    """
    Guest sends a complaint about broken AC.
    Should classify as complaint and always escalate.
    """
    payload = {
        "source": "whatsapp",
        "guest_name": "Priya Patel",
        "message": "The AC in the master bedroom is not working and it is extremely hot. This is unacceptable for the price we are paying.",
        "timestamp": "2026-05-06T23:15:00Z",
        "booking_ref": "NIS-2024-0903",
        "property_id": "villa-b1",
    }

    response = client.post("/webhook/message", json=payload)
    data = response.json()

    assert response.status_code == 200
    assert data["query_type"] == "complaint"
    assert data["action"] == "escalate"
    # Complaints are capped at 0.55
    assert data["confidence_score"] <= 0.55

    print(f"\n--- Test 2: Complaint ---")
    print(f"Query type: {data['query_type']}")
    print(f"Confidence: {data['confidence_score']}")
    print(f"Action: {data['action']}")
    print(f"Reply: {data['drafted_reply']}")


# ---------------------------------------------------------------------------
# Test 3: Post-sales check-in query (WiFi password)
# ---------------------------------------------------------------------------

def test_checkin_query():
    """
    Guest asks for WiFi password after checking in.
    Should classify as post_sales_checkin with high confidence.
    """
    payload = {
        "source": "direct",
        "guest_name": "Alex Chen",
        "message": "Hi, we just checked in. What is the WiFi password?",
        "timestamp": "2026-05-07T14:30:00Z",
        "booking_ref": "NIS-2024-0910",
        "property_id": "villa-b1",
    }

    response = client.post("/webhook/message", json=payload)
    data = response.json()

    assert response.status_code == 200
    assert data["query_type"] == "post_sales_checkin"
    assert "drafted_reply" in data
    # WiFi password is directly in context — should be high confidence
    assert data["confidence_score"] >= 0.7

    print(f"\n--- Test 3: Check-in Query ---")
    print(f"Query type: {data['query_type']}")
    print(f"Confidence: {data['confidence_score']}")
    print(f"Action: {data['action']}")
    print(f"Reply: {data['drafted_reply']}")


# ---------------------------------------------------------------------------
# Test 4: Edge case — missing optional fields
# ---------------------------------------------------------------------------

def test_missing_optional_fields():
    """
    Message without booking_ref or property_id.
    Should still process successfully using default property context.
    """
    payload = {
        "source": "instagram",
        "guest_name": "Maria Santos",
        "message": "Hey! Do you allow pets at your villa?",
        "timestamp": "2026-05-08T09:00:00Z",
    }

    response = client.post("/webhook/message", json=payload)
    data = response.json()

    assert response.status_code == 200
    assert data["query_type"] == "general_enquiry"
    assert "drafted_reply" in data
    assert data["action"] in ("auto_send", "agent_review", "escalate")

    print(f"\n--- Test 4: Missing Optional Fields ---")
    print(f"Query type: {data['query_type']}")
    print(f"Confidence: {data['confidence_score']}")
    print(f"Action: {data['action']}")
    print(f"Reply: {data['drafted_reply']}")


# ---------------------------------------------------------------------------
# Test 5: Invalid source — should return 422
# ---------------------------------------------------------------------------

def test_invalid_source_rejected():
    """
    Message with an invalid source channel.
    Should be rejected by Pydantic validation with 422.
    """
    payload = {
        "source": "telegram",  # Not a valid source
        "guest_name": "Test User",
        "message": "Hello",
        "timestamp": "2026-05-08T09:00:00Z",
    }

    response = client.post("/webhook/message", json=payload)
    assert response.status_code == 422

    print(f"\n--- Test 5: Invalid Source ---")
    print(f"Status: {response.status_code}")
    print(f"Detail: {response.json()['detail']}")


# ---------------------------------------------------------------------------
# Test 6: Special request
# ---------------------------------------------------------------------------

def test_special_request():
    """
    Guest requests early check-in.
    Should classify as special_request.
    """
    payload = {
        "source": "booking_com",
        "guest_name": "James Wilson",
        "message": "Hi, our flight lands at 10am. Is early check-in possible? We would also love to arrange an airport transfer.",
        "timestamp": "2026-05-09T08:00:00Z",
        "booking_ref": "NIS-2024-0915",
        "property_id": "villa-b1",
    }

    response = client.post("/webhook/message", json=payload)
    data = response.json()

    assert response.status_code == 200
    assert data["query_type"] == "special_request"
    assert "drafted_reply" in data

    print(f"\n--- Test 6: Special Request ---")
    print(f"Query type: {data['query_type']}")
    print(f"Confidence: {data['confidence_score']}")
    print(f"Action: {data['action']}")
    print(f"Reply: {data['drafted_reply']}")
