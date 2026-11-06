#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/paperclip-env.sh"

for executable in git node; do
  command -v "$executable" >/dev/null || { echo "Instale $executable antes de continuar." >&2; exit 1; }
done
node --input-type=module -e '
  const [major, minor] = process.versions.node.split(".").map(Number);
  if (major < 24 || (major === 24 && minor < 11)) {
    console.error("O Paperclip requer Node.js 24.11 ou superior.");
    process.exit(1);
  }
'

if ! command -v rustup >/dev/null; then
  echo "Instale o Rust via rustup (https://rustup.rs) e disponibilize rustup no PATH." >&2
  exit 1
fi

git -C "$PAPERCLIP_REPO_ROOT" submodule update --init --recursive -- paperclip
cd "$PAPERCLIP_REPO_ROOT/paperclip"
mkdir -p "$PAPERCLIP_RUNTIME_ROOT/bin"
if command -v corepack >/dev/null; then
  corepack enable --install-directory "$PAPERCLIP_RUNTIME_ROOT/bin" pnpm
elif ! command -v pnpm >/dev/null; then
  echo "Instale Corepack ou pnpm 9.15.4 antes de continuar." >&2
  exit 1
fi
if [[ "$(pnpm --version)" != "9.15.4" ]]; then
  echo "Esta versão do Paperclip requer pnpm 9.15.4; use Corepack para selecionar a versão." >&2
  exit 1
fi

paperclip_rust_channel="$(awk -F '"' '/^channel[[:space:]]*=/ { print $2; exit }' packages/paperclip-runner/rust-toolchain.toml)"
[[ -n "$paperclip_rust_channel" ]] || { echo "Versão do Rust ausente no submódulo." >&2; exit 1; }
rustup toolchain install "$paperclip_rust_channel" --profile minimal --component rustfmt
pnpm install --frozen-lockfile --store-dir "${PAPERCLIP_PNPM_STORE:-$PAPERCLIP_RUNTIME_ROOT/pnpm-store}"
pnpm --filter @paperclipai/plugin-sdk build
pnpm --filter @paperclipai/paperclip-runner build:typescript
node --import ./cli/node_modules/tsx/dist/loader.mjs --input-type=module -e '
  const { paperclipRunnerBinaryNeedsBuild } = await import("./scripts/dev-runner-native-binary.mjs");
  if (paperclipRunnerBinaryNeedsBuild({ repoRoot: process.cwd(), nativeRunnerRequired: true })) {
    const { spawnSync } = await import("node:child_process");
    const build = spawnSync("pnpm", ["--filter", "@paperclipai/paperclip-runner", "build:binary"], { stdio: "inherit" });
    process.exit(build.status ?? 1);
  }
'

# Use the same setup routine as `paperclipai run`, saving config without starting
# a second server or installing a system service.
node --import ./cli/node_modules/tsx/dist/loader.mjs --input-type=module -e '
  const { onboard } = await import("./cli/src/commands/onboard.ts");
  await onboard({ yes: true, installService: false, invokedByRun: true });
'
pnpm db:migrate
printf '\nPaperclip instalado. Dados: %s\nInicie com: %s/scripts/start-paperclip.sh\n' "$PAPERCLIP_HOME" "$PAPERCLIP_REPO_ROOT"
