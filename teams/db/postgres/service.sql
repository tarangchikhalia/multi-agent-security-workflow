REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA settings;
CREATE SCHEMA runtime;
CREATE TABLE settings.tenants (
    id text PRIMARY KEY,
    name text NOT NULL,
    owner text NOT NULL
);
CREATE TABLE settings.features (
    tenant_id text NOT NULL REFERENCES settings.tenants(id),
    feature_key text NOT NULL,
    enabled boolean NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id, feature_key)
);
CREATE TABLE runtime.features (
    tenant_id text NOT NULL REFERENCES settings.tenants(id),
    feature_key text NOT NULL,
    enabled boolean NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id, feature_key)
);
GRANT USAGE ON SCHEMA settings, runtime TO service_resource;
GRANT SELECT ON settings.tenants, settings.features TO service_resource;
GRANT UPDATE (enabled, updated_at) ON settings.features TO service_resource;
GRANT SELECT, INSERT, DELETE ON runtime.features TO service_resource;
