#!/usr/bin/env bash
set -euo pipefail
# Run on the destination VM; installs prerequisites, not the application.
if [[ $(id -u) -ne 0 ]]; then
  echo "Execute: sudo bash scripts/bootstrap-ubuntu.sh" >&2
  exit 1
fi
source /etc/os-release
if [[ "$ID" != ubuntu || "$VERSION_ID" != 24.04 ]]; then
  echo "Bootstrap preparado para Ubuntu 24.04. Consulte docs/INSTALACAO_GOOGLE_VM.md." >&2
  exit 1
fi
case "$(dpkg --print-architecture)" in
  amd64|arm64) ;;
  *) echo "Arquitetura não suportada." >&2; exit 1 ;;
esac
apt-get update
apt-get install -y ca-certificates curl git python3 docker.io docker-compose-v2 docker-buildx
systemctl enable --now docker
docker compose version
echo "Pré-requisitos instalados. Execute setup.py como seu usuário normal."
