#!/usr/bin/env bash
set -euo pipefail

force=false
case "${1:-}" in
  "") ;;
  --force) force=true ;;
  *) printf 'Usage: %s [--force]\n' "$0" >&2; exit 1 ;;
esac
if [ "$#" -gt 1 ]; then
  printf 'Usage: %s [--force]\n' "$0" >&2
  exit 1
fi

if [ "$(uname -s)" != Darwin ]; then
  printf 'This installer supports macOS with Colima only.\n' >&2
  exit 1
fi

for tool in docker colima; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf 'Missing %s. See README.md for prerequisites.\n' "$tool" >&2
    exit 1
  fi
done
docker --context colima compose version >/dev/null
docker --context colima buildx version >/dev/null

if [ -L "$HOME/.codex/AGENTS.md" ] || [ ! -f "$HOME/.codex/AGENTS.md" ]; then
  printf '~/.codex/AGENTS.md must be a regular file, not a symlink.\n' >&2
  exit 1
fi
if [ -L "$HOME/.codex/skills" ] || [ ! -d "$HOME/.codex/skills" ]; then
  printf '~/.codex/skills must be a regular directory, not a symlink.\n' >&2
  exit 1
fi

source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
config_dir="$HOME/.config/agentbox"
launcher="$HOME/.local/bin/agentbox"

if [ "$force" = false ] &&
   { [ -e "$config_dir" ] || [ -L "$config_dir" ] ||
     [ -e "$launcher" ] || [ -L "$launcher" ]; }; then
  printf 'Agentbox files already exist. Review them, then use --force to replace.\n' >&2
  exit 1
fi

# Refuse symlink destinations even with --force.
for target in "$config_dir" "$config_dir/proxy" "$launcher" \
              "$config_dir/Dockerfile" "$config_dir/compose.yaml" "$config_dir/.dockerignore" \
              "$config_dir/proxy/Dockerfile" "$config_dir/proxy/squid.conf" \
              "$config_dir/proxy/.dockerignore"; do
  if [ -L "$target" ]; then
    printf 'Refusing symlink destination: %s\n' "$target" >&2
    exit 1
  fi
done

if ! docker --context colima info >/dev/null 2>&1; then
  colima start
fi
engine_version="$(docker --context colima version --format '{{.Server.Version}}')"
if [ "${engine_version%%.*}" -lt 28 ]; then
  printf 'Docker Engine 28+ is required for isolated gateway networking.\n' >&2
  exit 1
fi

mkdir -p "$config_dir/proxy" "$HOME/.local/bin"
install -m 644 "$source_dir/Dockerfile" "$source_dir/compose.yaml" "$source_dir/.dockerignore" "$config_dir/"
install -m 644 "$source_dir/proxy/Dockerfile" "$source_dir/proxy/squid.conf" \
  "$source_dir/proxy/.dockerignore" "$config_dir/proxy/"
install -m 755 "$source_dir/agentbox" "$launcher"

AGENTBOX_WORKSPACE="$source_dir" docker --context colima compose \
  -f "$config_dir/compose.yaml" build agent proxy

printf 'Installed %s\nEnsure ~/.local/bin is on PATH.\nFrom a project directory, run: agentbox login --device-auth\n' "$launcher"
