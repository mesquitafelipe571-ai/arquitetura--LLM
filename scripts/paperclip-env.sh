#!/usr/bin/env bash
# Shared by the install and start commands. Existing environment overrides win.
PAPERCLIP_REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PAPERCLIP_RUNTIME_ROOT="$PAPERCLIP_REPO_ROOT/.runtime"
export PAPERCLIP_HOME="${PAPERCLIP_HOME:-$PAPERCLIP_RUNTIME_ROOT/paperclip}"
export COREPACK_HOME="${COREPACK_HOME:-$PAPERCLIP_RUNTIME_ROOT/corepack}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$PAPERCLIP_RUNTIME_ROOT/cache}"
export XDG_DATA_HOME="${XDG_DATA_HOME:-$PAPERCLIP_RUNTIME_ROOT/share}"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$PAPERCLIP_RUNTIME_ROOT/config}"
export XDG_STATE_HOME="${XDG_STATE_HOME:-$PAPERCLIP_RUNTIME_ROOT/state}"
export npm_config_cache="${npm_config_cache:-$PAPERCLIP_RUNTIME_ROOT/npm}"
export npm_config_devdir="${npm_config_devdir:-$PAPERCLIP_RUNTIME_ROOT/node-gyp}"
export PATH="$PAPERCLIP_RUNTIME_ROOT/bin:$PATH"
