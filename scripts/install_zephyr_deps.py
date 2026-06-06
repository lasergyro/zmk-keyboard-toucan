#!/usr/bin/env python3
import os
import sys
import glob
import subprocess

def main():
    zephyr_scripts_dir = ".zmk-workspace/zephyr/scripts"
    req_files = glob.glob(os.path.join(zephyr_scripts_dir, "requirements*.txt"))
    
    if not req_files:
        print(f"No requirements files found in {zephyr_scripts_dir}")
        sys.exit(0)
        
    deps = set()
    for req_file in req_files:
        try:
            with open(req_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("-r"):
                        continue
                    deps.add(line)
        except Exception as e:
            print(f"Error reading {req_file}: {e}")
            sys.exit(1)
            
    if not deps:
        print("No dependencies found.")
        sys.exit(0)
        
    print(f"Installing {len(deps)} Zephyr dependencies via pixi...")
    cmd = ["pixi", "add", "--pypi"] + list(deps)
    try:
        subprocess.run(cmd, check=True)
        print("Successfully installed Zephyr dependencies.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install dependencies: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
