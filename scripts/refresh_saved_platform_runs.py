#!/usr/bin/env python3
"""Refresh truncated saved platform run payloads via the CLI.

Some saved ``*.results/<run_id>.json`` files were written from partial
responses and contain no chart series, which leaves the records unalignable
(``platform_chart_periods = 0``).  ``factor_result`` re-reads a finished run
without spending compute credits, so the payload can be repaired in place.

The previous file is kept next to the refreshed one as ``*.json.partial``.
"""
from __future__ import annotations

import argparse
import glob
import json
import shutil
import subprocess
from pathlib import Path


def find_saved_file(run_id: str) -> Path | None:
    for pattern in ("*.results/*.json", "*/*.results/*.json", "*/*/*.results/*.json"):
        for path in glob.glob(pattern):
            if Path(path).stem == run_id:
                return Path(path)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_ids", nargs="+")
    parser.add_argument("--cli", default="pandaai-cli")
    args = parser.parse_args()

    for run_id in args.run_ids:
        target = find_saved_file(run_id)
        if target is None:
            print(f"{run_id}: no saved file found")
            continue
        completed = subprocess.run(
            [args.cli, "--json", "factor_result", run_id],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            print(f"{run_id}: cli failed rc={completed.returncode} {completed.stderr[:200]}")
            continue
        payload = json.loads(completed.stdout)
        text = json.dumps(payload)
        if "query_rank_ic_sequence_chart" not in text:
            print(f"{run_id}: refreshed payload still has no RankIC chart")
            continue
        shutil.copy2(target, target.with_suffix(target.suffix + ".partial"))
        target.write_text(json.dumps(payload, ensure_ascii=False))
        print(f"{run_id}: refreshed {target} ({len(text)} chars, partial kept as .partial)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
