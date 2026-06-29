#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


def load(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"missing known worker file: {path}")
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    workers = data.get("workers")
    if not isinstance(workers, dict):
        raise SystemExit(f"missing [workers] table in {path}")
    return workers


def main() -> int:
    parser = argparse.ArgumentParser(description="Read local known-worker mappings.")
    parser.add_argument("command", choices=["list", "get"])
    parser.add_argument("name", nargs="?")
    parser.add_argument("--file", default=".cao/known-workers.local.toml")
    args = parser.parse_args()

    workers = load(Path(args.file))
    if args.command == "list":
        print(json.dumps(sorted(workers), ensure_ascii=False, indent=2))
        return 0

    if not args.name:
        raise SystemExit("get requires a worker name")

    if args.name in workers:
        print(json.dumps(workers[args.name], ensure_ascii=False, indent=2))
        return 0

    lowered = args.name.lower()
    matches = [name for name in workers if name.lower() == lowered]
    if len(matches) == 1:
        print(json.dumps(workers[matches[0]], ensure_ascii=False, indent=2))
        return 0

    partials = [name for name in workers if lowered in name.lower()]
    if partials:
        print(json.dumps({"error": "not_found", "candidates": partials}, ensure_ascii=False, indent=2))
        return 2

    print(json.dumps({"error": "not_found"}, ensure_ascii=False, indent=2))
    return 2


if __name__ == "__main__":
    sys.exit(main())
