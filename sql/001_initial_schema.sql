CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY,
    first_seen_at TIMESTAMPTZ NOT NULL,
    acquisition_channel VARCHAR(32) NOT NULL,
    country VARCHAR(2) NOT NULL,
    device_type VARCHAR(16) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_first_seen_at ON users (first_seen_at);

CREATE TABLE IF NOT EXISTS experiment_config (
    experiment_id VARCHAR(64) PRIMARY KEY,
    traffic_split_a NUMERIC(5, 4) NOT NULL CHECK (traffic_split_a >= 0),
    traffic_split_b NUMERIC(5, 4) NOT NULL CHECK (traffic_split_b >= 0),
    conversion_alert_threshold NUMERIC(8, 6) NOT NULL CHECK (conversion_alert_threshold >= 0),
    gmv_alert_threshold NUMERIC(12, 2) NOT NULL CHECK (gmv_alert_threshold >= 0),
    updated_at TIMESTAMPTZ NOT NULL,
    CHECK (traffic_split_a + traffic_split_b = 1)
);

INSERT INTO experiment_config (
    experiment_id, traffic_split_a, traffic_split_b,
    conversion_alert_threshold, gmv_alert_threshold, updated_at
) VALUES (
    'homepage_checkout_v1', 0.5000, 0.5000, 0.020000, 1000.00, NOW()
)
ON CONFLICT (experiment_id) DO UPDATE SET
    traffic_split_a = EXCLUDED.traffic_split_a,
    traffic_split_b = EXCLUDED.traffic_split_b,
    conversion_alert_threshold = EXCLUDED.conversion_alert_threshold,
    gmv_alert_threshold = EXCLUDED.gmv_alert_threshold,
    updated_at = NOW();

CREATE TABLE IF NOT EXISTS events (
    event_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users (user_id),
    session_id UUID NOT NULL,
    event_type VARCHAR(16) NOT NULL CHECK (event_type IN ('click', 'add_to_cart', 'buy')),
    experiment_group VARCHAR(1) NULL CHECK (experiment_group IN ('A', 'B')),
    channel VARCHAR(32) NOT NULL,
    product_id VARCHAR(32) NOT NULL,
    order_value NUMERIC(12, 2) NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CHECK (
        (event_type = 'buy' AND order_value > 0)
        OR (event_type <> 'buy' AND order_value IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_events_created_at ON events (created_at);
CREATE INDEX IF NOT EXISTS idx_events_group_created_at ON events (experiment_group, created_at);
CREATE INDEX IF NOT EXISTS idx_events_user_created_at ON events (user_id, created_at);
