# Part 3 — Thinking Question

## Scenario

It is 3am. A guest at Villa B1 sends a WhatsApp message:

> "There is no hot water and we have guests arriving for breakfast in 4 hours. This is unacceptable. I want a refund for tonight."

---

## Question A — The Immediate Response

**The AI reply at 3am:**

> Hi [Guest Name], I sincerely apologise for this — I completely understand how frustrating it is to not have hot water, especially with guests arriving soon. I've flagged this as urgent and our operations team is being notified right now. Someone will reach out to you very shortly to resolve this. Your comfort is our top priority and we will make this right.

**Why this wording:**
The message leads with empathy and a genuine apology — at 3am, the guest is stressed and needs to feel heard, not handled. It explicitly avoids promising a refund (that requires human authority) but commits to immediate action and uses "we will make this right" to signal the issue will be resolved without over-committing to a specific resolution. The tone is personal, not corporate.

---

## Question B — The System Design

The platform should trigger a multi-step response chain beyond the message:

1. **Classification & escalation**: The message is classified as `complaint` with confidence capped at 0.55. Action is `escalate` — the AI reply is held for review unless a 3-minute timeout passes with no agent online, in which case it auto-sends to avoid silence.

2. **Urgent notifications**: The system pushes high-priority alerts to (a) the property's assigned caretaker via WhatsApp/call, (b) the on-duty operations manager via SMS and app push notification, and (c) a Slack/Teams alert to the `#urgent-ops` channel. At 3am, phone calls should be the primary channel — push notifications get missed.

3. **Logging**: The message, AI draft, classification, confidence score, and all notification timestamps are logged in the messages table. An incident record is created linking the conversation to the property and reservation.

4. **30-minute failsafe**: If no human has acknowledged the alert within 30 minutes, the system (a) re-escalates by calling the backup operations manager, (b) sends a follow-up message to the guest: "I want to confirm our team has been alerted and someone is on their way to help you," and (c) creates a P1 incident ticket for morning review.

5. **Resolution tracking**: The incident stays open until a human explicitly marks it resolved, capturing what action was taken (plumber called, refund issued, etc.) for the feedback loop.

---

## Question C — The Learning

Three hot water complaints at Villa B1 in two months is a pattern, not a coincidence.

**What the system should do immediately:**

The platform should run pattern detection on complaint data — grouping by property, complaint category (keyword extraction: "hot water", "water heater", "geyser"), and time window. When a threshold is hit (e.g., 3+ similar complaints at the same property within 60 days), it should auto-generate a **maintenance alert** sent to the property owner and operations team with the complaint timeline, suggesting preventive action.

**What I would build:**

A **recurring issue detector** that aggregates complaint metadata (property + topic + frequency). When the threshold triggers, it creates a maintenance task in the ops dashboard: "Villa B1 — Hot water system: 3 complaints in 8 weeks. Schedule inspection." The system should also flag this context for the AI — if a future guest at Villa B1 books or checks in, the AI could proactively send a message: "We've recently upgraded the hot water system at Villa B1. If you experience any issues, our caretaker is available 24/7 at [number]." Turning a reactive complaint into a proactive touchpoint is the difference between damage control and guest loyalty.
