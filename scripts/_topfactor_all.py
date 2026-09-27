import io, sys, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
base = Path(r"D:\factor\research_reports\platform_alignment\gp-platform-tests-20260925")
runs = {
 "K008 (round1, ok)":      r"candidates_panda.results\6ab636d745ce44aed9d15615.json",
 "K021 unscaled (r3, degenerate)": r"round3\candidates_panda.results\6ab66330812a2a13b9644c76.json",
 "K021 x1e18 (r4, ok)":    r"round4\candidates_panda.results\6ab665922d2f6998fc1bf75d.json",
 "K015 x1e24 (r5, ok)":    r"round5\candidates_panda.results\6ab667df9e9d797cfb2cf769.json",
 "K020 x1e27 d1 (r5)":     r"round5\candidates_panda.results\6ab66841a8ba1ed343bf7e04.json",
 "K020 x1e27 d0 (r6b, ok)":r"round6b\candidates_panda.results\6ab66f9e9e9d797cfb2cf776.json",
 "PROBE B/M (r7)":         r"round7\candidates_panda.results\6ab6745845ce44aed9d15652.json",
 "PROBE corr30 (r7b)":     r"round7b\candidates_panda.results\6ab6777b812a2a13b9644c7b.json",
}
for tag, rel in runs.items():
    p = base / rel
    if not p.exists():
        print(f"{tag:34s} MISSING"); continue
    raw = json.loads(p.read_text(encoding="utf-8"))
    fa = (raw.get("results") or {}).get("factor_analysis") or {}
    lst = fa.get("query_last_date_top_factor") or []
    vals = [x.get("factor1") for x in lst]
    uniq = len(set(vals))
    print(f"{tag:34s} n={len(vals):3d} distinct={uniq:3d} sample={vals[:3]}")
