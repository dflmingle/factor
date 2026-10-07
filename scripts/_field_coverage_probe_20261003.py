# -*- coding: utf-8 -*-
"""字段覆盖侦察探针（2026-10-03，零平台算力）。

目的：用当前版 pandaai_fields_local（348 formula + 1048 catalog）对本地
Tushare 快照做一次完整可物化性盘点，并与历史公式登记表（51,783 条签名）/
field_checklist / 失败登记表交叉，输出"本地可物化且从未挖过"的字段族清单。

status() 只检查"来源列是否存在"，因此用列名 stub frame + stub data 即可，不需要
物化任何真实面板（数值挖掘留给下一步的腿库）。

输出目录：research_reports/platform_alignment/field-recon-20261003/
  - field_coverage.csv   （1396 个声明字段 × status × 家族 × 历史接触）
  - family_summary.csv   （家族汇总：可物化/未接触计数）
  - probe_meta.json
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(r"D:\factor")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "quantlab" / "third_party" / "AlphaPROBE" / "src"))

import pandaai_fields_local as f  # noqa: E402

FIN_ROOT = ROOT / "quantlab" / ".quantlab" / "cache" / "research" / "cn_equity" / "financial_full_a"
REGISTRY = ROOT / "research_reports" / "platform_alignment" / "factor_formula_registry.json"
CHECKLIST = ROOT / "research_reports" / "platform_alignment" / "field-coverage-20260923" / "field_checklist.csv"
FAILURE = ROOT / "research_reports" / "platform_alignment" / "factor_alignment_failure_registry.json"
OUT = ROOT / "research_reports" / "platform_alignment" / "field-recon-20261003"

DAILY_COLUMNS = ["open", "close", "high", "low", "volume", "amount", "turnover",
                 "total_mv", "circ_mv", "open_qfq", "close_qfq", "high_qfq", "low_qfq"]


class _StubData:
    """Minimal adapter surface used by PandaAIFieldStore.__init__."""


def build_store() -> f.PandaAIFieldStore:
    stub = _StubData()
    dates = list(pd.bdate_range("2025-01-02", periods=20))
    stub._pre_dates = dates[:5]
    stub._evaluation_dates = dates[5:15]
    stub._post_dates = dates[15:]
    stub._pre_padding = 0
    stub.n_stocks = 3
    stub._stock_ids = ["000001.SZ", "000002.SZ", "000003.SZ"]
    stub.data = torch.zeros((len(dates) + 4, 5, 3), dtype=torch.float32)
    frame = pd.DataFrame({
        "date": np.repeat(dates[:3], 3),
        "instrument": ["000001.SZ", "000002.SZ", "000003.SZ"] * 3,
        **{column: 1.0 for column in DAILY_COLUMNS},
    })
    return f.PandaAIFieldStore(data=stub, frame=frame, financial_root=FIN_ROOT,
                               max_cached_fields=2, max_cached_arrays=2)


TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def registry_token_counts() -> Counter:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    counts: Counter = Counter()
    for entry in payload["formulas"]:
        text = entry.get("representative_formula") or ""
        for token in TOKEN.findall(text):
            counts[token.lower()] += 1
    return counts


def checklist_flags() -> dict[str, bool]:
    flags: dict[str, bool] = {}
    if not CHECKLIST.exists():
        return flags
    for row in csv.DictReader(CHECKLIST.open(encoding="utf-8-sig", newline="")):
        name = (row.get("field") or "").strip().lower()
        if name:
            flags[name] = (row.get("tested_platform") or "").strip() == "platform"
    return flags


def failure_flags() -> tuple[set, set]:
    payload = json.loads(FAILURE.read_text(encoding="utf-8"))
    blocked = {str(item.get("field")).lower() for item in payload.get("field_risks") or []
               if item.get("decision") == "blocked"}
    suspect = {str(item.get("field")).lower() for item in payload.get("field_risks") or []
               if item.get("decision") == "suspect"}
    return blocked, suspect


def main() -> int:
    store = build_store()
    counts = registry_token_counts()
    tested_platform = checklist_flags()
    blocked, suspect = failure_flags()

    variant_names: dict[str, set] = {}
    for name in f.formula_field_name_set():
        base, _ = f.split_formula_field_name(name)
        variant_names.setdefault(base, set()).add(name)

    rows = []
    for name in f.PLATFORM_DECLARED_FIELD_NAMES:
        status = store.status(name)
        base = status["base_field"]
        hits = sum(counts.get(v, 0) for v in variant_names.get(base, {name}))
        source_file = f.PLATFORM_FIELD_SOURCE_FILES.get(base, "fields.md")
        category = status.get("category") or f.PLATFORM_FIELD_CATEGORIES.get(base, "")
        rows.append({
            "field": base,
            "category": category,
            "source_file": source_file,
            "status": status["status"],
            "source": status["source"],
            "note": status["note"],
            "registry_hits": hits,
            "tested_platform": bool(tested_platform.get(base, False)),
            "blocked": base in blocked,
            "suspect": base in suspect,
        })

    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "field_coverage.csv", index=False, encoding="utf-8-sig")

    family = []
    for (cat, src), group in frame.groupby(["category", "source_file"]):
        family.append({
            "family": cat,
            "source_file": src,
            "declared": len(group),
            "available": int((group["status"] != "unavailable").sum()),
            "local_direct": int((group["status"] == "local_direct").sum()),
            "local_proxy": int((group["status"] == "local_proxy").sum()),
            "local_derived": int((group["status"] == "local_derived").sum()),
            "unavailable": int((group["status"] == "unavailable").sum()),
            "touched_registry": int((group["registry_hits"] > 0).sum()),
            "tested_platform": int(group["tested_platform"].sum()),
            "fresh_available": int(((group["status"] != "unavailable") & (group["registry_hits"] == 0)).sum()),
            "blocked": int(group["blocked"].sum()),
            "suspect": int(group["suspect"].sum()),
        })
    summary = pd.DataFrame(family).sort_values(["available", "declared"], ascending=False)
    summary.to_csv(OUT / "family_summary.csv", index=False, encoding="utf-8-sig")

    meta = {
        "reference": str(f.DEFAULT_REFERENCE),
        "formula_base_fields": len(f.PLATFORM_FIELD_NAMES),
        "catalog_fields": len(f.PLATFORM_CATALOG_FIELD_NAMES),
        "declared_fields": len(f.PLATFORM_DECLARED_FIELD_NAMES),
        "formula_names_with_periods": len(f.formula_field_name_set()),
        "status_counts": dict(Counter(frame["status"])),
        "registry_entries": json.loads(REGISTRY.read_text(encoding="utf-8"))["summary"],
    }
    (OUT / "probe_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== status counts (declared 1396) ===")
    print(frame["status"].value_counts().to_string())
    print()
    print("=== family summary ===")
    print(summary.to_string(index=False))
    print()
    fresh = frame[(frame["status"] != "unavailable") & (frame["registry_hits"] == 0)]
    print(f"=== fresh available (local-usable & never in any formula): {len(fresh)} ===")
    for cat, group in fresh.groupby("category"):
        names = ", ".join(group["field"].tolist()[:18])
        more = "" if len(group) <= 18 else f" ... (+{len(group) - 18})"
        print(f"[{cat}] {len(group)}: {names}{more}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
