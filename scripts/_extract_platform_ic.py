import json, io, sys, glob
import numpy as np
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
files = {
 "AGG(0924)": r"D:\factor\platform_pool_tests_20260924\agg.run.json",
 "G13(0924)": r"D:\factor\platform_pool_tests_20260924\g13.run.json",
 "DOWNSIDE(0924)": r"D:\factor\platform_pool_tests_20260924\downside.run.json",
 "WC(0924)": r"D:\factor\platform_pool_tests_20260924\wc.run.json",
 "T2(0926)": r"D:\factor\platform_pool_tests_20260926\pool6-t2t4-v2-20260926-candidates.results\6ab75e8fcd820fa2a40a6cbe.json",
 "T4(0926)": r"D:\factor\platform_pool_tests_20260926\pool6-t4v6-20260926-candidates.results\6ab769dd6ee632ca3f97b59d.json",
}
for name, f in files.items():
    d = json.load(open(f, encoding="utf-8"))
    r = d.get("results") or d
    fa = r.get("factor_analysis")
    if fa is None:
        print(name, "no factor_analysis; keys:", list(d.keys())); continue
    inds = {row["indicator"]: row["factor_value"] for row in fa["query_factor_analysis_data"]}
    seq = None
    for chart in ("query_rank_ic_sequence_chart",):
        data = fa.get(chart, {}).get("y", [])
        for series in data:
            if series.get("name") in ("Rank_IC", "rank_ic"):
                seq = np.asarray(series["data"], dtype=float)
    if seq is None and fa.get("query_rank_ic_sequence_chart"):
        seq = np.asarray(fa["query_rank_ic_sequence_chart"]["y"][0]["data"], dtype=float)
    print("==", name)
    print("   indicators:", json.dumps(inds, ensure_ascii=False))
    if seq is not None:
        s = seq[np.isfinite(seq)]
        print("   seq n=%d mean=%.4f std=%.4f IR=%.4f P(>0.02)=%.4f  P(<-0.02)=%.4f" % (
            len(s), s.mean(), s.std(ddof=1), s.mean()/s.std(ddof=1), (s > 0.02).mean(), (s < -0.02).mean()))
