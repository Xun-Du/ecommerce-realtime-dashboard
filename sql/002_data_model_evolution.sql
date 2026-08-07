ALTER TABLE users
ADD COLUMN IF NOT EXISTS customer_type VARCHAR(16) NOT NULL DEFAULT 'new'
CHECK (customer_type IN ('new', 'returning', 'unknown'));

ALTER TABLE users
ADD COLUMN IF NOT EXISTS external_user_id VARCHAR(128) NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_external_user_id
ON users (external_user_id)
WHERE external_user_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS experiments (
    experiment_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    hypothesis TEXT NULL,
    status VARCHAR(16) NOT NULL CHECK (
        status IN ('draft', 'running', 'paused', 'completed', 'cancelled')
    ),
    primary_metric VARCHAR(64) NOT NULL,
    start_time TIMESTAMPTZ NULL,
    end_time TIMESTAMPTZ NULL,
    traffic_split_a NUMERIC(5, 4) NOT NULL CHECK (traffic_split_a >= 0),
    traffic_split_b NUMERIC(5, 4) NOT NULL CHECK (traffic_split_b >= 0),
    minimum_sample_size INTEGER NOT NULL CHECK (minimum_sample_size >= 1),
    significance_level NUMERIC(5, 4) NOT NULL CHECK (
        significance_level > 0 AND significance_level < 1
    ),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CHECK (traffic_split_a + traffic_split_b = 1),
    CHECK (end_time IS NULL OR start_time IS NULL OR end_time > start_time)
);

INSERT INTO experiments (
    experiment_id,
    name,
    hypothesis,
    status,
    primary_metric,
    start_time,
    end_time,
    traffic_split_a,
    traffic_split_b,
    minimum_sample_size,
    significance_level,
    created_at,
    updated_at
)
SELECT
    experiment_id,
    experiment_id,
    NULL,
    'running',
    'purchase_conversion_rate',
    NULL,
    NULL,
    traffic_split_a,
    traffic_split_b,
    100,
    0.0500,
    updated_at,
    updated_at
FROM experiment_config
ON CONFLICT (experiment_id) DO UPDATE SET
    traffic_split_a = EXCLUDED.traffic_split_a,
    traffic_split_b = EXCLUDED.traffic_split_b,
    updated_at = EXCLUDED.updated_at;

CREATE TABLE IF NOT EXISTS experiment_variants (
    variant_id VARCHAR(96) PRIMARY KEY,
    experiment_id VARCHAR(64) NOT NULL REFERENCES experiments (experiment_id),
    variant_key VARCHAR(32) NOT NULL,
    name VARCHAR(128) NOT NULL,
    is_control BOOLEAN NOT NULL DEFAULT FALSE,
    traffic_proportion NUMERIC(5, 4) NOT NULL CHECK (
        traffic_proportion >= 0 AND traffic_proportion <= 1
    ),
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (experiment_id, variant_key)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_experiment_variants_one_control
ON experiment_variants (experiment_id)
WHERE is_control;

INSERT INTO experiment_variants (
    variant_id,
    experiment_id,
    variant_key,
    name,
    is_control,
    traffic_proportion,
    created_at
)
SELECT
    experiment_id || ':A',
    experiment_id,
    'A',
    'Control',
    TRUE,
    traffic_split_a,
    updated_at
FROM experiment_config
ON CONFLICT (variant_id) DO UPDATE SET
    traffic_proportion = EXCLUDED.traffic_proportion;

INSERT INTO experiment_variants (
    variant_id,
    experiment_id,
    variant_key,
    name,
    is_control,
    traffic_proportion,
    created_at
)
SELECT
    experiment_id || ':B',
    experiment_id,
    'B',
    'Treatment',
    FALSE,
    traffic_split_b,
    updated_at
FROM experiment_config
ON CONFLICT (variant_id) DO UPDATE SET
    traffic_proportion = EXCLUDED.traffic_proportion;

ALTER TABLE events
ADD COLUMN IF NOT EXISTS experiment_id VARCHAR(64) NULL
REFERENCES experiments (experiment_id);

ALTER TABLE events
ADD COLUMN IF NOT EXISTS source VARCHAR(64) NULL;

ALTER TABLE events
ADD COLUMN IF NOT EXISTS medium VARCHAR(64) NULL;

ALTER TABLE events
ADD COLUMN IF NOT EXISTS campaign_id VARCHAR(128) NULL;

ALTER TABLE events
ADD COLUMN IF NOT EXISTS campaign_name VARCHAR(256) NULL;

ALTER TABLE events
ADD COLUMN IF NOT EXISTS order_id VARCHAR(128) NULL;

ALTER TABLE events
ADD COLUMN IF NOT EXISTS event_properties JSONB NOT NULL DEFAULT '{}'::JSONB;

UPDATE events
SET experiment_id = 'homepage_checkout_v1'
WHERE experiment_id IS NULL
  AND experiment_group IN ('A', 'B');

UPDATE events
SET source = channel
WHERE source IS NULL;

UPDATE events
SET order_id = event_id::TEXT
WHERE event_type = 'buy'
  AND order_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_events_experiment_created_at
ON events (experiment_id, created_at);

CREATE INDEX IF NOT EXISTS idx_events_source_medium_created_at
ON events (source, medium, created_at);

CREATE INDEX IF NOT EXISTS idx_events_campaign_created_at
ON events (campaign_id, created_at);

CREATE UNIQUE INDEX IF NOT EXISTS idx_events_order_id_unique
ON events (order_id)
WHERE order_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS experiment_assignments (
    experiment_id VARCHAR(64) NOT NULL REFERENCES experiments (experiment_id),
    user_id UUID NOT NULL REFERENCES users (user_id),
    variant_id VARCHAR(96) NOT NULL REFERENCES experiment_variants (variant_id),
    assigned_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (experiment_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_experiment_assignments_variant
ON experiment_assignments (experiment_id, variant_id, assigned_at);

INSERT INTO experiment_assignments (
    experiment_id,
    user_id,
    variant_id,
    assigned_at
)
SELECT DISTINCT ON (experiment_id, user_id)
    experiment_id,
    user_id,
    experiment_id || ':' || experiment_group,
    created_at
FROM events
WHERE experiment_id IS NOT NULL
  AND experiment_group IN ('A', 'B')
ORDER BY experiment_id, user_id, created_at
ON CONFLICT (experiment_id, user_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS experiment_results (
    result_id UUID PRIMARY KEY,
    experiment_id VARCHAR(64) NOT NULL REFERENCES experiments (experiment_id),
    calculated_at TIMESTAMPTZ NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    metrics_snapshot JSONB NOT NULL DEFAULT '{}'::JSONB,
    statistics_snapshot JSONB NOT NULL DEFAULT '{}'::JSONB,
    decision_code VARCHAR(64) NOT NULL,
    decision_level VARCHAR(16) NOT NULL CHECK (
        decision_level IN ('info', 'success', 'warning', 'error')
    ),
    decision_message TEXT NOT NULL,
    notes TEXT NULL,
    CHECK (window_end > window_start),
    UNIQUE (experiment_id, calculated_at)
);

CREATE INDEX IF NOT EXISTS idx_experiment_results_window
ON experiment_results (experiment_id, window_start, window_end);

CREATE TABLE IF NOT EXISTS metric_thresholds (
    threshold_id UUID PRIMARY KEY,
    metric_name VARCHAR(64) NOT NULL,
    direction VARCHAR(16) NOT NULL CHECK (
        direction IN ('above', 'below', 'increase', 'decrease')
    ),
    threshold_value NUMERIC(18, 6) NOT NULL CHECK (threshold_value >= 0),
    scope VARCHAR(64) NOT NULL DEFAULT 'global',
    experiment_id VARCHAR(64) NULL REFERENCES experiments (experiment_id),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_metric_thresholds_scope_enabled
ON metric_thresholds (scope, enabled);
