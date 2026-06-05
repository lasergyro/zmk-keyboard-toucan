#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./release.sh [command]

Commands:
  build     Build release firmware. Default.
  upload    Flash UF2 artifacts to the XIAO bootloader volume.
  help      Show this help text.
EOF
}

COMMAND=${1:-build}
COMMAND_ARGS=("${@:2}")

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

case "$COMMAND" in
  build)
    exec "$REPO_ROOT/scripts/build.sh" "${COMMAND_ARGS[@]}"
    ;;
  upload)
    FORCE_CHANGE=0
    NEW_ARGS=()
    for arg in "${COMMAND_ARGS[@]}"; do
      if [[ "$arg" == "--change" ]]; then
        FORCE_CHANGE=1
      else
        NEW_ARGS+=("$arg")
      fi
    done
    COMMAND_ARGS=("${NEW_ARGS[@]}")

    if [[ $FORCE_CHANGE == 0 ]]; then
      if uv run "$REPO_ROOT/scripts/debug_tool.py" devices 2>/dev/null | grep -q "type=rpc"; then
        echo "error: A Toucan device running debug firmware is connected via USB." >&2
        echo "To overwrite debug firmware with a release version, you must pass '--change'." >&2
        exit 1
      fi
    fi

    export ARTIFACTS_DIR="$REPO_ROOT/artifacts"
    exec "$REPO_ROOT/scripts/upload.sh" "${COMMAND_ARGS[@]}"
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "error: Unknown command: $COMMAND" >&2
    usage
    exit 1
    ;;
esac
