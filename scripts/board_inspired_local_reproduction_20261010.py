#!/usr/bin/env python3
"""Local reproduction of the three board-inspired hypotheses.

Uses the current full-A/qfq/total_mv cache and the shared alignment evaluator;
no PandaAI calls and no platform compute are used.
"""
from __future__ import annotations
import gc, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from full_a_local_data import load_full_a_data, select_market_cap
from positive_factor_local_compare import (
    compact_full_a_frame, evaluate, panel_close, cross_rank, rolling_time_series_rank,
)
from qtld60_local_reproduction import load_calendar
from platform_alignment_rules import (
    ALIGNMENT_DATA_START, ALIGNMENT_START, ALIGNMENT_END, ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_MARKET_CAP_FIELD, ALIGNMENT_ROUND_TRIP_COST, ALIGNMENT_RULE_VERSION,
)

DATA_START = pd.Timestamp(ALIGNMENT_DATA_START)
FORMAL_START = pd.Timestamp(ALIGNMENT_START)
FORMAL_END = pd.Timestamp(ALIGNMENT_END)
RECENT_START = pd.Timestamp("20260101")
CYCLE = 10
PRICE_ROOT = ROOT / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches"
CAP_ROOT = ROOT / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/daily_basic_full_a"
CAL_ROOT = ROOT / "quantlab/.quantlab/cache/research/cn_equity/trade_calendar"
OUT = ROOT / "research_reports/platform_alignment/board-inspired-local-reproduction-20261010"

def generated_dates(calendar, start, end):
    pos = {d:i for i,d in enumerate(calendar)}
    anchor = pos[FORMAL_START]
    return [calendar[i] for i in range(anchor, len(calendar), CYCLE)
            if start <= calendar[i] <= end and i + ALIGNMENT_LABEL_OFFSET + CYCLE < len(calendar)]

def grouped_roll(frame, values, window, method="mean", min_periods=None):
    x = frame[["instrument"]].copy(); x["v"] = pd.to_numeric(values, errors="coerce")
    g = x.groupby("instrument", sort=False, observed=True)["v"]
    r = getattr(g.rolling(window=window, min_periods=min_periods or window), method)()
    return r.reset_index(level=0, drop=True).reindex(frame.index)

def grouped_corr(frame, xval, yval, window):
    x = frame[["instrument"]].copy(); x["x"] = xval.to_numpy(); x["y"] = yval.to_numpy()
    # pandas rolling corr on each instrument, aligned back to original rows
    out = pd.Series(np.nan, index=frame.index, dtype=float)
    for _, idx in x.groupby("instrument", sort=False, observed=True).groups.items():
        z = x.loc[idx].sort_index()
        out.loc[idx] = z["x"].rolling(window, min_periods=window).corr(z["y"]).to_numpy()
    return out

def build_factors(frame):
    close = frame["close_qfq"].astype(float)
    high = frame["high_qfq"].astype(float); low = frame["low_qfq"].astype(float)
    amount = frame["amount"].astype(float); turnover = frame["turnover"].astype(float)
    ret1 = close.groupby(frame["instrument"], sort=False).pct_change(fill_method=None)
    ret20 = close.groupby(frame["instrument"], sort=False).pct_change(20, fill_method=None)
    down_amt = amount.where(ret1 < 0, 0.0)
    down_share = grouped_roll(frame, down_amt, 20, "mean") / (grouped_roll(frame, amount, 20, "mean") + 1.0)
    rel_amt = grouped_roll(frame, amount, 5, "mean") / (grouped_roll(frame, amount, 60, "mean") + 1.0)
    f1 = cross_rank(-ret20, frame["date"]) * cross_rank(1.0-down_share, frame["date"]) * cross_rank(1.0-rel_amt, frame["date"])
    amplitude = (high-low) / close.replace(0, np.nan)
    amp_rank = rolling_time_series_rank(frame, amplitude, 60)
    mask = amp_rank > .7
    high_amp_ret = ret1.where(mask, 0.0)
    high_amp_n = mask.astype(float).groupby(frame["instrument"], sort=False).rolling(20, min_periods=20).sum().reset_index(level=0, drop=True).reindex(frame.index)
    high_amp_sum = high_amp_ret.groupby(frame["instrument"], sort=False).rolling(20, min_periods=20).sum().reset_index(level=0, drop=True).reindex(frame.index)
    f2 = -high_amp_sum / (high_amp_n + 1.0)
    corr60 = grouped_corr(frame, ret1, turnover, 60)
    corr10 = grouped_corr(frame, ret1, turnover, 10)
    f3 = cross_rank(-ret20, frame["date"]) * cross_rank(corr60-corr10, frame["date"])
    return {"F-BI1010-01": f1, "F-BI1010-02": f2, "F-BI1010-03": f3, "CTRL-REV20": -ret20, "CTRL-REV20-RELAMT": cross_rank(-ret20,frame["date"])*cross_rank(1-rel_amt,frame["date"]), "CTRL-LOWAMP-REV": -grouped_roll(frame,ret1.where(amp_rank<=.7,0),20,"sum")/(grouped_roll(frame,(amp_rank<=.7).astype(float),20,"sum")+1), "CTRL-SHORTCORR": cross_rank(-ret20,frame["date"])*cross_rank(-corr10,frame["date"])}

def corr_to_clusters(factors, frame, signal_dates):
    from scipy.stats import rankdata
    root = ROOT / "research_reports/platform_alignment/recent-factor-clusters-20261010-average-rank-v2"
    refs = pd.read_csv(root / "references.csv")
    u = pd.read_csv(root / "new_unanchored_clusters.csv").rename(columns={"new_cluster":"cluster"})
    refs = pd.concat([refs,u[["name","formula","cluster","panel_id"]]],ignore_index=True)
    meta = json.loads((root/"metadata.json").read_text())
    dates = pd.to_datetime(meta["signal_dates"])
    stocks = meta["stock_ids"]
    rows=[]
    for name, vals in factors.items():
        if name.startswith("CTRL"): continue
        x = frame[["date","instrument"]].copy(); x["v"] = vals.to_numpy()
        xp = x[x.date.isin(dates)].pivot(index="date", columns="instrument", values="v").reindex(index=dates,columns=stocks).to_numpy()
        for _,r in refs.iterrows():
            path=root/"panels"/(r.panel_id+".npy")
            if not path.exists(): continue
            arr=np.load(path); corrs=[]
            for left,right in zip(xp,arr):
                mask=np.isfinite(left)&np.isfinite(right)
                if mask.sum()<100: continue
                lx=rankdata(left[mask]); ry=rankdata(right[mask])
                if lx.std()>0 and ry.std()>0: corrs.append(float(np.corrcoef(lx,ry)[0,1]))
            if corrs: rows.append(dict(candidate=name, cluster=r.cluster, member=r["name"], rho=float(np.mean(corrs)), abs_rho=abs(float(np.mean(corrs))), dates=len(corrs)))
    result=pd.DataFrame(rows).sort_values(["candidate","abs_rho"],ascending=[True,False])
    result.to_csv(OUT/"member_correlations.csv",index=False)
    return result.groupby(["candidate","cluster"],sort=False).head(1)


def arithmetic_evaluate(frame, vals, close, dates, calendar):
    from positive_factor_local_compare import forward_returns, assign_groups
    x=frame[["date","instrument","total_mv"]].copy(); x["factor"]=vals.to_numpy()
    returns=forward_returns(close,calendar,dates,CYCLE,ALIGNMENT_LABEL_OFFSET)
    data=x[x.date.isin(dates)].merge(returns,on=["date","instrument"],how="inner").replace([np.inf,-np.inf],np.nan).dropna()
    previous=None; rows=[]
    for d,g in data.groupby("date",sort=True,observed=True):
        if len(g)<100: continue
        groups=assign_groups(g.factor)
        held=g[groups.eq(10)]; members=set(held.instrument)
        turn=np.nan if previous is None else 1-len(members&previous)/len(members)
        previous=members
        rows.append(dict(date=str(d.date()),stock_count=len(g),rank_ic=g.factor.corr(g.forward_return,method="spearman"),ic_mean=g.factor.corr(g.forward_return),excess=held.forward_return.mean()-g.forward_return.mean(),turnover=turn,corr_smallsize=g.factor.corr(-g.total_mv,method="spearman"),zero_share=float(g.factor.eq(0).mean())))
    periods=pd.DataFrame(rows); gross=float(periods.excess.mean()*252/CYCLE); turn=float(periods.turnover.mean()); cost=turn*252/CYCLE*ALIGNMENT_ROUND_TRIP_COST
    result=dict(periods=len(periods),rank_ic=float(periods.rank_ic.mean()),ic_mean=float(periods.ic_mean.mean()),gross_excess=gross,turnover=turn,annual_cost=cost,net_excess=gross-cost,corr_smallsize=float(periods.corr_smallsize.mean()),zero_share=float(periods.zero_share.mean()),first_signal=periods.date.min(),last_signal=periods.date.max())
    return result,periods

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    import os
    os.environ["FACTOR_LOCAL_UNIVERSE_FILTER"]="off"
    frame = load_full_a_data(PRICE_ROOT, CAP_ROOT, DATA_START, FORMAL_END, market_cap_field=ALIGNMENT_MARKET_CAP_FIELD)
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD); frame, _ = compact_full_a_frame(frame)
    calendar = load_calendar(CAL_ROOT, DATA_START, FORMAL_END)
    dates = generated_dates(calendar, FORMAL_START, FORMAL_END)
    factors = build_factors(frame)
    close = panel_close(frame, calendar)
    results=[]
    for name, vals in factors.items():
        for window, start in [("formal_5y", FORMAL_START), ("recent_2026", RECENT_START)]:
            ds=[d for d in dates if d>=start]
            r,periods=arithmetic_evaluate(frame, vals, close, ds, calendar)
            periods.to_csv(OUT/(name+"-"+window+"-periods.csv"),index=False)
            results.append(dict(candidate=name, window=window, **r))
            print(name,window,r,flush=True)
    pd.DataFrame(results).to_csv(OUT/"results.csv", index=False)
    corr_to_clusters(factors, frame, dates).to_csv(OUT/"cluster_correlations.csv", index=False)
    meta=dict(source_rule_version=ALIGNMENT_RULE_VERSION, diagnostic_version="full-a-arithmetic-noSTfilter-v1", data_start=str(DATA_START.date()), formal_start=str(FORMAL_START.date()), formal_end=str(FORMAL_END.date()), recent_start=str(RECENT_START.date()), cycle=CYCLE, label_offset=ALIGNMENT_LABEL_OFFSET, universe="full_a .SH/.SZ", price="qfq", market_cap=ALIGNMENT_MARKET_CAP_FIELD, cost=ALIGNMENT_ROUND_TRIP_COST, signal_dates=len(dates), cluster_corr_dates="common with saved U-cluster panels (through 2026-08-10)", verification="local_recheck_data verify currently reports 305 hash mismatches; cache is readable but provenance is marked mismatch")
    (OUT/"metadata.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2))
    lines=["# 榜单启发因子本地复现（2026-10-10）","", "没有创建平台因子，也没有消耗平台算力。收益按用户项目指令使用算术年化与未过滤全 A；与 qualitygate4 后文的过滤/复利规则不同，单独版本诊断，不混比旧结果。数据缓存可读，但校验清单报告 305 个文件哈希不一致，结果标记为本地缓存复现，不能视作平台字节级复现。","", "## 结果", "", "|candidate|window|periods|RankIC|gross excess|turnover|annual cost|net excess|", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for _,r in pd.DataFrame(results).iterrows(): lines.append(f"|{r.candidate}|{r.window}|{int(r.periods)}|{r.rank_ic:.4f}|{r.gross_excess*100:.2f}%|{r.turnover*100:.2f}%|{r.annual_cost*100:.2f}%|{r.net_excess*100:.2f}%|")
    lines += ["", "簇相关性只在保存簇面板的共同日期上计算（截至 2026-08-10），并记录每个候选对各已有簇成员的最大绝对日均 Spearman；不把它扩写成完整五年相关性。", "", "结果明细：[results.csv](results.csv)、[cluster_correlations.csv](cluster_correlations.csv)、[metadata.json](metadata.json)。"]
    (OUT/"summary.md").write_text("\n".join(lines)+"\n")
    print((OUT/"summary.md"))

if __name__ == "__main__": main()
