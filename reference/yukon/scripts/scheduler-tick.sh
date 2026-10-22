#!/bin/bash
set -euo pipefail

ENV_FILE="$HOME/yukon/prospector/.env.local"
if [ -f "$ENV_FILE" ]; then
  SCANNER_API_TOKEN=$(grep '^SCANNER_API_TOKEN=' "$ENV_FILE" | cut -d= -f2-)
fi

if [ -z "${SCANNER_API_TOKEN:-}" ]; then
  echo "SCANNER_API_TOKEN not found" >&2
  exit 1
fi

curl -sf -X POST http://127.0.0.1:3000/api/scheduler/tick \
  -H "Authorization: Bearer $SCANNER_API_TOKEN" \
  -H "Content-Type: application/json"
