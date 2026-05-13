"""
Mock property context store.

In production this would be backed by a database. For this assessment we
use a dictionary keyed by property_id containing all the information the
AI needs to answer guest queries accurately.
"""

from typing import Optional

# ---------------------------------------------------------------------------
# Property data — sourced from the assessment brief
# ---------------------------------------------------------------------------

PROPERTIES: dict[str, dict] = {
    "villa-b1": {
        "name": "Villa B1",
        "location": "Assagao, North Goa",
        "bedrooms": 3,
        "max_guests": 6,
        "private_pool": True,
        "check_in": "2:00 PM",
        "check_out": "11:00 AM",
        "base_rate_inr": 18_000,
        "base_rate_guests": 4,
        "extra_guest_rate_inr": 2_000,
        "wifi_password": "Nistula@2024",
        "caretaker_hours": "8:00 AM to 10:00 PM",
        "chef_on_call": True,
        "chef_note": "Pre-booking required",
        "availability_apr_20_24": True,
        "cancellation_policy": "Free cancellation up to 7 days before check-in",
    }
}

# Default property ID when none is specified in the message
DEFAULT_PROPERTY_ID = "villa-b1"


def get_property_context(property_id: Optional[str] = None) -> str:
    """
    Return a formatted string of property details for the Claude prompt.

    Falls back to the default property if the requested ID is not found.
    """
    pid = property_id or DEFAULT_PROPERTY_ID
    prop = PROPERTIES.get(pid, PROPERTIES[DEFAULT_PROPERTY_ID])

    return f"""Property: {prop['name']}, {prop['location']}
Bedrooms: {prop['bedrooms']} | Max guests: {prop['max_guests']} | Private pool: {'Yes' if prop['private_pool'] else 'No'}
Check-in: {prop['check_in']} | Check-out: {prop['check_out']}
Base rate: INR {prop['base_rate_inr']:,} per night (up to {prop['base_rate_guests']} guests)
Extra guest: INR {prop['extra_guest_rate_inr']:,} per night per person
WiFi password: {prop['wifi_password']}
Caretaker: Available {prop['caretaker_hours']}
Chef on call: {'Yes' if prop['chef_on_call'] else 'No'}, {prop['chef_note']}
Availability April 20-24: {'Available' if prop['availability_apr_20_24'] else 'Not available'}
Cancellation: {prop['cancellation_policy']}"""
