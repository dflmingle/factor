#!/usr/bin/env python3
"""方向 1 后验：在原始面板净额记录上，按 |corr_size| 切档，量"无 size 净额天花板"。

输入：GP run 目录下的 aligned_ic_records.json（每条含 net_excess / turnover / corr_size）。
输出：research_reports/platform_alignment/sizecap-gp-20261009/frontier.csv + frontier.md
零平台算力。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / ("quantlab/.quantlab/cache/research/cn_equity/reports/alphaprobe_gp_tushare/"
              "sizecap_net_s911_20261009/aligned_ic_records.json")
OUT = ROOT / "research_reports/platform_alignment/sizecap-gp-20261009"
BANDS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1.01]


def main() -> int:
    records = json.loads(RUN.read_text(encoding="utf-8"))
    rows = []
    for r in records:
        net, corr, turn = r.get("net_excess"), r.get("corr_size"), r.get("turnover")
        if net is None or corr is None or turn is None:
            continue
        if not all(isinstance(v, (int, float)) for v in (net, corr, turn)):
            continue
        rows.append({"formula": r["formula"], "net": float(net), "corr_size": float(corr),
                     "turnover": float(turn), "periods": r.get("periods"),
                     "gross": r.get("gross_excess")})
    print(f"records={len(records)} with_corr&net={len(rows)}")
    OUT.mkdir(parents=True, exist_ok=True)
    lines = ["# 无 size 净额天花板（方向 1，2026-10-09）", "",
             f"记录数 {len(records)}（可用 {len(rows)}）；窗口 2021-09-07..2026-09-07，cycle 10，120 信号日。", "",
             "| `|corr_size|` 档 | 记录数 | 最好净额 | 对应换手 | 次好 | 中位净额 | 净额>0 占比 |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for band in BANDS:
        sub = [x for x in rows if abs(x["corr_size"]) <= band]
        if not sub:
            lines.append(f"| ≤{band:.2f} | 0 | — | — | — | — | — |")
            continue
        sub.sort(key=lambda x: -x["net"])
        med = sorted(x["net"] for x in sub)[len(sub) // 2]
        pos = sum(1 for x in sub if x["net"] > 0) / len(sub)
        lines.append(
            f"| ≤{band:.2f} | {len(sub)} | **{sub[0]['net']*100:+.2f}%** | {sub[0]['turnover']:.3f} | "
            f"{sub[1]['net']*100:+.2f}% | {med*100:+.2f}% | {pos*100:.0f}% |")
    best = [x for x in rows if abs(x["corr_size"]) <= 0.30]
    best.sort(key=lambda x: -x["net"])
    lines += ["", "## `|corr_size| ≤ 0.30` 前 10 条", "",
              "| # | 净额 | 换手 | corr_size | 毛超额 | 公式 |", "| ---: | ---: | ---: | ---: | ---: | --- |"]
    for i, x in enumerate(best[:10], 1):
        f = x["formula"] if len(x["formula"]) <= 150 else x["formula"][:150] + "…"
        lines.append(f"| {i} | {x['net']*100:+.2f}% | {x['turnover']:.3f} | {x['corr_size']:+.3f} | "
                     f"{(x['gross'] or 0)*100:+.1f}% | `{f}` |")
    (OUT / "frontier.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    import csv
    with (OUT / "records_with_corr.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["formula", "net", "corr_size", "turnover", "gross", "periods"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda x: -x["net"]))
    print("\n".join(lines[:16]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
