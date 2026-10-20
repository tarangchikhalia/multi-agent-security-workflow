REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA support;
CREATE TABLE support.tenants (
    id text PRIMARY KEY,
    name text NOT NULL,
    owner text NOT NULL
);
CREATE TABLE support.requests (
    id text PRIMARY KEY,
    tenant_id text NOT NULL REFERENCES support.tenants(id),
    title text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
    description text NOT NULL CHECK (length(description) BETWEEN 1 AND 100000),
    owner text NOT NULL,
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'closed')),
    document_ids text[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE support.notes (
    id text PRIMARY KEY,
    request_id text NOT NULL REFERENCES support.requests(id),
    body text NOT NULL CHECK (length(body) BETWEEN 1 AND 100000),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

GRANT USAGE ON SCHEMA support TO requests_resource;
GRANT SELECT ON support.tenants TO requests_resource;
GRANT SELECT, INSERT, UPDATE ON support.requests TO requests_resource;
GRANT SELECT, INSERT ON support.notes TO requests_resource;
