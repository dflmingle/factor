import json, re, sys
from pathlib import Path
import pandas as pd

ROOT = Path("/data/games/factor_")
PA = ROOT / "research_reports/platform_alignment"
OUT = Path("/tmp/factor_cluster_20260930")

# ---------- members ----------
clusters = pd.read_csv(PA / "all-factor-cluster-expansion-20260919.clusters.csv")
pairs = pd.read_csv(PA / "positive-factor-pair-correlation-20260917.pairs.csv")
obj = json.loads((PA / "all-factor-cluster-expansion-20260919.json").read_text(encoding="utf-8"))

fmap = {}
for _, r in pairs.iterrows():
    for side in ("a", "b"):
        n, f = r.get(f"factor_{side}_name"), r.get(f"factor_{side}_formula")
        if isinstance(n, str) and isinstance(f, str) and f.strip():
            fmap.setdefault(n, f.strip())
for arr in (obj["assignments"], obj["unresolved"]):
    for rec in arr:
        n, f = rec.get("factor_name"), rec.get("formula")
        if isinstance(n, str) and isinstance(f, str) and f.strip():
            fmap.setdefault(n, f.strip())

rows, missing = [], []
seen = set()
for _, r in clusters.iterrows():
    for name in str(r["member_names"]).split(";"):
        name = name.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        formula = fmap.get(name)
        rows.append({"name": name, "cluster": str(r["cluster"]).strip(), "formula": formula})
        if not formula:
            missing.append(name)
print("member entries:", len(rows), "missing formula:", missing)
members = pd.DataFrame(rows)

# ---------- rolling window / blocked fields ----------
sys.path.insert(0, str(ROOT / "scripts"))
import gp_candidates_vs_clusters_20260924 as M

BLOCK = ["ratio_ev_ebitda_ttm","oper_roa_net_ttm","residual_volatility","ratio_ev_ebitda_lyr",
         "ratio_ev_no_cash","ev_no_cash","oper_roe_adj_ttm","gr_revenue_ttm","gr_roe_ttm",
         "current_assets","current_liabilities","bs_total_cur_assets","bs_inventory","inventory",
         "cfs_fix_asset_depr","fixed_asset_depreciation","is_biz_tax_surchg","is_oth_affecting_tp",
         "is_total_profit","lease_liabilities","long_term_liabilities_due_one_year","sales_tax",
         "bs_accu_depr","bs_bond_payable","bs_fin_lease_payable","cfd_surplus_cash_multi_ttm",
         "deferred_expense_amortization","AS_FLOAT","BIAS(","RSI(","TS_ZSCORE(","beta(","literature","profitability"]
members["window"] = members["formula"].apply(lambda f: M.max_rolling_window(f) if isinstance(f, str) else -1)
members["blocked"] = members["formula"].apply(
    lambda f: next((b for b in BLOCK if isinstance(f, str) and b in f), "") if isinstance(f, str) else "noformula")
print(members.groupby("blocked").size())
members[members["blocked"].astype(bool)].to_csv(OUT / "members_excluded_preview.csv", index=False, encoding="utf-8")
ok = members[(~members["blocked"].astype(bool)) & (members["window"] <= 756)].copy()
print("members evaluable:", len(ok), "of", len(members))
print(ok.to_string(max_colwidth=90))

# ---------- candidates ----------
def norm(f):
    f = re.sub(r"\bSTD\(", "STDDEV(", f)
    f = re.sub(r"\bAlpha191_", "alpha191_", f)
    return f

cands = [
 ("VV6-1250",   "0-(STDDEV(VOLUME,6)/STDDEV(VOLUME,1250))"),
 ("VV6-756",    "0-(STDDEV(VOLUME,6)/STDDEV(VOLUME,756))"),
 ("VV6-500",    "0-(STDDEV(VOLUME,6)/STDDEV(VOLUME,500))"),
 ("LAMD10-K5V2","(RANK(0-(MA(AMOUNT,60))) + RANK(0-(MA((CLOSE-OPEN)/OPEN,20))) + RANK(0-(STDDEV(TURNOVER,20))) + RANK(MA(ABS(RETURNS(CLOSE,1))/AMOUNT,20)) + RANK(0-(STDDEV(VOLUME,6)/STDDEV(VOLUME,756)))) / 5"),
 ("LAMD0-K8V2", "(RANK(0-(STDDEV(VOLUME,6)/STDDEV(VOLUME,756))) + RANK(0-(MA((CLOSE-OPEN)/OPEN,20))) + RANK(0-(MA(AMOUNT,60))) + RANK(0-(CORR(HIGH,VOLUME,20))) + RANK(0-(RETURNS(CLOSE,5))) + RANK(0-(TS_MAX(RETURNS(CLOSE,1),20))) + RANK(MA(ABS(RETURNS(CLOSE,1))/AMOUNT,20)) + RANK(0-(MA(CLOSE*VOLUME/AMOUNT,20)))) / 8"),
 ("LAMD20-K5V2","(RANK(0-(MA(AMOUNT,60))) + RANK(0-(TURNOVER)) + RANK(MA(ABS(RETURNS(CLOSE,1))/AMOUNT,20)) + RANK(0-(MA((CLOSE-OPEN)/OPEN,20))) + RANK(0-(MA(CLOSE*VOLUME/AMOUNT,20)))) / 5"),
 ("a046-t10x750-w30",  "0.3*RANK(alpha191_046)+(0.7*(1-RANK(STDDEV(turnover,10)/STDDEV(turnover,750))))"),
 ("a046-t10x750-w30-rsm20", "0.3*RANK(alpha191_046)+(0.7*(1-RANK(MA(STDDEV(turnover,10)/STDDEV(turnover,750),20))))"),
 ("a046-t10x750-w20-rsm40", "0.2*RANK(alpha191_046)+(0.8*(1-RANK(MA(STDDEV(turnover,10)/STDDEV(turnover,750),40))))"),
 ("comp-pvcorr20-amihud20-vs500", "(0-(RANK(CORR(HIGH,VOLUME,20))) + RANK(MA(ABS(RETURNS(CLOSE,1))/AMOUNT,20)) + 0-(RANK(STDDEV(VOLUME,6)/STDDEV(VOLUME,500)))) / 3"),
 ("comp-amt60-vs500-retrev20",    "(0-(RANK(MA(AMOUNT,60))) + 0-(RANK(STDDEV(VOLUME,6)/STDDEV(VOLUME,500))) + 0-(RANK(RETURNS(CLOSE,20)))) / 3"),
 ("comp-amihud20-vs500",          "(RANK(MA(ABS(RETURNS(CLOSE,1))/AMOUNT,20)) + 0-(RANK(STDDEV(VOLUME,6)/STDDEV(VOLUME,500)))) / 2"),
 ("V4R01",  "TsMax(TsMax(cal_12d_vol_ma,20),10)"),
 ("V5-V01", "Greater(Greater(vol10,Log(TsWMA(TsWMA(cal_20d_amt_ma,30),30))),Log(cal_20d_amt_ma))"),
 ("V6-V01", "TsEMA(TsStd(mcst,10),40)"),
 ("V7-V01", "TsSum(cal_10d_vol_std,50)"),
]
cand = pd.DataFrame(cands, columns=["label", "formula"])
cand["formula"] = cand["formula"].apply(norm)
cand["window"] = cand["formula"].apply(M.max_rolling_window)
print(cand.to_string(max_colwidth=80))

bad = []
from pathlib import Path as P
info = []
nf = pd.DataFrame({
    "band": cand["label"], "formula": cand["formula"],
    "net": float("nan"), "turnover": float("nan"), "net_y2026": float("nan"),
    "s_i_rank": float("nan"), "corr_size": float("nan"), "corr_max_seat": float("nan"),
    "corr_max_seat_name": "", "delta_points": float("nan"),
})
nf.to_csv(OUT / "nf_candidates.csv", index=False, encoding="utf-8")
ok[["name", "formula"]].rename(columns={"name": "factor_a_name", "formula": "factor_a_formula"}).to_csv(
    OUT / "members77.csv", index=False, encoding="utf-8")
print("wrote nf_candidates.csv", len(nf), "members77.csv", len(ok))
