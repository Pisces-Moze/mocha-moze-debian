#!/usr/bin/env python3
"""Verify the published project-file inventory in a five-repository workspace."""
# SPDX-License-Identifier: GPL-2.0-only
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path, help="Parent of the five repository directories")
    args = parser.parse_args()
    manifest = Path(__file__).resolve().parents[1] / "manifests/open-source-files.json"
    entries = json.loads(manifest.read_text(encoding="utf-8"))["files"]
    errors = []
    for entry in entries:
        path = args.workspace / entry["repository"] / entry["path"]
        if not path.is_file():
            errors.append(f"missing: {path}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            errors.append(f"changed: {path}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Verified {len(entries)} published project files")


if __name__ == "__main__":
    main()
