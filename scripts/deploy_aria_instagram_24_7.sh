#!/usr/bin/env bash
# Compatibility entrypoint: use the versioned source, not an embedded old copy.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/server_git_deploy.sh" "$@"
