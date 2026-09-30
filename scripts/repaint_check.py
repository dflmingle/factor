"""repaint / 未来泄漏自检（2026-09-29 起，Python 池合成因子提交前必跑）。

原理：把回测面板截断到 cutoff 后重算候选因子；因果因子的历史值只依赖 t 之前的数据，
截断后必须逐位不变。若不重合 => 因子值 repaint（用了未来信息），平台指标会虚高、实盘不可复现。

用法:
    python3 scripts/repaint_check.py <candidate.py> [n_symbols] [cutoff]
默认 n_symbols=500、cutoff=2025-06-30；对比区间 = cutoff 前 12 个月（该区间两侧都有足够暖机）。
退出码 0=通过，1=检出泄漏/异常。
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "scripts/_smoke_pool6_lamd10k5v2_20260929.py"
PANELS = ROOT / "research_reports/platform_alignment/e-decomp-20260929/panels_cache.pkl"
OPS = ["RANK", "ZSCORE", "DELAY", "SUM", "MA", "STD", "STDDEV", "TS_MAX",
       "CORR", "ABS", "RETURNS"]


def load_smoke():
    spec = importlib.util.spec_from_file_location("smoke6", SMOKE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_factor_class(path, smoke):
    g = {"np": np, "Factor": type("Factor", (), {})}
    for name in OPS:
        g[name] = getattr(smoke, name)
    src = Path(path).read_text(encoding="utf-8")
    exec(compile(src, str(path), "exec"), g)
    classes = [v for k, v in g.items()
               if isinstance(v, type) and k != "Factor" and issubclass(v, g["Factor"])]
    if not classes:
        raise SystemExit(f"未找到 Factor 子类: {path}")
    return classes[0]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = Path(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 500
    cutoff = pd.Timestamp(sys.argv[3]) if len(sys.argv) > 3 else pd.Timestamp("2025-06-30")
    smoke = load_smoke()
    fields = smoke.load_fields(n_symbols=n)
    fields_cut = {k: v[v.index.get_level_values(0) <= cutoff] for k, v in fields.items()}
    cls = load_factor_class(path, smoke)
    full = cls().calculate(dict(fields))
    cut = cls().calculate(dict(fields_cut)).reindex(full.index)
    start = cutoff - pd.Timedelta(days=365)
    idx = full.index
    mask = (idx.get_level_values(0) >= start) & (idx.get_level_values(0) <= cutoff)
    df = pd.concat([full[mask].rename("full"), cut[mask].rename("cut")], axis=1).dropna()
    rows = []
    for dt, grp in df.groupby(level=0):
        if len(grp) < 50:
            continue
        rows.append((dt, grp["full"].corr(grp["cut"]),
                     float((grp["full"] - grp["cut"]).abs().max())))
    if not rows:
        print(f"[repaint] {path.name}: 对比区间无有效数据，无法判定")
        return 1
    corr_mean = float(np.mean([r[1] for r in rows]))
    corr_min = float(np.min([r[1] for r in rows]))
    maxdiff = float(np.max([r[2] for r in rows]))
    scale = float(df["full"].std(ddof=0))
    rel = maxdiff / scale if scale > 0 else float("inf")
    verdict = "PASS（因果，无未来泄漏）" if (corr_min > 0.999999 and rel < 1e-6) else "FAIL（repaint = 用了未来数据）"
    print(f"[repaint] {path.name}: n_sym={n} cutoff={cutoff.date()} 对比期数={len(rows)}")
    print(f"          逐日相关 mean={corr_mean:.6f} min={corr_min:.6f} | "
          f"max|Δ|={maxdiff:.3e} (相对std {rel:.1e})")
    print(f"          判定: {verdict}")
    return 0 if verdict.startswith("PASS") else 1


if __name__ == "__main__":
    sys.exit(main())
