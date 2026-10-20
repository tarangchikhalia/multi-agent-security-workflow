#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
 --set=docs_password="$DOCS_DB_PASSWORD" --set=requests_password="$REQUESTS_DB_PASSWORD" \
 --set=service_password="$SERVICE_DB_PASSWORD" <<'SQL'
CREATE ROLE docs_resource LOGIN PASSWORD :'docs_password';
CREATE ROLE requests_resource LOGIN PASSWORD :'requests_password';
CREATE ROLE service_resource LOGIN PASSWORD :'service_password';
REVOKE CONNECT ON DATABASE postgres FROM PUBLIC;
REVOKE CONNECT ON DATABASE template1 FROM PUBLIC;
CREATE DATABASE docs_db;
CREATE DATABASE requests_db;
CREATE DATABASE service_db;
REVOKE ALL ON DATABASE docs_db, requests_db, service_db FROM PUBLIC;
GRANT CONNECT ON DATABASE docs_db TO docs_resource;
GRANT CONNECT ON DATABASE requests_db TO requests_resource;
GRANT CONNECT ON DATABASE service_db TO service_resource;
SQL
for name in docs requests service; do
 psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "${name}_db" --file="/schema/${name}.sql"
done
