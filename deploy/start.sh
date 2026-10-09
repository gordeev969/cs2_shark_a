#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

if [[ ! -f .env ]]; then
  echo 'Create .env from deploy/production.env.example and set ANALYZER_DOMAIN.' >&2
  exit 1
fi

deployment_domain="$(sed -n 's/^ANALYZER_DOMAIN=//p' .env)"
if [[ ! "$deployment_domain" =~ ^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$ ]] \
  || [[ "$deployment_domain" == *example.com ]] \
  || [[ "$deployment_domain" == *example.org ]]; then
  echo 'Set ANALYZER_DOMAIN to a real DNS hostname without a scheme or path.' >&2
  exit 1
fi

chmod 600 .env
compose_args=(--env-file .env -f compose.yaml -f compose.production.yaml)
if [[ "${1:-}" == "--gc" ]]; then
  compose_args+=(--profile gc)
fi

docker compose "${compose_args[@]}" config --quiet
docker compose "${compose_args[@]}" up --build -d --wait
echo "Services started. Open https://${deployment_domain} after DNS resolves and HTTPS is issued."
echo 'For diagnostics: docker compose -f compose.yaml -f compose.production.yaml logs --tail=50 gateway backend'
