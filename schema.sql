-- ============================================================================
-- NISTULA UNIFIED MESSAGING PLATFORM — PostgreSQL Schema
-- ============================================================================
--
-- This schema supports:
--   1. Guest profiles — one record per guest across all channels
--   2. All messages across all channels in one table
--   3. Conversations linked to guests linked to reservations
--   4. Tracking whether a message was AI drafted, agent edited, or auto-sent
--   5. AI confidence score and query type stored per inbound message
--
-- ============================================================================


-- ---------------------------------------------------------------------------
-- Custom ENUM types
-- ---------------------------------------------------------------------------

-- The channel a message originated from or was sent to
CREATE TYPE channel_type AS ENUM (
    'whatsapp',
    'booking_com',
    'airbnb',
    'instagram',
    'direct'
);

-- How the guest's query was classified by the AI
CREATE TYPE query_type AS ENUM (
    'pre_sales_availability',
    'pre_sales_pricing',
    'post_sales_checkin',
    'special_request',
    'complaint',
    'general_enquiry'
);

-- Whether a message is coming in from a guest or going out from the system
CREATE TYPE message_direction AS ENUM (
    'inbound',
    'outbound'
);

-- Tracks the lifecycle of an outbound (reply) message
CREATE TYPE draft_status AS ENUM (
    'ai_drafted',       -- AI generated the reply, pending review
    'agent_edited',     -- A human agent modified the AI draft before sending
    'auto_sent',        -- AI reply was auto-sent (high confidence)
    'manually_sent'     -- Agent wrote the reply from scratch
);

-- Reservation status
CREATE TYPE reservation_status AS ENUM (
    'confirmed',
    'checked_in',
    'checked_out',
    'cancelled',
    'no_show'
);


-- ---------------------------------------------------------------------------
-- 1. GUESTS — one record per real-world guest, deduplicated across channels
-- ---------------------------------------------------------------------------
-- A guest who contacts us via WhatsApp today and Airbnb tomorrow should
-- resolve to the same guest record. The guest_channels table (below)
-- maps their channel-specific identifiers to this single profile.

CREATE TABLE guests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name       VARCHAR(255) NOT NULL,
    email           VARCHAR(255),
    phone           VARCHAR(50),
    notes           TEXT,               -- internal notes about this guest
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for searching guests by name or email
CREATE INDEX idx_guests_email ON guests(email);
CREATE INDEX idx_guests_name  ON guests(full_name);


-- ---------------------------------------------------------------------------
-- 2. GUEST CHANNELS — maps channel-specific IDs to the unified guest record
-- ---------------------------------------------------------------------------
-- This junction table allows one guest to have multiple channel identities.
-- For example, a WhatsApp phone number AND an Airbnb profile ID.
-- The UNIQUE constraint prevents duplicate channel+identifier pairs.

CREATE TABLE guest_channels (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_id            UUID NOT NULL REFERENCES guests(id) ON DELETE CASCADE,
    channel             channel_type NOT NULL,
    channel_identifier  VARCHAR(255) NOT NULL,  -- e.g., phone number, Airbnb profile ID
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- A guest can only have one identity per channel+identifier combination
    UNIQUE (channel, channel_identifier)
);

CREATE INDEX idx_guest_channels_guest ON guest_channels(guest_id);
CREATE INDEX idx_guest_channels_lookup ON guest_channels(channel, channel_identifier);


-- ---------------------------------------------------------------------------
-- 3. PROPERTIES — villa/property details
-- ---------------------------------------------------------------------------

CREATE TABLE properties (
    id              VARCHAR(50) PRIMARY KEY,   -- e.g., 'villa-b1'
    name            VARCHAR(255) NOT NULL,
    location        VARCHAR(255),
    bedrooms        SMALLINT,
    max_guests      SMALLINT,
    base_rate       DECIMAL(10, 2),            -- per night in INR
    metadata        JSONB,                      -- flexible store for amenities, rules, etc.
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ---------------------------------------------------------------------------
-- 4. RESERVATIONS — bookings linked to guests and properties
-- ---------------------------------------------------------------------------

CREATE TABLE reservations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_ref     VARCHAR(50) NOT NULL UNIQUE,   -- e.g., 'NIS-2024-0891'
    guest_id        UUID NOT NULL REFERENCES guests(id),
    property_id     VARCHAR(50) NOT NULL REFERENCES properties(id),
    check_in_date   DATE NOT NULL,
    check_out_date  DATE NOT NULL,
    num_guests      SMALLINT NOT NULL DEFAULT 1,
    total_amount    DECIMAL(12, 2),
    status          reservation_status NOT NULL DEFAULT 'confirmed',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Check-out must be after check-in
    CONSTRAINT valid_dates CHECK (check_out_date > check_in_date)
);

CREATE INDEX idx_reservations_guest    ON reservations(guest_id);
CREATE INDEX idx_reservations_property ON reservations(property_id);
CREATE INDEX idx_reservations_ref      ON reservations(booking_ref);


-- ---------------------------------------------------------------------------
-- 5. CONVERSATIONS — groups messages into threads
-- ---------------------------------------------------------------------------
-- A conversation is a thread of messages between a guest and the system.
-- It can optionally be linked to a reservation (post-booking conversations).
-- The channel field tracks which channel this conversation is happening on.

CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_id        UUID NOT NULL REFERENCES guests(id),
    reservation_id  UUID REFERENCES reservations(id),  -- nullable for pre-booking chats
    channel         channel_type NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'closed', 'escalated')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversations_guest       ON conversations(guest_id);
CREATE INDEX idx_conversations_reservation ON conversations(reservation_id);
CREATE INDEX idx_conversations_status      ON conversations(status);


-- ---------------------------------------------------------------------------
-- 6. MESSAGES — every message (inbound + outbound) in one table
-- ---------------------------------------------------------------------------
-- This is the core table. All messages from all channels live here.
--
-- AI metadata fields (query_type, ai_confidence_score) are stored directly
-- on inbound messages rather than in a separate table. See design decision
-- notes below for the rationale.
--
-- For outbound messages, draft_status tracks whether the reply was
-- AI-drafted, edited by a human, auto-sent, or manually composed.

CREATE TABLE messages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID NOT NULL REFERENCES conversations(id),
    direction           message_direction NOT NULL,
    message_text        TEXT NOT NULL,
    timestamp           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- AI classification metadata (populated for inbound messages)
    query_type          query_type,                 -- null for outbound messages
    ai_confidence_score DECIMAL(3, 2)               -- 0.00 to 1.00, null for outbound
                        CHECK (ai_confidence_score IS NULL
                               OR (ai_confidence_score >= 0 AND ai_confidence_score <= 1)),

    -- Outbound message tracking (populated for outbound messages)
    draft_status        draft_status,               -- null for inbound messages
    drafted_by_model    VARCHAR(100),               -- e.g., 'claude-sonnet-4-20250514'
    original_ai_draft   TEXT,                        -- preserved even if agent edits the reply
    agent_id            UUID,                        -- who reviewed/edited (FK to a users table)

    -- Action taken on this message
    action_taken        VARCHAR(20)                  -- 'auto_send', 'agent_review', 'escalate'
                        CHECK (action_taken IS NULL
                               OR action_taken IN ('auto_send', 'agent_review', 'escalate')),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX idx_messages_conversation  ON messages(conversation_id);
CREATE INDEX idx_messages_direction     ON messages(direction);
CREATE INDEX idx_messages_timestamp     ON messages(timestamp);
CREATE INDEX idx_messages_query_type    ON messages(query_type) WHERE query_type IS NOT NULL;
CREATE INDEX idx_messages_draft_status  ON messages(draft_status) WHERE draft_status IS NOT NULL;
CREATE INDEX idx_messages_action        ON messages(action_taken) WHERE action_taken IS NOT NULL;


-- ============================================================================
-- DESIGN DECISIONS
-- ============================================================================
--
-- 1. GUEST DEDUPLICATION (guest_channels table)
--    Instead of storing channel info directly on the guest, a separate
--    guest_channels table allows one guest to have multiple channel
--    identities. This prevents duplicate guest records when someone
--    contacts us on WhatsApp and then books on Airbnb.
--
-- 2. SINGLE MESSAGES TABLE
--    Both inbound and outbound messages live in one table, distinguished
--    by the `direction` enum. This simplifies conversation timeline queries
--    (a single SELECT ordered by timestamp) and avoids UNION queries across
--    separate inbound/outbound tables.
--
-- 3. AI METADATA INLINE ON MESSAGES
--    The confidence score, query_type, and draft tracking fields are stored
--    directly on the messages table rather than in a separate ai_metadata
--    or ai_classifications table. This avoids JOINs in every dashboard and
--    analytics query. The trade-off is some nullable columns on outbound
--    messages, but this is a worthwhile simplification given that nearly
--    every query touching messages will need this data.
--
-- 4. ORIGINAL AI DRAFT PRESERVED
--    The original_ai_draft column preserves the AI's response even when an
--    agent edits it. This is critical for training feedback loops — you can
--    compare what the AI said vs. what the agent actually sent to identify
--    where the AI needs improvement.
--
-- 5. FLEXIBLE PROPERTY METADATA
--    The properties table uses a JSONB `metadata` column for amenities,
--    house rules, and other details that vary by property. This avoids
--    schema changes every time a new property attribute is needed.
--
-- ============================================================================
-- HARDEST DESIGN DECISION
-- ============================================================================
--
-- The hardest decision was whether to store AI metadata (confidence score,
-- query_type, draft_status) inline on the messages table or in a separate
-- ai_classifications table with a foreign key back to messages.
--
-- A separate table would be cleaner in a normalised sense — not every
-- message has AI metadata, so the nullable columns feel wasteful. It would
-- also make it easier to store multiple classification attempts or A/B test
-- different models per message.
--
-- I chose inline storage because in practice, every single dashboard query,
-- analytics report, and agent workflow screen needs to show the message
-- alongside its AI metadata. A JOIN on every read is an unnecessary cost
-- when the relationship is strictly 1:1 (one classification per inbound
-- message). The nullable columns on outbound messages are a small price for
-- dramatically simpler queries. If we later need multi-model A/B testing,
-- a separate table can be added without changing the core messages table.
-- ============================================================================
