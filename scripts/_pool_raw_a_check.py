import io, json, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path("D:/factor")
RUNS = {
    "base5": ROOT / "pool-candCD-20260922-candidates.results/6ab254c08b01f62dc5147d3a.json",
    "t2_six": ROOT / "platform_pool_tests_20260926/pool6-t2t4-v2-20260926-candidates.results/6ab75e8fcd820fa2a40a6cbe.json",
    "agg_0924": ROOT / "platform_pool_tests_20260924/agg.run.json",
}
for label, path in RUNS.items():
    payload = json.loads(path.read_text(encoding="utf-8"))
    fa = payload["results"]["factor_analysis"]
    ind = {row["indicator"]: row["factor_value"] for row in fa["query_factor_analysis_data"]}
    print(f"== {label}")
    for k, v in ind.items():
        print(f"   {k:16s} {v}")
    try:
        rank_ic = float(ind["Rank_IC"]); ic_ir = float(ind["IC_IR"])
        win = float(ind["P(IC>0.02)"])
        raw_a = rank_ic * ic_ir * win
        print(f"   -> raw_a = RankIC*IC_IR*P(IC>0.02) = {rank_ic}*{ic_ir}*{win} = {raw_a:.6f} "
              f"NA={min(raw_a/0.08,0.7):.4f}")
    except Exception as exc:
        print("   raw_a calc failed:", exc)