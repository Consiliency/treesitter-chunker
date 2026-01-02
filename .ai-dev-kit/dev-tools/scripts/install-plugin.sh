#!/bin/bash
# Install the AI Dev Kit Claude Code plugin into ~/.claude/plugins
# Usage:
#   ./dev-tools/scripts/install-plugin.sh [--dev] [--force]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PLUGIN_SRC="${REPO_ROOT}/plugins/ai-dev-kit"
PLUGIN_DST="${HOME}/.claude/plugins/ai-dev-kit"

MODE="copy"
FORCE="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dev)
      MODE="dev"
      shift
      ;;
    --force)
      FORCE="true"
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [--dev] [--force]"
      echo ""
      echo "Options:"
      echo "  --dev    Create symlink instead of copy (for development)"
      echo "  --force  Overwrite existing installation"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

if [ ! -d "$PLUGIN_SRC" ]; then
  echo "error: plugin source not found at $PLUGIN_SRC" >&2
  exit 1
fi

mkdir -p "${HOME}/.claude/plugins"

if [ -e "$PLUGIN_DST" ] || [ -L "$PLUGIN_DST" ]; then
  if [ "$FORCE" = "true" ]; then
    rm -rf "$PLUGIN_DST"
  else
    echo "plugin already exists at $PLUGIN_DST" >&2
    echo "use --force to overwrite"
    exit 0
  fi
fi

if [ "$MODE" = "dev" ]; then
  ln -s "$PLUGIN_SRC" "$PLUGIN_DST"
  echo "installed plugin symlink: $PLUGIN_DST -> $PLUGIN_SRC"
  exit 0
fi

# Copy mode
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete "$PLUGIN_SRC/" "$PLUGIN_DST/"
else
  cp -R "$PLUGIN_SRC" "$PLUGIN_DST"
fi

echo "installed plugin copy: $PLUGIN_DST"
