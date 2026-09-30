"""legmix 复合候选的审计：符号/换手/size 暴露/与现役席腿的重叠（本地零算力）。

输出：research_reports/platform_alignment/legmix-20260928/audit.md + composite_formula.txt
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PANELS = ROOT / "research_reports/platform_alignment/alpha191-local-20260923/panels.pkl"
OUT = ROOT / "research_reports/platform_alignment/legmix-20260928"
CYCLE = 10
W5 = ("2021-09-07", "2026-09-07")
W1 = ("2026-01-01", "2026-09-07")

LEGS = ["intr20", "amt60", "maxret20", "retrev5", "pvcorr20", "t_std10_60", "amihud20"]


def load_panels() -> dict:
    with PANELS.open("rb") as fh:
        panels = pickle.load(fh)["panels"]
    return {k: v.astype("float32") for k, v in panels.items()}


def sched_of(cal, span):
    lo = int(cal.searchsorted(pd.Timestamp(span[0]), side="left"))
    hi = int(cal.searchsorted(pd.Timestamp(span[1]), side="right")) - 1
    return list(cal[lo:hi + 1:CYCLE])


def ic_series(values, close, cal, sched, idx):
    out = np.full(len(sched), np.nan)
    for k, date in enumerate(sched):
        i = idx[date]
        if i + 1 + CYCLE >= len(cal):
            continue
        y = (close.iloc[i + 1 + CYCLE].to_numpy("float64") / close.iloc[i + 1].to_numpy("float64") - 1.0)
        x = values.iloc[i].to_numpy("float64")
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 100:
            continue
        xr = pd.Series(x[ok]).rank().to_numpy()
        yr = pd.Series(y[ok]).rank().to_numpy()
        if xr.std() == 0 or yr.std() == 0:
            continue
        out[k] = float(np.corrcoef(xr, yr)[0, 1])
    return out


def stats(s):
    s = s[np.isfinite(s)]
    if len(s) < 6:
        return dict(n=len(s), ic=np.nan, icir=np.nan, win=np.nan, s_i=np.nan, mean=np.nan)
    m, sd = float(s.mean()), float(s.std(ddof=1))
    sign = 1.0 if m >= 0 else -1.0
    icir = abs(m) / sd if sd > 0 else 0.0
    win = float(np.mean(s * sign > 0.02))
    return dict(n=len(s), ic=abs(m), icir=icir, win=win, s_i=abs(m) * icir * win, mean=m)


def turnover_top(values, sched, idx, top=0.10):
    prev, chg = None, []
    for date in sched:
        x = values.iloc[idx[date]]
        k = max(int(np.isfinite(x).sum() * top), 1)
        cur = set(np.argsort(-np.nan_to_num(x.to_numpy("float64"), nan=-np.inf))[:k])
        if prev is not None:
            chg.append(1.0 - len(cur & prev) / k)
        prev = cur
    return float(np.mean(chg)) if chg else float("nan")


def main() -> int:
    panels = load_panels()
    C = panels["close"]
    cal = C.index
    idx = {d: i for i, d in enumerate(cal)}
    V, A, O, H, L, T = (panels[k] for k in ("volume", "amount", "open", "high", "low", "turnover"))
    ret1 = C.pct_change(fill_method=None)
    vwap = A * 10.0 / V

    raw = {
        "intr20": ((C - O) / O).rolling(20).mean(),
        "amt60": A.rolling(60).mean(),
        "maxret20": ret1.rolling(20).max(),
        "retrev5": C / C.shift(5) - 1,
        "pvcorr20": H.astype("float64").rolling(20).corr(V.astype("float64")).astype("float32"),
        "t_std10_60": T.rolling(10).std() / T.rolling(60).std(),
        "amihud20": (ret1.abs() / A).rolling(20).mean(),
    }
    formula = {
        "intr20": "MA((CLOSE-OPEN)/OPEN,20)",
        "amt60": "MA(AMOUNT,60)",
        "maxret20": "TS_MAX(RETURNS(CLOSE,1),20)",
        "retrev5": "RETURNS(CLOSE,5)",
        "pvcorr20": "CORR(HIGH,VOLUME,20)",
        "t_std10_60": "DIV(STD(TURNOVER,10),STD(TURNOVER,60))",
        "amihud20": "MA(ABS(RETURNS(CLOSE,1))/AMOUNT,20)",
    }
    w5s, w1s = sched_of(cal, W5), sched_of(cal, W1)

    signs, rows = {}, []
    for name, df in raw.items():
        st = stats(ic_series(df.rank(axis=1, pct=True), C, cal, w5s, idx))
        d = 1.0 if st["mean"] >= 0 else -1.0
        signs[name] = d
        rows.append(dict(leg=name, direction=int(d), ic=st["ic"], icir=st["icir"], win=st["win"], s_i=st["s_i"]))
        print("%-12s dir=%+d  ic=%.4f icir=%.3f win=%.3f s_i=%.4f" % (name, d, st["ic"], st["icir"], st["win"], st["s_i"]), flush=True)

    comp = None
    parts = []
    for i, name in enumerate(LEGS):
        df = (signs[name] * raw[name]).rank(axis=1, pct=True).astype("float32")
        comp = df if comp is None else comp + df
        sgn = "-" if signs[name] < 0 else ""
        parts.append(f"RANK({sgn}{formula[name]})")
    comp = comp / len(LEGS)

    st5 = stats(ic_series(comp, C, cal, w5s, idx))
    st1 = stats(ic_series(comp, C, cal, w1s, idx))
    turn10 = turnover_top(comp, w5s, idx, 0.10)
    turn20 = turnover_top(comp, w5s, idx, 0.20)
    print("\nCOMPOSITE 5y: ic=%.4f icir=%.3f win=%.3f s_i=%.4f turn10=%.3f turn20=%.3f" % (
        st5["ic"], st5["icir"], st5["win"], st5["s_i"], turn10, turn20))
    print("COMPOSITE 1y: ic=%.4f icir=%.3f win=%.3f s_i=%.4f" % (st1["ic"], st1["icir"], st1["win"], st1["s_i"]))

    # 参照腿（现役席成分 / size）
    refs = {
        "SIZE(RANK(MARKET_CAP))": C * 0 + (panels["total_mv"]).rank(axis=1, pct=True),
        "SEAT:1-MA(T,21)/MA(T,504)": 1.0 - (T.rolling(21).mean() / T.rolling(504, min_periods=200).mean()).rank(axis=1, pct=True),
        "SEAT:1-RETURNS(C,40)": 1.0 - (C / C.shift(40) - 1).rank(axis=1, pct=True),
        "SEAT:Amihud60": (A * 0 + (((H - L) / (C.shift(1) + 1e-6)).rolling(60).mean() / (A.rolling(60).mean() + 1))).rank(axis=1, pct=True),
        "SEAT:VWAP250Dev": ((V * (O + C) / 2).rolling(250, min_periods=60).sum() / V.rolling(250, min_periods=60).sum() / C - 1).rank(axis=1, pct=True),
        "SIZE-ONLY-seat(RANK(MV))": panels["total_mv"].rank(axis=1, pct=True),
    }
    corrs = []
    for label, ref in refs.items():
        vals = []
        for date in w5s[-24:]:
            a = comp.iloc[idx[date]].rank(pct=True).to_numpy("float64")
            b = ref.iloc[idx[date]].rank(pct=True).to_numpy("float64")
            ok = np.isfinite(a) & np.isfinite(b)
            if ok.sum() > 200:
                vals.append(float(np.corrcoef(a[ok], b[ok])[0, 1]))
        corrs.append((label, float(np.mean(vals)), len(vals)))
        print("corr vs %-28s = %+.3f (n=%d)" % (label, corrs[-1][1], corrs[-1][2]), flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / "composite_legs.csv", index=False, encoding="utf-8-sig")
    expr = "(" + " + ".join(parts) + f") / {len(LEGS)}"
    (OUT / "composite_formula.txt").write_text("LEGMIX7 ~ " + expr + " ~ 1\n", encoding="utf-8")
    with (OUT / "audit.md").open("w", encoding="utf-8") as fh:
        fh.write("# LEGMIX7 复合候选审计（2026-09-28，本地零算力）\n\n")
        fh.write("贪心前向选择（39 腿库，窗口全部 ≤60 交易日，平台可表达）产物。\n\n")
        fh.write("## 因子级三元组（全 A / qfq / label-1 / cycle=10）\n\n")
        fh.write("| 窗口 | n | ic | icir | win | s_i |\n|---|---:|---:|---:|---:|---:|\n")
        fh.write(f"| 5y 2021-09-07..2026-09-07 | {st5['n']} | {st5['ic']:.4f} | {st5['icir']:.3f} | {st5['win']:.3f} | **{st5['s_i']:.4f}** |\n")
        fh.write(f"| 1y 2026-01-01..2026-09-07 | {st1['n']} | {st1['ic']:.4f} | {st1['icir']:.3f} | {st1['win']:.3f} | {st1['s_i']:.4f} |\n\n")
        fh.write(f"top-decile 逐期换手 = {turn10:.3f}；top-quintile = {turn20:.3f}\n\n")
        fh.write("## 成分与符号\n\n| 腿 | 方向 | 公式 |\n|---|---:|---|\n")
        for r in rows:
            sgn = "-" if r["direction"] < 0 else ""
            fh.write(f"| {r['leg']} | {'正向' if r['direction'] > 0 else '反向'} | `{sgn}{formula[r['leg']]}` |\n")
        fh.write(f"\n## 提交公式\n\n`LEGMIX7 ~ {expr} ~ 1`\n\n")
        fh.write("## size 暴露与现役席重叠（近 24 期截面秩相关均值）\n\n| 参照 | corr | n |\n|---|---:|---:|\n")
        for label, c, n in corrs:
            fh.write(f"| {label} | {c:+.3f} | {n} |\n")
    print(f"\nwrote {OUT/'audit.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
