#!/usr/bin/env python3
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="Generic file patching tool for AI agents")
    parser.add_argument("file", help="File to patch")
    parser.add_argument("--search", required=True, help="Text to search for")
    parser.add_argument("--replace", required=True, help="Text to replace with")
    args = parser.parse_args()

    with open(args.file, "r") as f:
        text = f.read()

    if args.search not in text:
        print(f"Error: Search text not found in {args.file}")
        sys.exit(1)

    text = text.replace(args.search, args.replace)

    with open(args.file, "w") as f:
        f.write(text)
    
    print(f"Successfully patched {args.file}")

if __name__ == "__main__":
    main()
