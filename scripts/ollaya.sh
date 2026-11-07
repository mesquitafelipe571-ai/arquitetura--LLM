#!/bin/sh
# Ollaya do perfil de desenvolvimento: binário e modelos em .runtime/ollaya, servidor só em loopback.
# Uso: sh scripts/ollaya.sh install | sh scripts/ollaya.sh <comando do ollaya>
set -eu

VERSION=0.18.0
SOURCE_SHA=a8bce962dc8219e696604403a5c2a30e6c9523f0 # tag v0.18.0 de ollaya-dev/ollaya
ROOT=$(cd "$(dirname "$0")/.." && pwd)
DIR="$ROOT/.runtime/ollaya"

export OLLAYA_HOST=127.0.0.1:11435 OLLAYA_MODELS="$DIR/models"

if [ "${1:-}" = install ]; then
    # O instalador confere os binários da release pelo sha256sum.txt; sem serviço e sem sudo.
    curl -fsSL "https://raw.githubusercontent.com/ollaya-dev/ollaya/$SOURCE_SHA/scripts/install.sh" |
        OLLAYA_VERSION=$VERSION OLLAYA_INSTALL_DIR="$DIR" OLLAYA_NO_SERVICE=1 sh
    exit
fi

if [ ! -x "$DIR/bin/ollaya" ]; then
    echo "Ollaya não está instalado neste projeto. Rode: npm run ollaya:install" >&2
    exit 1
fi
exec "$DIR/bin/ollaya" "$@"
