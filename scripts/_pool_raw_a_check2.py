import io, json, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path("D:/factor")
RUNS = {
    "base5": ROOT / "pool-candCD-20260922-candidates.results/6ab254c08b01f62dc5147d3a.json",
    "t2_six": ROOT / "platform_pool_tests_20260926/pool6-t2t4-v2-20260926-candidates.results/6ab75e8fcd820fa2a40a6cbe.json",
    "t4_six": ROOT / "platform_pool_tests_20260926/pool6-t4v6-20260926-candidates.results/6ab769dd6ee632ca3f97b59d.json",
}
rows = {}
for label, path in RUNS.items():
    fa = json.loads(path.read_text(encoding="utf-8"))["results"]["factor_analysis"]
    ind = {r["indicator"]: r["factor_value"] for r in fa["query_factor_analysis_data"]}
    def num(text):
        return float(str(text).rstrip("%")) / (100.0 if str(text).endswith("%") else 1.0)
    rank_ic, ic_ir = num(ind["Rank_IC"]), num(ind["IC_IR"])
    win = num(ind["P(IC>0.02)"])
    raw_a = rank_ic * ic_ir * win
    rows[label] = dict(rank_ic=rank_ic, ic_ir=ic_ir, win=win, raw_a=raw_a, na=min(raw_a / 0.08, 0.70))
    row = next(r for r in fa["query_group_return_analysis"] if r["group"] == "分组10")
    print(f"{label:8s} RankIC={rank_ic:.4f} IC_IR={ic_ir:.4f} P(IC>0.02)={win*100:6.2f}%  "
          f"raw_a={raw_a:.5f} NA={rows[label]['na']:.4f}  "
          f"gross={row['excessAnnualized']:>7s} turn={row['turnoverRate']:>7s} "
          f"sharpe={row['sharpeRatio']:>7s} dd={row['maxDrawdown']:>7s}")
base = rows["base5"]
for key in ("t2_six", "t4_six"):
    d = rows[key]
    print(f"  Δ vs base5 [{key}]: Δraw_a={d['raw_a']-base['raw_a']:+.5f} ΔNA={d['na']-base['na']:+.4f} "
          f"-> A 项 {(d['na']-base['na'])*0.20*44000:+.0f} 分/月")