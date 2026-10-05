#!/bin/sh
# Runs once, on first initialisation of the Postgres data volume (docker-entrypoint-initdb.d).
# The application database (`sip`) is created by POSTGRES_DB. This script creates the pseudonym vault
# database with its own login role, so the vault is a separate connection/credential boundary even locally.
# Local-development credentials only; never reuse these values elsewhere.
set -eu

VAULT_DB="${SIP_VAULT_DB:-sip_vault}"
VAULT_USER="${SIP_VAULT_DB_USER:-sip_vault}"
VAULT_PASSWORD="${SIP_VAULT_DB_PASSWORD:-sip_vault}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
  CREATE ROLE ${VAULT_USER} LOGIN PASSWORD '${VAULT_PASSWORD}';
  CREATE DATABASE ${VAULT_DB} OWNER ${VAULT_USER};
  REVOKE CONNECT ON DATABASE ${VAULT_DB} FROM PUBLIC;
  REVOKE CONNECT ON DATABASE ${POSTGRES_DB} FROM PUBLIC;
  GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO ${POSTGRES_USER};
SQL
