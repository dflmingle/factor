"""归因：池合成因子在平台上收益/IC 的虚高（20.30% -> 46.72%）来自哪？

背景：pool5-live-20260928.py / pool6-* 的 _date_level 在平台 [date, symbol] 索引下
误判 symbol 层为日期层，导致最终 _normalize 变成"按股票全样本 z-score"。
本脚本用同一组席位信号做零算力对照，拆两件事：
  (a) 全样本标准化里的未来信息泄漏（1%/99% 截尾、均值、标准差用整段 5 年算）
  (b) 信号被重定义：截面排序 -> 个股相对自身 5 年历史的偏离（时序信号）

归一化口径（对 5 席 / 6 席合成各做一遍）：
  cs            按日截面 clip(1/99)+z            -- 正确几何
  ts_full_eval  按股票、仅评估窗口全样本 clip+z   -- 线上 bug 的近似复刻
  ts_full_panel 按股票、整段面板(含2018暖机)      -- 错误口径的另一种样本定义
  ts_full_nc    按股票、全样本 z、不截尾          -- 拆出截尾的贡献
  ts_exp        按股票、因果 expanding z(min252)  -- 无未来信息，只剩信号重定义

指标：top-decile 换手/次、10d RankIC、top-decile 相对当日截面均值的超额（mock 口径）。
绝对水平与平台不可比，只做口径间相对比较。零算力，不提交平台。
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "scripts/_smoke_pool6_lamd10k5v2_20260929.py"
POOL6 = ROOT / "pool6-lamd10k5v2-20260929.py"
PANELS = ROOT / "research_reports/platform_alignment/e-decomp-20260929/panels_cache.pkl"
OUTDIR = ROOT / "research_reports/platform_alignment/lookahead-attrib-20260929"
START = "2021-09-07"
CYCLE = 10


def load_smoke():
    import importlib.util

    spec = importlib.util.spec_from_file_location("smoke6", SMOKE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def capture_seats(path, fields, smoke):
    """执行候选池文件，拦截 _normalize，拿到 6 个未归一化的席位信号。"""
    g = {"np": np, "Factor": type("Factor", (), {})}
    for name in ["RANK", "ZSCORE", "DELAY", "SUM", "MA", "STD", "STDDEV",
                 "TS_MAX", "CORR", "ABS", "RETURNS"]:
        g[name] = getattr(smoke, name)
    cap = []
    src = Path(path).read_text(encoding="utf-8")
    exec(compile(src, str(path), "exec"), g)
    g["_normalize"] = lambda s, level: (cap.append(s.copy()) or s)
    cls = g["Pool6Lamd10K5V2Factor"]
    cls().calculate(dict(fields))
    return cap


def _clean(x):
    return x.replace([np.inf, -np.inf], np.nan)


def _clipz(x):
    x = _clean(x)
    lo, hi = x.quantile(0.01), x.quantile(0.99)
    x = x.clip(lower=lo, upper=hi)
    sd = x.std(ddof=0)
    if not np.isfinite(sd) or sd <= 1e-12:
        return x * 0.0
    return (x - x.mean()) / sd


def _z(x):
    x = _clean(x)
    sd = x.std(ddof=0)
    if not np.isfinite(sd) or sd <= 1e-12:
        return x * 0.0
    return (x - x.mean()) / sd


def _expz(x):
    x = _clean(x)
    m = x.expanding(min_periods=252).mean()
    sd = x.expanding(min_periods=252).std(ddof=0)
    sd = sd.where(sd > 1e-12)
    return (x - m) / sd


MODES = ["cs", "ts_full_eval", "ts_full_panel", "ts_full_nc", "ts_exp",
         "ts_fullmean_expstd", "ts_expmean_fullstd"]


def _full_mean(s, ts):
    sub = s[s.index.get_level_values(0) >= ts]
    return sub.groupby(level=1).transform(lambda x: x.mean()).reindex(s.index)


def _full_std(s, ts):
    sub = s[s.index.get_level_values(0) >= ts]
    return sub.groupby(level=1).transform(lambda x: x.std(ddof=0)).reindex(s.index)


def _exp_mean(s):
    return s.groupby(level=1).transform(lambda x: x.expanding(min_periods=252).mean())


def _exp_std(s):
    return s.groupby(level=1).transform(lambda x: x.expanding(min_periods=252).std(ddof=0))


def build_composite(seats, mode, n_seat):
    out = []
    ts = pd.Timestamp(START)
    for s in seats[:n_seat]:
        if mode == "cs":
            o = s.groupby(level=0).transform(_clipz)
        elif mode == "ts_full_eval":
            sub = s[s.index.get_level_values(0) >= ts]
            o = sub.groupby(level=1).transform(_clipz).reindex(s.index)
        elif mode == "ts_full_panel":
            o = s.groupby(level=1).transform(_clipz)
        elif mode == "ts_full_nc":
            o = s.groupby(level=1).transform(_z)
        elif mode == "ts_exp":
            o = s.groupby(level=1).transform(_expz)
        elif mode == "ts_fullmean_expstd":
            o = (s - _full_mean(s, ts)) / _exp_std(s)
        elif mode == "ts_expmean_fullstd":
            o = (s - _exp_mean(s)) / _full_std(s, ts)
        else:
            raise ValueError(mode)
        out.append(o)
    return sum(out) / len(out)


def rebalance_dates(dates, start=START, cycle=CYCLE):
    d = [x for x in dates if str(x)[:10] >= start]
    return d[::cycle]


def turnover_topdecile(f, rb):
    tos, prev = [], None
    for dt in rb:
        x = _clean(f.xs(dt, level=0)).dropna()
        if len(x) < 50:
            prev = None
            continue
        k = max(1, int(len(x) * 0.1))
        cur = set(x.nlargest(k).index)
        if prev is not None:
            tos.append(1.0 - len(cur & prev) / len(prev))
        prev = cur
    return float(np.mean(tos)) if tos else float("nan")


def forward_metrics(f, rb, close_w):
    ics, exs, lss = [], [], []
    for i in range(len(rb) - 1):
        d0, d1 = rb[i], rb[i + 1]
        x = _clean(f.xs(d0, level=0))
        fwd = _clean(close_w.loc[d1] / close_w.loc[d0] - 1.0)
        df = pd.concat([x.rename("f"), fwd.rename("r")], axis=1).dropna()
        if len(df) < 50:
            continue
        ics.append(df["f"].rank().corr(df["r"].rank()))
        k = max(1, int(len(df) * 0.1))
        top = df.nlargest(k, "f")["r"].mean()
        bot = df.nsmallest(k, "f")["r"].mean()
        exs.append(top - df["r"].mean())
        lss.append(top - bot)
    ic = float(np.mean(ics)) if ics else float("nan")
    icir = float(np.mean(ics) / np.std(ics, ddof=0)) if len(ics) > 2 else float("nan")
    return {
        "rank_ic": ic,
        "ic_ir": icir,
        "excess_per_period": float(np.mean(exs)) if exs else float("nan"),
        "excess_annualized": float(np.mean(exs) * 252.0 / CYCLE) if exs else float("nan"),
        "cum5y_excess": float(np.prod([1.0 + e for e in exs]) - 1.0) if exs else float("nan"),
        "ls_per_period": float(np.mean(lss)) if lss else float("nan"),
        "n_periods": len(ics),
    }


def rank_overlap(fa, fb, rb):
    cs = []
    for dt in rb:
        a = _clean(fa.xs(dt, level=0)).rank()
        b = _clean(fb.xs(dt, level=0)).rank()
        df = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
        if len(df) >= 50:
            cs.append(df["a"].corr(df["b"]))
    return float(np.mean(cs)) if cs else float("nan")


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    smoke = load_smoke()
    fields = smoke.load_fields(n_symbols=n)
    print(f"[attrib] loaded {len(fields['close']):,} rows, symbols~{n}", flush=True)
    seats = capture_seats(POOL6, fields, smoke)
    print(f"[attrib] captured {len(seats)} seats", flush=True)
    close_w = pd.read_pickle(PANELS)["close"]
    syms = sorted(set(seats[0].index.get_level_values(1)))
    close_w = close_w.reindex(columns=syms)
    dates = sorted(set(seats[0].index.get_level_values(0)))
    rb = rebalance_dates(dates)
    print(f"[attrib] rebalance dates: {len(rb)} ({str(rb[0])[:10]} .. {str(rb[-1])[:10]})", flush=True)

    result = {"n_symbols": n, "rebalance_dates": len(rb), "pools": {}}
    for pool_name, k in (("pool5", 5), ("pool6", 6)):
        result["pools"][pool_name] = {}
        for mode in MODES:
            f = build_composite(seats, mode, k)
            t = turnover_topdecile(f, rb)
            m = forward_metrics(f, rb, close_w)
            m["turnover_per_reb"] = t
            result["pools"][pool_name][mode] = m
            print(f"[attrib] {pool_name:5s} {mode:13s} turn={t:.4f} ric={m['rank_ic']:.4f} "
                  f"ex={m['excess_annualized']:+.2%}/yr cum5y={m['cum5y_excess']:+.1%}", flush=True)
        cs_f = build_composite(seats, "cs", k)
        for mode in MODES[1:]:
            f = build_composite(seats, mode, k)
            result["pools"][pool_name][mode]["rank_corr_vs_cs"] = rank_overlap(cs_f, f, rb)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "attribution.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[attrib] wrote {OUTDIR/'attribution.json'}", flush=True)


if __name__ == "__main__":
    main()
