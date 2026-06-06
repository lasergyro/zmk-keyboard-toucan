#!/usr/bin/env bash

set -euo pipefail

if [[ -z "${PIXI_PROJECT_ROOT:-}" ]]; then
  exec pixi run "$0" "$@"
fi

log() {
  printf '==> %s\n' "$*"
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage: ./debug.sh [command]

Commands:
  build     Build debug firmware into artifacts/debug. Default.
  upload    Flash debug UF2 artifacts to the XIAO bootloader volume.
  devices   List Toucan USB CDC ACM devices on macOS and annotate rpc/log roles.
  logs      Open one or both log streams and capture timestamped files.
  rpc       Send a debug RPC command over the USB CDC ACM RPC port.
  inject    Convenience wrapper for debug-only input injection commands.
  help      Show this help text.

Examples:
  ./debug.sh
  ./debug.sh devices
  ./debug.sh logs both
  ./debug.sh rpc left ping
  ./debug.sh inject right move 40 -25
EOF
}

require_file() {
  local path=$1
  [[ -f "$path" ]] || die "Missing required file: $path"
}

require_dir() {
  local path=$1
  [[ -d "$path" ]] || die "Missing required directory: $path"
}

require_command() {
  local cmd=$1
  command -v "$cmd" >/dev/null 2>&1 || die "Required command not found: $cmd"
}

find_compiler_cache() {
  if [[ -n "${COMPILER_CACHE:-}" ]]; then
    if command -v "$COMPILER_CACHE" >/dev/null 2>&1; then
      command -v "$COMPILER_CACHE"
      return 0
    fi
    die "Requested compiler cache not found: $COMPILER_CACHE"
  fi

  local candidate
  for candidate in ccache sccache; do
    if command -v "$candidate" >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done

  return 1
}

setup_compiler_cache() {
  local cache_bin
  cache_bin="$(find_compiler_cache || true)"
  [[ -n "$cache_bin" ]] || return 0

  COMPILER_CACHE_BIN="$cache_bin"
  COMPILER_CACHE_NAME="$(basename "$cache_bin")"

  case "$COMPILER_CACHE_NAME" in
    ccache)
      CCACHE_DIR="${CCACHE_DIR:-$REPO_ROOT/.ccache}"
      mkdir -p "$CCACHE_DIR"
      export CCACHE_DIR
      export CCACHE_BASEDIR="$WORKSPACE_DIR"
      export CCACHE_NOHASHDIR=1
      export CCACHE_COMPILERCHECK=content
      ;;
    sccache)
      SCCACHE_DIR="${SCCACHE_DIR:-$REPO_ROOT/.sccache}"
      mkdir -p "$SCCACHE_DIR"
      export SCCACHE_DIR
      ;;
  esac

  COMPILER_LAUNCHER_CMAKE_ARGS=(
    -DCMAKE_C_COMPILER_LAUNCHER="$COMPILER_CACHE_BIN"
    -DCMAKE_CXX_COMPILER_LAUNCHER="$COMPILER_CACHE_BIN"
    -DCMAKE_ASM_COMPILER_LAUNCHER="$COMPILER_CACHE_BIN"
  )

  log "Using compiler cache launcher: $COMPILER_CACHE_NAME"
}



copy_artifact() {
  local build_dir=$1
  local output_path=$2

  require_file "$build_dir/zephyr/zmk.uf2"
  cp -f "$build_dir/zephyr/zmk.uf2" "$output_path"
  log "Wrote $output_path"
}

sync_config_dir() {
  mkdir -p "$WORKSPACE_CONFIG_DIR" "$BUILD_DIR" "$ARTIFACT_DIR"
  rsync -a --delete "$CONFIG_SOURCE_DIR/" "$WORKSPACE_CONFIG_DIR/"
}

determine_toolchain_path() {
  local compiler
  compiler="$(command -v arm-none-eabi-gcc)" || return 1
  dirname "$(dirname "$compiler")"
}



ensure_workspace() {
  log "Synchronizing local ZMK workspace"
  "$REPO_ROOT/scripts/build.sh" --bootstrap-only --skip-brew
}

build_left_debug() {
  local build_dir="$BUILD_DIR/toucan_left_debug"
  local output_path="$ARTIFACT_DIR/toucan_left-debug-rgbled_adapter-nice_view_gem-seeeduino_xiao_ble-zmk.uf2"

  log "Building left debug firmware with USB logging"
  (
    cd "$WORKSPACE_DIR"
    "$WEST_BIN" build -s zmk/app -d "$build_dir" -p "$BUILD_PRISTINE" \
      -b seeeduino_xiao_ble \
      -S studio-rpc-usb-uart \
      -S zmk-usb-logging \
      -- \
      "${COMMON_DEBUG_CMAKE_ARGS[@]}" \
      -DCONFIG_ZMK_STUDIO=y \
      -DCONFIG_INPUT_LOG_LEVEL_WRN=y \
      -DEXTRA_DTC_OVERLAY_FILE="$REPO_ROOT/boards/shields/toucan/toucan_left_debug.overlay" \
      -DSHIELD="toucan_left rgbled_adapter nice_view_gem" \
      "${COMPILER_LAUNCHER_CMAKE_ARGS[@]}"
  )

  copy_artifact "$build_dir" "$output_path"
}

build_right_debug() {
  local build_dir="$BUILD_DIR/toucan_right"
  local output_path="$ARTIFACT_DIR/toucan_right-rgbled_adapter-seeeduino_xiao_ble-zmk.uf2"

  log "Building right debug firmware with independent USB serial"
  (
    cd "$WORKSPACE_DIR"
    "$WEST_BIN" build -s zmk/app -d "$build_dir" -p "$BUILD_PRISTINE" \
      -b seeeduino_xiao_ble \
      -S zmk-usb-logging \
      -- \
      "${COMMON_DEBUG_CMAKE_ARGS[@]}" \
      -DCONFIG_INPUT_LOG_LEVEL_INF=y \
      -DEXTRA_DTC_OVERLAY_FILE="$REPO_ROOT/boards/shields/toucan/toucan_right_debug.overlay" \
      -DSHIELD="toucan_right rgbled_adapter" \
      "${COMPILER_LAUNCHER_CMAKE_ARGS[@]}"
  )

  copy_artifact "$build_dir" "$output_path"
}

COMMAND=${1:-build}
COMMAND_ARGS=("${@:2}")

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

WEST_BIN="west"

CONFIG_SOURCE_DIR="$REPO_ROOT/config"
WORKSPACE_DIR="${WORKSPACE_DIR:-$REPO_ROOT/.zmk-workspace}"
WORKSPACE_CONFIG_DIR="$WORKSPACE_DIR/config"
BUILD_DIR="${BUILD_DIR:-$REPO_ROOT/build/debug}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$REPO_ROOT/artifacts/debug}"
BUILD_PRISTINE="${BUILD_PRISTINE:-always}"
COMPILER_CACHE_BIN=""
COMPILER_CACHE_NAME=""
declare -a COMPILER_LAUNCHER_CMAKE_ARGS=()

if [[ "$COMMAND" == "upload" ]]; then
  export ARTIFACTS_DIR="$ARTIFACT_DIR"
  exec "$REPO_ROOT/scripts/upload.sh" "${COMMAND_ARGS[@]}"
fi

if [[ "$COMMAND" != "build" ]]; then
  exec toucan-debug "$COMMAND" "${COMMAND_ARGS[@]}"
fi

require_dir "$CONFIG_SOURCE_DIR"
require_command rsync
require_command arm-none-eabi-gcc
ensure_workspace
require_command "$WEST_BIN"
sync_config_dir

install-zephyr-deps

export ZEPHYR_TOOLCHAIN_VARIANT=gnuarmemb
GNUARMEMB_TOOLCHAIN_PATH="$(determine_toolchain_path)" || \
  die "Unable to determine the GNU Arm Embedded toolchain path"
export GNUARMEMB_TOOLCHAIN_PATH
setup_compiler_cache

# Common cmake args shared by both halves — edit here to change both together.
# ZMK_LOG_LEVEL_DBG (not ZMK_LOGGING_MINIMAL) so LOG_DBG calls in
# behavior_leader_key and keymap.c are compiled in and visible at runtime.
COMMON_DEBUG_CMAKE_ARGS=(
  -DCONFIG_ASSERT=y
  -DCONFIG_LOG_MODE_DEFERRED=y
  -DCONFIG_LOG_BUFFER_SIZE=32768
  -DCONFIG_TOUCAN_DEBUG_RPC=y
  -DCONFIG_ZMK_LOG_LEVEL_DBG=y
  -DCONFIG_USB_MAX_NUM_TRANSFERS=16
  # Zephyr's DTS preprocessor does not include autoconf.h, so #ifdef CONFIG_*
  # guards in keymap .dtsi files are always false unless we forward them here.
  "-DDTS_EXTRA_CPPFLAGS=-DCONFIG_ZMK_BLE=1;-DCONFIG_ZMK_STUDIO=1"
  -DZMK_CONFIG="$WORKSPACE_CONFIG_DIR"
  -DZMK_EXTRA_MODULES="$REPO_ROOT;$REPO_ROOT/external/zmk-input-gestures;$REPO_ROOT/external/cirque-input-module"
)

build_left_debug
build_right_debug