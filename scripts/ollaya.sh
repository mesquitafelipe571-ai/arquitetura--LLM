#!/bin/sh
# Ollaya do perfil de desenvolvimento: binário e modelos em .runtime/ollaya, servidor só em loopback.
# Uso: sh scripts/ollaya.sh install | sh scripts/ollaya.sh <comando do ollaya>
set -eu

VERSION=0.18.0
SOURCE_SHA=a8bce962dc8219e696604403a5c2a30e6c9523f0 # tag v0.18.0 de ollaya-dev/ollaya
INSTALLER_SHA256=c2bddcd2b93a3e9422e1acb90e5ff5b0673a6d708bdc3926c6c4be2cdfdaa7a2 # scripts/install.sh nesse commit
SUMS_SHA256=ba4b8a35f0a8abb8a88f39ababc6e73d71c53b67a8d3f8d668d859bb3d6d7d36 # sha256sum.txt da release v0.18.0 (hash de cada binário)
ROOT=$(cd "$(dirname "$0")/.." && pwd)
DIR="$ROOT/.runtime/ollaya"

export OLLAYA_HOST=127.0.0.1:11435 OLLAYA_MODELS="$DIR/models"

if [ "${1:-}" = install ]; then
    # Executa código baixado: só com confirmação de uma pessoa no terminal. Sem
    # variável de ambiente que pule a pergunta, para um agente não poder liberar sozinho.
    if [ ! -t 0 ]; then
        echo "Instalação não confirmada: rode num terminal e responda à pergunta." >&2
        exit 1
    fi
    printf 'Instalar o Ollaya %s em %s (baixa e executa o instalador oficial)? [s/N] ' "$VERSION" "$DIR"
    read -r answer
    case $answer in s|S|sim|y|yes) ;; *) echo "Cancelado." >&2; exit 1 ;; esac
    # Baixa para um arquivo antes de executar: num pipe, uma falha do curl terminaria com sucesso.
    stage=$(mktemp -d)
    trap 'rm -rf "$stage"' EXIT
    verify() {
        if command -v sha256sum >/dev/null 2>&1; then
            actual=$(sha256sum "$1" | cut -d' ' -f1)
        else
            actual=$(shasum -a 256 "$1" | cut -d' ' -f1)
        fi
        if [ "$actual" != "$2" ]; then
            echo "$3 com checksum inesperado ($actual); nada foi executado." >&2
            exit 1
        fi
    }
    curl -fsSL -o "$stage/install.sh" "https://raw.githubusercontent.com/ollaya-dev/ollaya/$SOURCE_SHA/scripts/install.sh"
    verify "$stage/install.sh" "$INSTALLER_SHA256" Instalador
    curl -fsSL -o "$stage/sha256sum.txt" "https://github.com/ollaya-dev/ollaya/releases/download/v$VERSION/sha256sum.txt"
    verify "$stage/sha256sum.txt" "$SUMS_SHA256" "sha256sum.txt da release"
    # O instalador confere os binários pelo sha256sum.txt que ele baixa; assets de release podem ser
    # reenviados, então este curl lhe entrega a cópia conferida acima e baixa o resto normalmente.
    mkdir "$stage/bin"
    cat >"$stage/bin/curl" <<SHIM
#!/bin/sh
for arg; do [ "\${prev:-}" != -o ] || out=\$arg; prev=\$arg; done
case \$arg in */sha256sum.txt) exec cp "$stage/sha256sum.txt" "\$out" ;; esac
exec "$(command -v curl)" "\$@"
SHIM
    chmod +x "$stage/bin/curl"
    # Sem serviço e sem sudo.
    PATH="$stage/bin:$PATH" OLLAYA_VERSION=$VERSION OLLAYA_INSTALL_DIR="$DIR" OLLAYA_NO_SERVICE=1 sh "$stage/install.sh"
    exit
fi

if [ ! -x "$DIR/bin/ollaya" ]; then
    echo "Ollaya não está instalado neste projeto. Rode: npm run ollaya:install" >&2
    exit 1
fi
exec "$DIR/bin/ollaya" "$@"
