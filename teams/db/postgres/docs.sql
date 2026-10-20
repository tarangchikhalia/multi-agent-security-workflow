REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA docs;
CREATE TABLE docs.documents (
    id text PRIMARY KEY,
    title text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
    body text NOT NULL CHECK (length(body) BETWEEN 1 AND 100000),
    owner text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
GRANT USAGE ON SCHEMA docs TO docs_resource;
GRANT SELECT, INSERT, UPDATE, DELETE ON docs.documents TO docs_resource;
