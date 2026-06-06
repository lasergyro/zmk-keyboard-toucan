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
Usage: ./build.sh [options] [target...]

Builds the firmware targets declared in build.yaml using a local west workspace.

Options:
  --bootstrap-only  Install dependencies and initialize/update the workspace.
  --skip-brew       Do not install missing Homebrew packages.
  --skip-update     Do not run west update.
  -h, --help        Show this help text.

Targets:
  If one or more targets are provided, only matching entries from build.yaml are
  built. A target may be the board name, the shield string, or the sanitized
  artifact/build name (spaces replaced with hyphens).

Environment overrides:
  BUILD_MATRIX_FILE  Path to build.yaml
  CONFIG_SOURCE_DIR  Path to the config directory
  WORKSPACE_DIR      Persistent west workspace directory
  VENV_DIR           Python virtualenv directory
  BUILD_ROOT         Per-target build directory root
  ARTIFACT_ROOT      Firmware output directory
  FALLBACK_BINARY    Artifact extension to use when no .uf2 was produced
  RUN_ZEPHYR_EXPORT  Set to 1 to run "west zephyr-export"
  BUILD_PRISTINE     west pristine mode to use (default: auto)
  COMPILER_CACHE     Compiler launcher to use (auto-detects ccache/sccache)
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



ensure_homebrew_packages() {
  (( SKIP_BREW )) && return

  require_command brew

  local -a packages=(
    python@3.12
    cmake
    ninja
    dtc
    arm-none-eabi-gcc
    ccache
  )
  local -a missing=()
  local package

  for package in "${packages[@]}"; do
    if ! brew list --formula "$package" >/dev/null 2>&1; then
      missing+=("$package")
    fi
  done

  if ((${#missing[@]} > 0)); then
    log "Installing missing Homebrew packages: ${missing[*]}"
    brew install "${missing[@]}"
  fi
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

ensure_host_tools() {
  require_command ruby
  require_command rsync
  require_command git
  require_command gperf
  require_command cmake
  require_command ninja
  require_command dtc
  require_command arm-none-eabi-gcc
}



sync_config_dir() {
  mkdir -p "$WORKSPACE_DIR" "$BUILD_ROOT" "$ARTIFACT_ROOT"
  mkdir -p "$WORKSPACE_CONFIG_DIR"
  rsync -a --delete "$CONFIG_SOURCE_DIR/" "$WORKSPACE_CONFIG_DIR/"
}

init_workspace() {
  sync_config_dir

  if [[ ! -d "$WORKSPACE_DIR/.west" ]]; then
    log "Initializing west workspace in $WORKSPACE_DIR"
    (
      cd "$WORKSPACE_DIR"
      "$WEST_BIN" init -l "$WORKSPACE_CONFIG_DIR"
    )
  fi
}

update_workspace() {
  sync_config_dir

  if (( SKIP_UPDATE )); then
    [[ -d "$WORKSPACE_DIR/zmk" ]] || die "--skip-update requires an existing workspace checkout"
  else
    log "Updating west projects"
    (
      cd "$WORKSPACE_DIR"
      "$WEST_BIN" update --narrow --fetch-opt=--depth=1
    )
  fi

  local zephyr_requirements="$WORKSPACE_DIR/zephyr/scripts/requirements.txt"
  require_file "$zephyr_requirements"

  install-zephyr-deps

  if (( RUN_ZEPHYR_EXPORT )); then
    log "Exporting Zephyr CMake package"
    (
      cd "$WORKSPACE_DIR"
      "$WEST_BIN" zephyr-export
    )
  fi
}

sync_external_repos() {
  local ext_dir
  for ext_dir in "$REPO_ROOT"/external/*; do
    if [[ -d "$ext_dir/.git" ]]; then
      if [[ -n "$(git -C "$ext_dir" status --porcelain)" ]]; then
        die "External repo $(basename "$ext_dir") is dirty. Please commit your changes."
      fi
    fi
  done

  local needs_update=0
  local ext_zmk="$REPO_ROOT/external/zmk"
  local ws_zmk="$WORKSPACE_DIR/zmk"
  
  if [[ ! -d "$ws_zmk/.git" ]]; then
    needs_update=1
  elif [[ -d "$ext_zmk/.git" ]]; then
    local ext_head ws_head
    ext_head="$(git -C "$ext_zmk" rev-parse HEAD 2>/dev/null || true)"
    ws_head="$(git -C "$ws_zmk" rev-parse HEAD 2>/dev/null || true)"
    if [[ -n "$ext_head" && -n "$ws_head" && "$ext_head" != "$ws_head" ]]; then
      log "external/zmk has new commits ($ext_head != $ws_head)"
      needs_update=1
    fi
  fi

  if (( needs_update )); then
    if (( SKIP_UPDATE )); then
      die "Workspace cache is out of date, but --skip-update was provided."
    fi
    update_workspace
  else
    sync_config_dir
  fi
}

determine_toolchain_path() {
  local compiler
  compiler="$(command -v arm-none-eabi-gcc)" || return 1

  dirname "$(dirname "$compiler")"
}

sanitize_name() {
  ruby -e '
    value = ARGV.fetch(0).tr(" /", "--").gsub(/-+/, "-")
    value = value.gsub(/[^0-9A-Za-z_.-]/, "")
    print value
  ' "$1"
}

default_artifact_name() {
  local board=$1
  local shield=$2

  if [[ -n "$shield" ]]; then
    printf '%s-zmk' "$(sanitize_name "$shield-$board")"
  else
    printf '%s-zmk' "$(sanitize_name "$board")"
  fi
}

build_identifier() {
  sanitize_name "$1"
}

list_builds() {
  ruby -e '
    require "yaml"

    data = YAML.load_file(ARGV.fetch(0))
    entries = data.fetch("include")

    entries.each do |entry|
      fields = [
        entry.fetch("board"),
        entry.fetch("shield", ""),
        entry.fetch("snippet", ""),
        entry.fetch("cmake-args", ""),
        entry.fetch("artifact-name", "")
      ]
      puts fields.join("\x1f")
    end
  ' "$BUILD_MATRIX_FILE"
}

target_requested() {
  local board=$1
  local shield=$2
  local artifact_name=$3

  if ((${#REQUESTED_TARGETS[@]} == 0)); then
    return 0
  fi

  local build_name
  build_name="${artifact_name:-$(default_artifact_name "$board" "$shield")}"

  local build_id
  build_id="$(build_identifier "$build_name")"

  local requested
  for requested in "${REQUESTED_TARGETS[@]}"; do
    if [[ "$requested" == "$board" || \
          "$requested" == "$shield" || \
          "$requested" == "$artifact_name" || \
          "$requested" == "$build_id" ]]; then
      return 0
    fi
  done

  return 1
}

copy_firmware_artifact() {
  local build_dir=$1
  local output_base=$2

  if [[ -f "$build_dir/zephyr/zmk.uf2" ]]; then
    cp -f "$build_dir/zephyr/zmk.uf2" "$output_base.uf2"
    printf '%s.uf2\n' "$output_base"
    return 0
  fi

  if [[ -f "$build_dir/zephyr/zmk.$FALLBACK_BINARY" ]]; then
    cp -f "$build_dir/zephyr/zmk.$FALLBACK_BINARY" "$output_base.$FALLBACK_BINARY"
    printf '%s.%s\n' "$output_base" "$FALLBACK_BINARY"
    return 0
  fi

  return 1
}

build_target() {
  local board=$1
  local shield=$2
  local snippet=$3
  local cmake_args=$4
  local artifact_name=$5

  local build_name
  build_name="${artifact_name:-$(default_artifact_name "$board" "$shield")}"

  local build_id
  build_id="$(build_identifier "$build_name")"

  local build_dir="$BUILD_ROOT/$build_id"
  local output_base="$ARTIFACT_ROOT/$build_id"
  local -a cmd=(
    "$WEST_BIN"
    build
    -p
    "$BUILD_PRISTINE"
    -s
    zmk/app
    -d
    "$build_dir"
    -b
    "$board"
  )

  if [[ -n "$snippet" ]]; then
    cmd+=(-S "$snippet")
  fi

  cmd+=(--)
  cmd+=(-DZMK_CONFIG="$WORKSPACE_CONFIG_DIR")

  if [[ -n "$shield" ]]; then
    cmd+=(-DSHIELD="$shield")
  fi

  cmd+=(-DZMK_EXTRA_MODULES="$REPO_ROOT;$REPO_ROOT/external/zmk-input-gestures;$REPO_ROOT/external/cirque-input-module")
  cmd+=("${COMPILER_LAUNCHER_CMAKE_ARGS[@]}")

  if [[ -n "$cmake_args" ]]; then
    # shellcheck disable=SC2206
    local extra_cmake_args=( $cmake_args )
    cmd+=("${extra_cmake_args[@]}")
  fi

  log "Building $build_name"
  (
    cd "$WORKSPACE_DIR"
    "${cmd[@]}"
  )

  local artifact_path
  artifact_path="$(copy_firmware_artifact "$build_dir" "$output_base")" || \
    die "No firmware artifact found in $build_dir/zephyr"
  log "Wrote $artifact_path"
}

main() {
  local bootstrap_only=0
  local check_repos_only=0

  while (($# > 0)); do
    case "$1" in
      --bootstrap-only)
        bootstrap_only=1
        ;;
      --skip-brew)
        SKIP_BREW=1
        ;;
      --skip-update)
        SKIP_UPDATE=1
        ;;
      --check-repos)
        check_repos_only=1
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        REQUESTED_TARGETS+=("$1")
        ;;
    esac
    shift
  done

  if (( check_repos_only )); then
    sync_external_repos
    exit 0
  fi

  require_file "$BUILD_MATRIX_FILE"
  require_dir "$CONFIG_SOURCE_DIR"

  ensure_homebrew_packages
  ensure_host_tools

  WEST_BIN="west"

  require_command "$WEST_BIN"

  init_workspace
  sync_external_repos


  export ZEPHYR_TOOLCHAIN_VARIANT=gnuarmemb
  GNUARMEMB_TOOLCHAIN_PATH="$(determine_toolchain_path)" || \
    die "Unable to determine the GNU Arm Embedded toolchain path"
  export GNUARMEMB_TOOLCHAIN_PATH
  setup_compiler_cache

  if (( bootstrap_only )); then
    log "Bootstrap complete"
    exit 0
  fi

  local built_any=0
  local board shield snippet cmake_args artifact_name
  while IFS=$'\x1f' read -r board shield snippet cmake_args artifact_name; do
    target_requested "$board" "$shield" "$artifact_name" || continue
    build_target "$board" "$shield" "$snippet" "$cmake_args" "$artifact_name"
    built_any=1
  done < <(list_builds)

  (( built_any )) || die "No build targets matched: ${REQUESTED_TARGETS[*]}"

  log "Artifacts are in $ARTIFACT_ROOT"
}

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_MATRIX_FILE="${BUILD_MATRIX_FILE:-$REPO_ROOT/build.yaml}"
CONFIG_SOURCE_DIR="${CONFIG_SOURCE_DIR:-$REPO_ROOT/config}"
WORKSPACE_DIR="${WORKSPACE_DIR:-$REPO_ROOT/.zmk-workspace}"
WORKSPACE_CONFIG_DIR="$WORKSPACE_DIR/config"
BUILD_ROOT="${BUILD_ROOT:-$REPO_ROOT/build}"
ARTIFACT_ROOT="${ARTIFACT_ROOT:-$REPO_ROOT/artifacts}"
FALLBACK_BINARY="${FALLBACK_BINARY:-bin}"
WEST_BIN=""
SKIP_BREW=0
SKIP_UPDATE=0
RUN_ZEPHYR_EXPORT="${RUN_ZEPHYR_EXPORT:-0}"
BUILD_PRISTINE="${BUILD_PRISTINE:-auto}"
COMPILER_CACHE_BIN=""
COMPILER_CACHE_NAME=""
declare -a COMPILER_LAUNCHER_CMAKE_ARGS=()
declare -a REQUESTED_TARGETS=()

main "$@"
