import json, sys, os
from pathlib import Path
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")

RUNS = [
 ("ours: T10-ADD-BM", r"t10-additions-20260911-candidates.results\6aa3c6d25d52c44d2f55c45b.json"),
 ("ours: VERIFY10-F", r"verify-field-scan-cycle10-20260910-candidates.results\6aa28e56a7f535324660b838.json"),
 ("ours: VERIFY10-E", r"verify-field-scan-cycle10-20260910-candidates.results\6aa28e0a5d52c44d2f55c2da.json"),
 ("ours: H03-T10",    r"h03-t10-single-20260911-candidates.results\6aa36bd3ecb163ea7228cffe.json"),
 ("ours: SIZE-ONLY",  r"size-only-20260911-candidates.results\6aa3b8576df2a192a47e7cfe.json"),
 ("cand: AGG",        r"t10-more-additions-20260911-candidates.results\6aa3ca1451cdfe29b2e0bce4.json"),
 ("cand: DOWNSIDE",   r"t10-more-additions-20260911-candidates.results\6aa3c9208b01f62dc5146090.json"),
 ("cand: G13",        r"t10-additions-20260911-candidates.results\6aa3c61451cdfe29b2e0bcdd.json"),
 ("cand: WC",         r"t10-newdirections-20260911-candidates.results\6aa3690a6df2a192a47e7c60.json"),
]

def stats(dates, series, lo=None, hi=None):
    m = np.isfinite(series)
    if lo is not None:
        m &= (dates >= lo)
    if hi is not None:
        m &= (dates <= hi)
    s = series[m]
    if s.size < 4:
        return None
    mean = float(s.mean()); std = float(s.std(ddof=1))
    sign = 1.0 if mean >= 0 else -1.0
    win = float(np.mean(s * sign > 0.02))
    ir = abs(mean) / std if std > 0 else float("nan")
    return dict(n=int(s.size), ic=abs(mean), ir=ir, win=win, s_i=abs(mean) * ir * win)

for label, rel in RUNS:
    p = Path(r"D:\factor") / rel
    d = json.loads(p.read_text(encoding="utf-8-sig"))
    res = d.get("results", d)
    fa = res.get("factor_analysis", {})
    ch = fa.get("query_rank_ic_sequence_chart", {})
    xs = ch.get("x") or []
    dates = None
    for e in xs:
        if str(e.get("name", "")).lower() == "date":
            dates = np.array([np.datetime64(str(v)) for v in e.get("data") or []])
    series = None
    for e in ch.get("y") or []:
        if str(e.get("name", "")).lower().replace(" ", "_") in ("rank_ic", "rankic"):
            series = np.array([np.nan if v is None else float(v) for v in e.get("data") or []])
    assert dates is not None and series is not None, rel
    end = dates[np.isfinite(series)].max()
    y1 = stats(dates, series, lo=end - np.timedelta64(365, "D"), hi=end)
    m3 = stats(dates, series, lo=end - np.timedelta64(91, "D"), hi=end)
    full = stats(dates, series)
    fmt = lambda st: ("n=%3d ic=%+.4f ir=%+.3f win=%.3f s_i=%.5f" % (st["n"], st["ic"], st["ir"], st["win"], st["s_i"])) if st else "n/a"
    print("%-18s end=%s | 5y %s | 1y %s | 3m %s" % (
        label, str(end), fmt(full), fmt(y1), fmt(m3)))
