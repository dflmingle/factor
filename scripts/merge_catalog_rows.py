#!/usr/bin/env python3
"""Merge freshly recomputed record rows back into the comparison catalog."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("updates", nargs="+", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.catalog.read_text())
    rows = {str(row["id"]): row for row in payload["results"]}
    replaced = []
    for path in args.updates:
        for row in json.loads(path.read_text()).get("results", []):
            key = str(row["id"])
            if key in rows:
                rows[key] = row
                replaced.append(f"{row['name']} [{row['handler']}]")
    payload["results"] = list(rows.values())
    args.catalog.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"replaced {len(replaced)} rows: {', '.join(replaced)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
