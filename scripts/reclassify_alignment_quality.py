#!/usr/bin/env python3
"""Re-apply the alignment quality gate to a finished comparison catalog.

The gate is a pure function of the stored per-record metrics, so a rule change
that only touches the classification (not the local evaluation) can be applied
without re-running the expensive panel rebuild.  This script rewrites the
quality fields in place and prints the before/after status counts.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from platform_alignment_rules import classify_alignment_quality  # noqa: E402


def quality_from_row(row: dict) -> dict:
    return classify_alignment_quality(
        net_delta_pp=row.get("local_net_delta_pp"),
        gross_delta_pp=row.get("local_gross_delta_pp"),
        platform_rank_ic=row.get("platform_rank_ic"),
        local_rank_ic=row.get("local_rank_ic"),
        top20_overlap=row.get("top20_overlap"),
        local_periods=row.get("periods"),
        platform_periods=row.get("platform_chart_periods"),
        turnover_status=row.get("turnover_alignment"),
        sensitivity_delta_pp=row.get("platform_turnover_sensitivity_delta_pp"),
        ic_series_corr=row.get("ic_series_corr"),
        ic_series_mean_abs_delta=row.get("ic_series_mean_abs_delta"),
        ic_series_periods=row.get("ic_series_periods"),
        ic_series_rank_corr=row.get("ic_series_rank_corr"),
        ic_series_std_local=row.get("ic_series_std_local"),
        ic_series_std_platform=row.get("ic_series_std_platform"),
        ic_series_beta=row.get("ic_series_beta"),
        ic_series_mean_abs_delta_scaled=row.get("ic_series_mean_abs_delta_scaled"),
        handler=row.get("handler"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--write", action="store_true", help="rewrite the catalog in place")
    args = parser.parse_args()

    payload = json.loads(args.catalog.read_text())
    before = Counter(row.get("alignment_quality") for row in payload["results"])
    eligible_before = sum(1 for row in payload["results"] if row.get("local_mining_eligible"))

    changed = []
    for row in payload["results"]:
        quality = quality_from_row(row)
        if quality["status"] != row.get("alignment_quality"):
            changed.append((row.get("name"), row.get("handler"), row.get("alignment_quality"), quality["status"]))
        row["alignment_quality"] = quality["status"]
        row["alignment_quality_flags"] = quality["flags"]
        row["alignment_quality_diagnostic_flags"] = quality["diagnostic_flags"]
        row["alignment_quality_reason"] = quality["reason"]
        row["local_mining_eligible"] = bool(quality["mining_eligible"])
        row["net_tier"] = quality["net_tier"]

    after = Counter(row.get("alignment_quality") for row in payload["results"])
    eligible_after = sum(1 for row in payload["results"] if row.get("local_mining_eligible"))
    print(f"records={len(payload['results'])}")
    print("before:", dict(before), "eligible:", eligible_before)
    print("after: ", dict(after), "eligible:", eligible_after)
    for name, handler, old, new in changed:
        print(f"  {name} [{handler}]: {old} -> {new}")

    if args.write:
        args.catalog.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        print("catalog rewritten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
