#!/usr/bin/env python3
"""Validate the portable local inputs for a canonical platform comparison.

This is a read-only preflight.  It checks the alignment contract and the
restored cache layout without reading credentials or contacting PandaAI.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_RULES_DOCUMENT,
    ALIGNMENT_RULE_VERSION,
    alignment_config_snapshot,
    validate_alignment_config,
)


DEFAULT_CACHE_ROOT = Path(
    os.environ.get(
        "FACTOR_RESEARCH_CACHE_ROOT",
        str(PROJECT_ROOT / "quantlab" / ".quantlab" / "cache" / "research" / "cn_equity"),
    )
).expanduser()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument(
        "--check-snapshot",
        action="store_true",
        help="also require the tracked LFS archive and its manifest",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    return parser.parse_args()


def check_path(path: Path, *, pattern: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"path": str(path), "exists": path.exists(), "is_dir": path.is_dir()}
    if pattern is not None and path.is_dir():
        result["matching_files"] = len(list(path.glob(pattern)))
        result["pattern"] = pattern
    return result


def main() -> int:
    args = parse_args()
    cache_root = args.cache_root.expanduser().resolve()
    try:
        validate_alignment_config(alignment_config_snapshot())
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    paths = {
        "rules_document": PROJECT_ROOT / ALIGNMENT_RULES_DOCUMENT,
        "price_root": cache_root / "tushare_factor_recheck" / "qfq" / "daily_batches",
        "cap_root": cache_root / "tushare_factor_recheck" / "daily_basic_full_a",
        "financial_root": cache_root / "financial_full_a",
        "calendar_root": cache_root / "trade_calendar",
        "platform_reports": cache_root / "reports",
    }
    checks = {
        "rules_document": check_path(paths["rules_document"]),
        "price_root": check_path(paths["price_root"], pattern="batch_*.parquet"),
        "cap_root": check_path(paths["cap_root"], pattern="daily_basic_*.parquet"),
        "financial_root": check_path(paths["financial_root"]),
        "calendar_root": check_path(paths["calendar_root"], pattern="*.parquet"),
        "platform_reports": check_path(paths["platform_reports"]),
    }
    for statement in ("fina_indicator", "income", "balancesheet", "cashflow"):
        checks[f"financial_{statement}"] = check_path(paths["financial_root"] / statement)

    if args.check_snapshot:
        checks["snapshot_archive"] = check_path(
            PROJECT_ROOT / "data" / "local_recheck" / "factor-local-recheck-data.tar.gz"
        )
        checks["snapshot_manifest"] = check_path(
            PROJECT_ROOT / "research_reports" / "platform_alignment" / "local_recheck_data_manifest.json"
        )

    missing = []
    for name, check in checks.items():
        if not check["exists"]:
            missing.append(name)
        elif check.get("is_dir") and check.get("matching_files", 1) == 0:
            missing.append(name)
    result = {
        "status": "ok" if not missing else "missing_inputs",
        "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        "alignment_config": alignment_config_snapshot(),
        "cache_root": str(cache_root),
        "checks": checks,
        "missing": missing,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"alignment_rule_version={ALIGNMENT_RULE_VERSION}")
        print(f"cache_root={cache_root}")
        print(f"status={result['status']}")
        if missing:
            print("missing=" + ",".join(missing))
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
