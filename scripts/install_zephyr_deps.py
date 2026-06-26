#!/usr/bin/env python3
"""Sync Zephyr's requirements*.txt into the pixi 'zephyr' feature.

Idempotent: this only `pixi add`s dependencies that are NOT already declared in
pyproject.toml. `pixi add` re-resolves loose specs (e.g. a bare `pytest`) and
re-pins the manifest's lower bound to whatever is newest at that moment, so
calling it unconditionally on every build churns pyproject.toml / pixi.lock for
no reason. By skipping deps that are already present we let the committed
manifest and lockfile govern versions; nothing changes unless Zephyr actually
introduces a new requirement (or this is a fresh checkout).
"""
import glob
import os
import re
import subprocess
import sys

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - fallback for older interpreters
    tomllib = None

ZEPHYR_SCRIPTS_DIR = ".zmk-workspace/zephyr/scripts"
PYPROJECT = "pyproject.toml"
FEATURE = "zephyr"


def normalize(name):
    """PEP 503 name normalization (case-insensitive, -/_/. equivalent)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def dep_name(spec):
    """Extract the distribution name from a requirement specifier line."""
    # Strip everything from the first version operator / extra / marker / space.
    m = re.match(r"^\s*([A-Za-z0-9._-]+)", spec)
    return normalize(m.group(1)) if m else None


def existing_dep_names():
    """Normalized names already declared in the zephyr feature's pypi deps."""
    if tomllib is None:
        return _existing_dep_names_regex()
    try:
        with open(PYPROJECT, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        return set()
    deps = (
        data.get("tool", {})
        .get("pixi", {})
        .get("feature", {})
        .get(FEATURE, {})
        .get("pypi-dependencies", {})
    )
    return {normalize(k) for k in deps}


def _existing_dep_names_regex():
    """Fallback parser when tomllib is unavailable: read the feature section."""
    section = f"[tool.pixi.feature.{FEATURE}.pypi-dependencies]"
    names = set()
    in_section = False
    try:
        with open(PYPROJECT, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("["):
                    in_section = stripped == section
                    continue
                if in_section and "=" in stripped and not stripped.startswith("#"):
                    names.add(normalize(stripped.split("=", 1)[0].strip()))
    except FileNotFoundError:
        return set()
    return names


def main():
    req_files = glob.glob(os.path.join(ZEPHYR_SCRIPTS_DIR, "requirements*.txt"))
    if not req_files:
        print(f"No requirements files found in {ZEPHYR_SCRIPTS_DIR}")
        sys.exit(0)

    specs = {}  # normalized name -> original spec string
    for req_file in req_files:
        try:
            with open(req_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("-r"):
                        continue
                    name = dep_name(line)
                    if name:
                        specs.setdefault(name, line)
        except Exception as e:
            print(f"Error reading {req_file}: {e}")
            sys.exit(1)

    if not specs:
        print("No dependencies found.")
        sys.exit(0)

    present = existing_dep_names()
    missing = [spec for name, spec in specs.items() if name not in present]

    if not missing:
        print(
            f"All {len(specs)} Zephyr dependencies already declared in {PYPROJECT}; "
            "nothing to add."
        )
        sys.exit(0)

    print(f"Adding {len(missing)} new Zephyr dependencies into the '{FEATURE}' feature via pixi...")
    cmd = ["pixi", "add", "--feature", FEATURE, "--pypi"] + missing
    try:
        subprocess.run(cmd, check=True)
        print("Successfully installed new Zephyr dependencies.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install dependencies: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
