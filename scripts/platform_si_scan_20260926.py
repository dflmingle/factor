"""Scan every platform run JSON in the repo and recompute the arena s_i under the VERIFIED rule.

s_i = |RankIC_mean| * IR(RankIC series) * P(RankIC > +0.02, hard count)
RankIC series comes from query_rank_ic_sequence_chart; IR = mean/std(ddof=1) of that series.

Zero platform compute: reads only local artifacts.
"""
from __future__ import annotations
import io, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor")
OUT = ROOT / "research_reports/platform_alignment/a-basis-correction-20260926"
OUT.mkdir(parents=True, exist_ok=True)

SKIP = {".git", "node_modules", ".venv", "__pycache__", "quantlab"}

def iter_json(root: Path):
    for path in root.rglob("*.json"):
        if any(part in SKIP for part in path.parts):
            continue
        if path.stat().st_size > 8_000_000:
            continue
        yield path

def extract(path: Path):
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    results = payload.get("results") if isinstance(payload.get("results"), dict) else payload
    if not isinstance(results, dict):
        return None
    analysis = results.get("factor_analysis")
    if not isinstance(analysis, dict):
        return None
    indicators = {}
    for row in analysis.get("query_factor_analysis_data") or []:
        if isinstance(row, dict) and "indicator" in row:
            indicators[str(row["indicator"])] = row.get("factor_value")
    chart = analysis.get("query_rank_ic_sequence_chart") or {}
    series = None
    for entry in chart.get("y") or []:
        name = str(entry.get("name", ""))
        if name.lower().replace(" ", "_") in ("rank_ic", "rankic"):
            series = np.asarray([np.nan if v is None else float(v) for v in entry.get("data") or []], dtype=float)
            break
    if series is None:
        return None
    finite = series[np.isfinite(series)]
    if finite.size < 10:
        return None
    mean = float(finite.mean())
    std = float(finite.std(ddof=1))
    ir = mean / std if std > 0 else float("nan")
    # SCORE_RULES: the win rate is a hard count of the *sign-aligned* RankIC > +0.02,
    # and it is not flipped by `direction` on its own - align by sign(mean) first.
    aligned = finite if mean >= 0 else -finite
    win = float((aligned > 0.02).mean())
    win_raw = float((finite > 0.02).mean())
    si = abs(mean) * abs(ir) * win
    return dict(path=str(path.relative_to(ROOT)), n_periods=int(finite.size), rank_ic=mean,
                rank_ic_ir=ir, win=win, win_raw=win_raw, s_i=si, indicators=indicators,
                reported_rank_ic=_num(indicators.get("Rank_IC")),
                reported_ic_ir=_num(indicators.get("IC_IR")),
                reported_p_ic=_num(indicators.get("P(IC>0.02)")),
                reported_win_series=win)

def _num(v):
    if v is None:
        return None
    try:
        return float(str(v).replace("%", "")) / (100.0 if str(v).endswith("%") else 1.0)
    except Exception:
        return None

def main() -> int:
    rows = []
    for path in iter_json(ROOT):
        item = extract(path)
        if item:
            rows.append(item)
    frame = pd.DataFrame([{k: v for k, v in row.items() if k != "indicators"} for row in rows])
    frame = frame.sort_values("s_i", ascending=False, ignore_index=True)
    frame.to_csv(OUT / "platform_si_scan.csv", index=False, encoding="utf-8-sig")
    with (OUT / "platform_si_scan.json").open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=1, default=str)
    print(f"scanned {len(frame)} runs with a RankIC sequence")
    show = ["path", "n_periods", "rank_ic", "rank_ic_ir", "win", "s_i"]
    with pd.option_context("display.width", 220, "display.max_colwidth", 95):
        print(frame[show].head(25).to_string(index=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
