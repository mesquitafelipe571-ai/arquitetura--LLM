#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/paperclip-env.sh"
if [[ ! -f "$PAPERCLIP_REPO_ROOT/paperclip/server/node_modules/tsx/dist/cli.mjs" ]]; then
  echo "Execute primeiro: $PAPERCLIP_REPO_ROOT/scripts/install-paperclip.sh" >&2
  exit 1
fi
if ! command -v pnpm >/dev/null; then
  echo "pnpm não encontrado. Execute novamente scripts/install-paperclip.sh." >&2
  exit 1
fi
cd "$PAPERCLIP_REPO_ROOT/paperclip"
exec pnpm dev:once "$@"
