import json, io, sys, math
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

def pct(s):
    if isinstance(s, (int, float)): return float(s)
    return float(str(s).replace("%", "").replace("+", ""))

def load(p):
    d = json.loads(Path(p).read_text(encoding="utf-8-sig"))
    fa = d.get("factor_analysis") or d.get("results", {}).get("factor_analysis")
    return d, fa

def summarize(label, path):
    d, fa = load(path)
    qa = fa["query_factor_analysis_data"]
    rows = qa["y"] if isinstance(qa, dict) and "y" in qa else qa
    kv = {}
    for r in rows:
        k = r.get("indicator")
        v = r.get("factor_value", r.get("factor1"))
        kv[k] = v
    g = fa["query_group_return_analysis"]
    gg = g["y"] if isinstance(g, dict) and "y" in g else g
    gr = {x["group"]: x for x in gg}
    long_name = "分组10"
    L = gr[long_name]
    long_ex = pct(L["excessAnnualized"]); turn = pct(L["turnoverRate"])
    cost = turn * 0.006 * 25.2
    net = long_ex - cost
    print("== %s ==" % label)
    print("  status=%s duration=%.1fs" % (d.get("status"), d.get("duration_seconds") or 0))
    print("  IC_mean=%s Rank_IC=%s IC_IR=%s 单调性=%s" % (kv.get("IC_mean"), kv.get("Rank_IC"), kv.get("IC_IR"), kv.get("单调性")))
    print("  %s: excessAnn=%+.2f%% turnover=%.2f%% -> cost=%.2f%% NET=%+.2f%%" % (long_name, long_ex, turn, cost, net))
    print("  多空组合: excessAnn=%s sharpe=%s" % (gr["多空组合"]["excessAnnualized"], gr["多空组合"]["sharpeRatio"]))
    print("  %s: sharpe=%s maxDD=%s monthlyWin=%s" % (long_name, L["sharpeRatio"], L["maxDrawdown"], L["monthlyWinRate"]))
    return dict(ic=kv.get("IC_mean"), rank_ic=kv.get("Rank_IC"), ic_ir=kv.get("IC_IR"),
                mono=kv.get("单调性"), long_ex=long_ex, turn=turn, cost=cost, net=net,
                sharpe=L["sharpeRatio"], maxdd=L["maxDrawdown"], win=L["monthlyWinRate"])

if __name__ == "__main__":
    for label, path in [(a.split("=")[0], a.split("=", 1)[1]) for a in sys.argv[1:]]:
        summarize(label, path)
