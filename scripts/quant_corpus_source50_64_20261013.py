"""Source-fixed RSRS/bias variants from corpus sources 50 and 64.

Offline only.  The ETF/index execution path is deliberately not claimed;
these are causal full-A factor adaptations used to discover whether the
source signal has independent cross-sectional information.
"""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec, audit, simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text

SRC50 = "quant/2024年度精选策略2/50.ETF动量轮动RSRS择时-V2.1.txt"
SRC64 = "quant/2024年度精选策略2/64.ETF轮动策略升级-增加盘中止损.txt"
OUT = q.ROOT / "research_reports/platform_alignment/quant-corpus-semantic-source153-20261013"
COMMON = (
    "proxy: completed prior-bar daily OHLC extension of the source ETF/index kernel to full-A; "
    "rolling-600 RSRS population-z and R2 are causal. ETF holdings, cross-asset universe, "
    "intraday 60-minute stop, and order execution are not reconstructed."
)
SPECS = [
    spec(
        "source50_rsrs_slope8_guard_m07",
        "RSRS阈值零点反转与八日斜率联合非卖出",
        SRC50,
        "I(rsrs18_z600_R2>-0.7 AND NOT(rsrs8_slope<0 AND rsrs>0))",
        COMMON + " Exact source50 score threshold is 0.7; the negative-score exit has priority over BUY.",
    ),
    spec(
        "source50_bias90_joint_rsrs_slope8_m07",
        "九十日乖离动量与RSRS非卖出联合",
        SRC50,
        "bias90_OLS20_prior WHERE rsrs18_z600_R2>-0.7 AND NOT(rsrs8_slope<0 AND rsrs>0)",
        COMMON + " Source ranks the 90/20 bias slope and separately gates trading with RSRS; product is a fixed diagnostic joint, no tuning.",
    ),

]
SPECS[-1]["gated"] = True


def rsrs_and_slope(f):
    h = pd.DataFrame(f["high"].astype(float))
    l = pd.DataFrame(f["low"].astype(float))
    cov = h.rolling(18).cov(l, ddof=0)
    vl = l.rolling(18).var(ddof=0)
    vh = h.rolling(18).var(ddof=0)
    beta = cov / vl
    z = (beta - beta.rolling(600).mean()) / beta.rolling(600).std(ddof=0)
    rs = (z * cov**2 / (vl * vh)).to_numpy()
    slope = np.full(rs.shape, np.nan)
    x = np.arange(8) - 3.5
    den = float((x * x).sum())
    for t in range(7, len(rs)):
        slope[t] = (x[:, None] * rs[t - 7 : t + 1]).sum(axis=0) / den
    return rs, slope


def bias90(f):
    c = pd.DataFrame(f["close"].astype(float))
    b = (c / c.rolling(90).mean()).to_numpy()
    out = np.full(b.shape, np.nan)
    x = np.arange(20) - 9.5
    den = float((x * x).sum())
    for t in range(19, len(b)):
        a = b[t - 19 : t + 1]
        out[t] = (x[:, None] * (a / a[0])).sum(axis=0) / den
    return out


def values(f, pos):
    rs, slope = rsrs_and_slope(f)
    allow = np.isfinite(rs) & np.isfinite(slope) & (rs > -0.7) & ~((slope < 0) & (rs > 0))
    bs = bias90(f)
    valid = np.isfinite(rs) & np.isfinite(slope)
    return [np.where(valid, allow.astype(float), np.nan)[pos-1], np.where(allow, bs, np.nan)[pos-1]]



def main():
    OUT.mkdir(exist_ok=True)
    plan = dict(specs=SPECS, rule=q.ALIGNMENT_RULE_VERSION, platform_compute=0, selection="source-fixed source50 threshold and joint, source64 traced to existing source100 instead of redundant retest")
    fp = OUT / "frozen_plan.json"
    if fp.exists() and json.loads(fp.read_text()) != plan:
        raise ValueError("frozen mismatch")
    q.dump(fp, plan)
    if (OUT / "audit_complete.json").exists():
        return
    cal, stocks, f = q.load_market()
    grid = pd.read_pickle(q.OUT / "signal_panels.pkl")["dates"]
    pos = cal.get_indexer(grid)
    sf = {k: v[:, :32] for k, v in f.items()}
    full = values(sf, pos)
    checks = []
    for n in [35, 79]:
        stop = pos[n - 1] + 1
        cut = values({k: v[:stop] for k, v in sf.items()}, pos[:n])
        for sp, a, b in zip(SPECS, full, cut):
            np.testing.assert_allclose(a[:n], b, equal_nan=True, atol=1e-7)
            checks.append(dict(key=sp["key"], test="causal_prefix_replay", passed=True))
    rs, sl = rsrs_and_slope(sf)
    for i in [35, 79]:
        t = pos[i]
        for j in range(8):
            if np.isfinite(rs[t - 7 : t + 1, j]).all():
                np.testing.assert_allclose(sl[t, j], np.polyfit(np.arange(8), rs[t - 7 : t + 1, j], 1)[0], atol=1e-8)
    checks.append(dict(test="independent_rsrs_18_600_population_z_r2_and_slope8", passed=True))
    # Independent literal OLS18 and population standardization of all 600 betas.
    for i in [35, 79]:
        t = pos[i]-1
        for j in range(4):
            betas = []
            r2 = np.nan
            for end in range(t-599, t+1):
                lo = sf['low'][end-17:end+1,j].astype(float)
                hi = sf['high'][end-17:end+1,j].astype(float)
                if not np.isfinite(lo).all() or not np.isfinite(hi).all() or lo.std()==0:
                    betas.append(np.nan)
                    continue
                betas.append(np.polyfit(lo, hi, 1)[0])
                r2 = np.corrcoef(lo,hi)[0,1]**2
            betas=np.array(betas)
            if np.isfinite(betas).all():
                np.testing.assert_allclose(rs[t,j], (betas[-1]-betas.mean())/betas.std()*r2, atol=1e-5)
    checks.append(dict(test='independent600_literal_OLS18_population_z_R2',passed=True))
    q.dump(OUT / "source_evidence.json", {SRC50: read_text(q.ROOT / SRC50), SRC64: read_text(q.ROOT / SRC64)})
    run(OUT, SPECS, values(f, pos), cal, stocks, f, checks, dict(statistics="exploratory no untouched OOS", fidelity=COMMON), residualizer=lambda x, s, r: simultaneous_residual(x, [s, r]))
    tie_diagnostic(OUT, cal, stocks, f)
    audit(OUT, cal, stocks, f)
    q.dump(OUT / "audit_complete.json", dict(completed=True, platform_compute=0))
    print("FINISHED153", flush=True)


if __name__ == "__main__":
    main()
