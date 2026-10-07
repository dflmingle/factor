# -*- coding: utf-8 -*-
"""Tolerant batch runner (2026-10-05).

The bundled batch.py crashes in extract() when a completed python-mode pool run
returns `query_factor_analysis_data = null` on the factor_analysis node while the
real indicators sit on the result_json node (observed on POOL5-REBUILD-L2C).
That crash happens AFTER the run is billed, so it loses the metrics but not the
credits.  This wrapper patches extract() to backfill the indicators from the
result_json node, then delegates to the bundled main().
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "vendor" / "skill-pandaai-factor-online" / "scripts"
sys.path.insert(0, str(SKILL))

import batch  # noqa: E402

_ORIG = batch.extract


def _result_json_lists(payload: dict):
    for node in ((payload.get("results") or {}).get("nodes") or {}).values():
        raw = node.get("result_json") if isinstance(node, dict) else None
        if not isinstance(raw, str):
            continue
        try:
            nested = json.loads(raw)
        except ValueError:
            continue
        if nested.get("factor_data_analysis") and nested.get("group_return_analysis"):
            return nested["factor_data_analysis"], nested["group_return_analysis"]
    return None, None


def extract(payload, direction, group_number=None):
    fa = payload.get("factor_analysis") or (payload.get("results") or {}).get("factor_analysis")
    if isinstance(fa, dict) and fa.get("query_factor_analysis_data") is None:
        fda, gra = _result_json_lists(payload)
        if fda is not None:
            fa["query_factor_analysis_data"] = fda
            if fa.get("query_group_return_analysis") is None:
                fa["query_group_return_analysis"] = gra
            print("[tolerant] backfilled query_factor_analysis_data from result_json node",
                  file=sys.stderr)
    return _ORIG(payload, direction, group_number)


batch.extract = extract

if __name__ == "__main__":
    raise SystemExit(batch.main())