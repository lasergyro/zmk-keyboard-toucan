#!/usr/bin/env bash

set -euo pipefail
shopt -s nullglob

log() {
  printf '==> %s\n' "$*"
}

warn() {
  printf 'warning: %s\n' "$*" >&2
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage: ./upload.sh [options] [target]

Flash Toucan UF2 artifacts to the XIAO bootloader volume on macOS.

Targets:
  both          Flash left, then right. Default.
  left          Flash only the left half.
  right         Flash only the right half.
  reset         Flash settings_reset to both halves.
  reset-left    Flash settings_reset to the left half only.
  reset-right   Flash settings_reset to the right half only.

Options:
  --debug           Enter UF2 bootloader via debug RPC before waiting for the volume.
  --dry-run         Print what would happen without waiting for hardware.
  --timeout SEC     Wait up to SEC seconds for a bootloader volume, default: 90
  --volume-root DIR Volume root to watch, default: /Volumes
  --volume-glob G   Bootloader glob under volume root, default: XIAO*
  -h, --help        Show this help text
EOF
}

require_file() {
  local path=$1
  [[ -f "$path" ]] || die "Missing required file: $path"
}

SCRIPT_DIR=$(
  cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
  pwd
)
REPO_ROOT=$SCRIPT_DIR
ARTIFACTS_DIR=${ARTIFACTS_DIR:-$REPO_ROOT/artifacts}
VOLUME_ROOT=/Volumes
VOLUME_GLOB='XIAO*'
TIMEOUT_SECONDS=90
COPY_RETRY_COUNT=6
COPY_RETRY_DELAY_SECONDS=1
DRY_RUN=0
DEBUG_MODE=0
TARGET=both
TARGET_SET=0

while (($# > 0)); do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --debug)
      DEBUG_MODE=1
      shift
      ;;
    --timeout)
      [[ $# -ge 2 ]] || die "--timeout requires a value"
      TIMEOUT_SECONDS=$2
      shift 2
      ;;
    --volume-root)
      [[ $# -ge 2 ]] || die "--volume-root requires a value"
      VOLUME_ROOT=$2
      shift 2
      ;;
    --volume-glob)
      [[ $# -ge 2 ]] || die "--volume-glob requires a value"
      VOLUME_GLOB=$2
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      die "Unknown option: $1"
      ;;
    *)
      if (( TARGET_SET )); then
        die "Only one target may be provided"
      fi
      TARGET=$1
      TARGET_SET=1
      shift
      ;;
  esac
done

artifact_for_kind() {
  local kind=$1
  local matches=()

  case "$kind" in
    left)
      matches=("$ARTIFACTS_DIR"/toucan_left-*.uf2)
      ;;
    right)
      matches=("$ARTIFACTS_DIR"/toucan_right-*.uf2)
      ;;
    reset)
      matches=("$ARTIFACTS_DIR"/settings_reset-*.uf2)
      ;;
    *)
      die "Unknown artifact kind: $kind"
      ;;
  esac

  (( ${#matches[@]} > 0 )) || die "No UF2 found for '$kind' in $ARTIFACTS_DIR"
  (( ${#matches[@]} == 1 )) || die "Multiple UF2 files found for '$kind': ${matches[*]}"
  printf '%s\n' "${matches[0]}"
}

list_bootloader_volumes() {
  local matches=("$VOLUME_ROOT"/$VOLUME_GLOB)
  for volume in "${matches[@]}"; do
    [[ -d "$volume" ]] && printf '%s\n' "$volume"
  done
}

wait_for_volume() {
  local label=$1
  local start
  start=$(date +%s)

  while true; do
    mapfile -t volumes < <(list_bootloader_volumes)

    if (( ${#volumes[@]} == 1 )); then
      printf '%s\n' "${volumes[0]}"
      return 0
    fi

    if (( ${#volumes[@]} > 1 )); then
      die "Multiple XIAO volumes detected while waiting for $label: ${volumes[*]}"
    fi

    if (( $(date +%s) - start >= TIMEOUT_SECONDS )); then
      die "Timed out waiting for $label bootloader volume under $VOLUME_ROOT/$VOLUME_GLOB"
    fi

    sleep 1
  done
}

wait_for_detach() {
  local volume=$1
  local label=$2
  local start
  start=$(date +%s)

  while [[ -d "$volume" ]]; do
    if (( $(date +%s) - start >= TIMEOUT_SECONDS )); then
      warn "$label volume is still mounted at $volume after ${TIMEOUT_SECONDS}s"
      return 0
    fi
    sleep 1
  done

  log "$label rebooted and unmounted $volume"
}

wait_for_writable_volume() {
  local volume=$1
  local label=$2
  local start
  start=$(date +%s)

  while true; do
    [[ -d "$volume" ]] || die "$label bootloader volume disappeared before it became writable"

    if [[ -w "$volume" ]]; then
      return 0
    fi

    if (( $(date +%s) - start >= TIMEOUT_SECONDS )); then
      die "Timed out waiting for $label bootloader volume to become writable: $volume"
    fi

    sleep 1
  done
}

copy_with_retry() {
  local artifact=$1
  local volume=$2
  local label=$3
  local target=$volume/$(basename "$artifact")
  local attempt
  local output

  for ((attempt = 1; attempt <= COPY_RETRY_COUNT; attempt++)); do
    [[ -d "$volume" ]] || die "$label bootloader volume disappeared before copy completed"

    if output=$(cp "$artifact" "$target" 2>&1); then
      sync
      return 0
    fi

    if (( attempt == COPY_RETRY_COUNT )); then
      die "Copy failed for $label after ${COPY_RETRY_COUNT} attempts: $output"
    fi

    warn "$label copy attempt ${attempt}/${COPY_RETRY_COUNT} failed: $output"
    sleep "$COPY_RETRY_DELAY_SECONDS"
  done
}

describe_artifact() {
  local artifact=$1
  local size
  local sha

  if size=$(stat -f '%z' "$artifact" 2>/dev/null); then
    :
  elif size=$(stat -c '%s' "$artifact" 2>/dev/null); then
    :
  else
    die "Unable to determine file size for $artifact"
  fi
  sha=$(shasum -a 256 "$artifact" | awk '{print $1}')
  printf '%s (%s bytes, sha256 %s)\n' "$artifact" "$size" "$sha"
}

trigger_debug_bootloader() {
  local side=$1

  require_file "$REPO_ROOT/debug.sh"

  if (( DRY_RUN )); then
    log "[dry-run] Would request UF2 bootloader over debug RPC for $side"
    return 0
  fi

  log "Requesting UF2 bootloader over debug RPC for $side"
  bash "$REPO_ROOT/debug.sh" rpc "$side" bootloader
}

flash_half() {
  local label=$1
  local kind=$2
  local side=${3:-}
  local artifact
  local volume

  artifact=$(artifact_for_kind "$kind")
  require_file "$artifact"

  log "$label artifact: $(describe_artifact "$artifact")"
  log "Trackpad note: the physical touchpad controller is on the right half."

  if (( DRY_RUN )); then
    if (( DEBUG_MODE )) && [[ -n "$side" ]]; then
      trigger_debug_bootloader "$side"
    else
      log "Connect the $label half over USB, then double-tap the XIAO RST button."
    fi
    log "[dry-run] Would wait for $VOLUME_ROOT/$VOLUME_GLOB and copy $(basename "$artifact")"
    return 0
  fi

  if (( DEBUG_MODE )) && [[ -n "$side" ]]; then
    trigger_debug_bootloader "$side"
  else
    log "Connect the $label half over USB, then double-tap the XIAO RST button."
  fi

  volume=$(wait_for_volume "$label")
  log "Detected $label bootloader volume at $volume"
  log "Waiting for $volume to become writable"
  wait_for_writable_volume "$volume" "$label"
  log "Copying $(basename "$artifact") to $volume"
  copy_with_retry "$artifact" "$volume" "$label"
  log "Copy complete for $label"
  wait_for_detach "$volume" "$label"
}

case "$TARGET" in
  both)
    flash_half "left" left left
    flash_half "right" right right
    ;;
  left)
    flash_half "left" left left
    ;;
  right)
    flash_half "right" right right
    ;;
  reset)
    flash_half "left reset" reset left
    flash_half "right reset" reset right
    ;;
  reset-left)
    flash_half "left reset" reset left
    ;;
  reset-right)
    flash_half "right reset" reset right
    ;;
  *)
    die "Unknown target: $TARGET"
    ;;
esac

log "Done"
