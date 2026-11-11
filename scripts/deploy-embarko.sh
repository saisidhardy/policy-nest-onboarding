#!/usr/bin/env bash
# Deploy backend and frontend to Embarko as two apps: <name>-api and <name>-web.
# Usage: EMBARKO_TOKEN=... scripts/deploy-embarko.sh [name]   (token optional for a first, temporary deploy)
set -euo pipefail

NAME="${1:-policynest}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
AUTH=()
[[ -n "${EMBARKO_TOKEN:-}" ]] && AUTH=(--oauth2-bearer "$EMBARKO_TOKEN")

deploy() {
  local app="$1" dir="$2"
  tar -czf "$STAGE/$app.tar.gz" --exclude=node_modules --exclude=.git --exclude='.env*' --exclude=.next \
    --exclude=.venv --exclude=__pycache__ --exclude=.pytest_cache --exclude=.ruff_cache --exclude=Dockerfile \
    --exclude=tests -C "$dir" .
  curl -sS -X POST https://ship.embarko.ai/apps "${AUTH[@]}" -H "X-App-Name: $app" -H "X-Agent-Name: devin" \
    -F "source=@$STAGE/$app.tar.gz"
  echo
}

deploy "$NAME-api" "$ROOT/backend"

mkdir -p "$STAGE/web"
cp -a "$ROOT/frontend/." "$STAGE/web/"
rm -rf "$STAGE/web/node_modules" "$STAGE/web/.next"
printf 'https://%s-api.embarko.app\n' "$NAME" > "$STAGE/web/backend-url.txt"
deploy "$NAME-web" "$STAGE/web"
