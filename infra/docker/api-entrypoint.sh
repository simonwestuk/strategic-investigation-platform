#!/bin/sh
# API container entrypoint: apply database migrations (app DB + vault schema), then exec the server.
# Set SIP_RUN_MIGRATIONS=false when migrations are run as a separate job (e.g. multi-replica deployments,
# where concurrent replicas would otherwise race to migrate).
set -eu

if [ "${SIP_RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "api-entrypoint: running 'sip db upgrade'"
  sip db upgrade
fi

exec "$@"
