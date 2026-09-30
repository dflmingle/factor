"""本地冒烟：mock 平台 Python 因子环境，执行 pool5 / pool6 类并比较池级换手与 RankIC。

用途：提交前零算力验证 .py 可执行（未定义名、字段、滚动窗口），并预估
"加入 LAMD10-K5V2 第 6 席"对池换手/IC 的方向性影响（绝对水平不可与平台互比：
bm 用 -log(mcap) 占位、宇宙/成本口径与平台不同）。
"""
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PANELS = Path("research_reports/platform_alignment/e-decomp-20260929/panels_cache.pkl")


def load_fields(n_symbols=None, seed=7):
    d = pickle.load(open(PANELS, "rb"))
    keep_dates = d["close"].index
    syms = d["close"].columns
    if n_symbols and n_symbols < len(syms):
        rng = np.random.default_rng(seed)
        sel = np.sort(rng.choice(len(syms), size=n_symbols, replace=False))
        syms = syms[sel]
    out = {}
    for name, src in (("close", "close"), ("open", "open"), ("high", "high"), ("low", "low"),
                      ("volume", "volume"), ("amount", "amount"), ("turnover", "turn"),
                      ("market_cap", "mcap")):
        w = d[src].loc[keep_dates, syms].astype("float64")
        out[name] = w.stack(dropna=False)
    out["book_to_market_ratio_lf"] = -np.log(out["market_cap"].clip(lower=1.0))
    return out


def _wide(s):
    return s.unstack(1)


def _long(df, idx):
    return df.stack(dropna=False).reindex(idx)


def _roll(s, n, how, min_periods=None):
    idx = s.index
    mp = n if min_periods is None else min_periods
    w = _wide(s)
    if how == "corr":
        raise ValueError
    r = getattr(w.rolling(n, min_periods=mp), how)()
    return _long(r, idx)


def RANK(s):
    return s.groupby(level=0).rank(pct=True)


def ZSCORE(s):
    def _one(x):
        sd = x.std(ddof=0)
        if not np.isfinite(sd) or sd <= 1e-12:
            return x * 0.0
        return (x - x.mean()) / sd
    return s.groupby(level=0).transform(_one)


def DELAY(s, n):
    return _long(_wide(s).shift(n), s.index)


def SUM(s, n):
    return _roll(s, n, "sum")


def MA(s, n):
    return _roll(s, n, "mean")


def STD(x, n):
    return _roll(x, n, "std")


STDDEV = STD


def TS_MAX(s, n):
    return _roll(s, n, "max")


def CORR(a, b, n):
    idx = a.index
    wa, wb = _wide(a), _wide(b)
    cov = wa.rolling(n, min_periods=n).cov(wb)
    va = wa.rolling(n, min_periods=n).var()
    vb = wb.rolling(n, min_periods=n).var()
    r = cov / (np.sqrt(va) * np.sqrt(vb))
    return _long(r, idx)


def ABS(s):
    return s.abs()


def RETURNS(s, n):
    return _long(_wide(s) / _wide(s).shift(n) - 1.0, s.index)


def _load_class(path, name, force_level=None):
    src = Path(path).read_text(encoding="utf-8")

    class Factor:
        pass

    g = {"np": np, "Factor": Factor, "RANK": RANK, "ZSCORE": ZSCORE, "DELAY": DELAY,
         "SUM": SUM, "MA": MA, "STD": STD, "STDDEV": STDDEV, "TS_MAX": TS_MAX,
         "CORR": CORR, "ABS": ABS, "RETURNS": RETURNS}
    exec(compile(src, str(path), "exec"), g)
    # force_level: 覆盖文件里的 _date_level 探测（0=截面/日期层，1=symbol 层），
    # 用于复现/排除"Python 侧索引层探测错误"导致的时序归一化。
    if force_level is not None:
        g["_date_level"] = lambda s, _lv=force_level: _lv
    return g[name]


def _rebalance_idx(dates, start, cycle=10):
    d = [x for x in dates if str(x)[:10] >= start]
    return d[::cycle]


def _turnover_topdecile(f, dates):
    tos = []
    prev = None
    for dt in dates:
        x = f.xs(dt, level=0)
        x = x.replace([np.inf, -np.inf], np.nan).dropna()
        if len(x) < 50:
            prev = None
            continue
        k = max(1, int(len(x) * 0.1))
        cur = set(x.nlargest(k).index)
        if prev is not None:
            tos.append(1.0 - len(cur & prev) / len(prev))
        prev = cur
    return float(np.mean(tos)) if tos else float("nan")


def _rank_ic(f, dates, close_w, cycle=10):
    ics = []
    c = close_w
    for i in range(len(dates) - 1):
        d0, d1 = dates[i], dates[i + 1]
        x = f.xs(d0, level=0).replace([np.inf, -np.inf], np.nan)
        fwd = (c.loc[d1] / c.loc[d0] - 1).replace([np.inf, -np.inf], np.nan)
        df = pd.concat([x.rename("f"), fwd.rename("r")], axis=1).dropna()
        if len(df) < 50:
            continue
        ics.append(df["f"].rank().corr(df["r"].rank()))
    return float(np.mean(ics)) if ics else float("nan")


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 800
    force_level = int(sys.argv[2]) if len(sys.argv) > 2 else None
    fields = load_fields(n_symbols=n)
    print(f"loaded {len(fields['close']):,} rows, symbols~{n}")
    cls5 = _load_class("pool5-live-20260928.py", "Pool5LiveFactor", force_level)
    cls6 = _load_class("pool6-lamd10k5v2-20260929.py", "Pool6Lamd10K5V2Factor", force_level)
    f5 = cls5().calculate(dict(fields))
    f6 = cls6().calculate(dict(fields))
    cov5 = f5.dropna().groupby(level=0).size()
    cov6 = f6.dropna().groupby(level=0).size()
    print(f"coverage5: last date n={cov5.iloc[-1]}, mean={cov5.mean():.0f}")
    print(f"coverage6: last date n={cov6.iloc[-1]}, mean={cov6.mean():.0f}")
    dates = sorted(set(f5.index.get_level_values(0)))
    rb = _rebalance_idx(dates, "2021-09-07", 10)
    print(f"rebalance dates: {len(rb)} ({str(rb[0])[:10]} .. {str(rb[-1])[:10]})")
    close_w = _wide(fields["close"]).unstack(1) if False else None
    close_w = pickle.load(open(PANELS, "rb"))["close"]
    close_w = close_w.reindex(columns=sorted(set(f5.index.get_level_values(1))))
    t5 = _turnover_topdecile(f5, rb)
    t6 = _turnover_topdecile(f6, rb)
    ic5 = _rank_ic(f5, rb, close_w)
    ic6 = _rank_ic(f6, rb, close_w)
    print(f"turnover(top10%): 5seat={t5:.4f} 6seat={t6:.4f} delta={t6 - t5:+.4f}")
    print(f"RankIC(10d fwd):  5seat={ic5:.4f} 6seat={ic6:.4f} delta={ic6 - ic5:+.4f}")
    print("corr(rank) 5 vs 6 seat last date:", end=" ")
    d_last = rb[-1]
    a = f5.xs(d_last, level=0).rank()
    b = f6.xs(d_last, level=0).rank()
    print(f"{a.corr(b):.4f}")


if __name__ == "__main__":
    main()
