import json, sys, os
from pathlib import Path
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"D:\factor")
SKIP = {".git", "node_modules", ".venv", "__pycache__", "quantlab", "tests"}

def walk():
    for p in ROOT.rglob("*.json"):
        if any(part in SKIP for part in p.parts):
            continue
        try:
            if p.stat().st_size > 8_000_000:
                continue
        except OSError:
            continue
        yield p

def stats(dates, series, days=None):
    m = np.isfinite(series)
    if days is not None and dates is not None:
        end = dates[m].max()
        m = m & (dates >= end - np.timedelta64(days, "D"))
    s = series[m]
    if s.size < 4:
        return None
    mean = float(s.mean()); std = float(s.std(ddof=1))
    sign = 1.0 if mean >= 0 else -1.0
    win = float(np.mean(s * sign > 0.02))
    ir = abs(mean) / std if std > 0 else float("nan")
    return dict(n=int(s.size), ic=abs(mean), ir=ir, win=win, s_i=abs(mean) * ir * win)

rows = []
for p in walk():
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        continue
    if not isinstance(d, dict):
        continue
    res = d.get("results", d)
    if not isinstance(res, dict):
        continue
    fa = res.get("factor_analysis")
    if not isinstance(fa, dict):
        continue
    ch = fa.get("query_rank_ic_sequence_chart") or {}
    dates = None
    for e in ch.get("x") or []:
        if str(e.get("name", "")).lower() == "date":
            try:
                dates = np.array([np.datetime64(str(v)) for v in e.get("data") or []])
            except Exception:
                dates = None
    series = None
    for e in ch.get("y") or []:
        if str(e.get("name", "")).lower().replace(" ", "_") in ("rank_ic", "rankic"):
            series = np.array([np.nan if v is None else float(v) for v in e.get("data") or []])
    if series is None or series.size < 12:
        continue
    full = stats(dates, series)
    y1 = stats(dates, series, 365)
    m3 = stats(dates, series, 91)
    if full is None or full["n"] < 100:
        continue
    rel = str(p.relative_to(ROOT))
    rows.append((full, y1, m3, rel))

print("runs with 5y-like series:", len(rows))
rows_sorted = sorted(rows, key=lambda r: -(r[1]["s_i"] if r[1] else -1))
print()
print("== TOP 25 by 1y s_i (n>=100 runs) ==")
print("%-6s %-6s %-6s | %-6s %-6s %-6s | %s" % ("5y_si", "1y_si", "3m_si", "5y_ic", "1y_ic", "1y_n", "run"))
for full, y1, m3, rel in rows_sorted[:25]:
    print("%-6.4f %-6.4f %-6.4f | %-6.4f %-6.4f %-6d | %s" % (
        full["s_i"], y1["s_i"] if y1 else float("nan"), m3["s_i"] if m3 else float("nan"),
        full["ic"], y1["ic"] if y1 else float("nan"), y1["n"] if y1 else 0, rel[:96]))
print()
print("== TOP 15 by 5y s_i ==")
rows_sorted5 = sorted(rows, key=lambda r: -r[0]["s_i"])
for full, y1, m3, rel in rows_sorted5[:15]:
    print("%-6.4f %-6.4f %-6.4f | %s" % (full["s_i"], y1["s_i"] if y1 else float("nan"),
                                          m3["s_i"] if m3 else float("nan"), rel[:96]))
