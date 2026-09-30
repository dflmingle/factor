#!/usr/bin/env python3
"""LEGMIX-NEXT 复合候选池级轻量屏（2026-09-29，零平台算力）。

对挖掘输出的复合腿候选（specs JSON 的每个 K 步）计算：
  - 池侧口径 s_i（RankIC 序列，120 期，与平台池侧一致）
  - 候选自身 top-decile 换手 / corr_size（vs total_mv）
  - 池合成 ΔT 预测（z-score 插入 5 席池，top-decile 换手差；与 light_cand_screen 同逻辑）
  - ΔNA 与 A 段预测（池侧公式：ΔA = 18333 x (s_i - .025893) 分/月）
  - 纯换手通道的 C 段代价情景表（固定 Rex/SR/DD，仅 T 变化）

用法：
  python scripts/legmix_next_screen_20260929.py --specs <tag1>_specs.json,<tag2>_specs.json --min-k 5
"""
from __future__ import annotations

import argparse
import gc
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from legmix_next_legs_20260929 import build_raw_legs  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/legmix-next-20260929"
PANELS = ROOT / "research_reports/platform_alignment/e-decomp-20260929/panels_cache.pkl"
REBUILD = ROOT / "research_reports/platform_alignment/e-decomp-20260928/seat_panels_rebuilt.pkl"
CYCLE, GROUPS = 10, 10
T0 = time.time()

SEAT_SUM_S = 0.1295            # 平台实测 5 席 s_i 合计（.0593+.0221+.0210+.0180+.0091）
SEAT_MEAN_S = SEAT_SUM_S / 5.0
A_UNIT_POOL = 40000.0 * 1.1 * 0.20 * 12.5 / 6.0   # = 18333.3 分/月 per unit s_i（池侧公式）
T5_POOL = 0.2410               # 平台实测 5 席池每次调仓换手
C_ANCHOR, W_C = 0.60, 0.45


def log(m: str) -> None:
    print(f"[{time.time() - T0:7.1f}s] {m}", flush=True)


def top_decile_held(values: np.ndarray) -> set:
    finite = np.isfinite(values)
    idx = np.flatnonzero(finite)
    if len(idx) < GROUPS * 10:
        return set()
    q = (len(idx) * (GROUPS - 1)) // GROUPS
    part = np.argpartition(values[idx], q)[q:]
    return set(idx[part].tolist())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--specs", required=True, help="逗号分隔的挖掘 specs JSON 路径")
    ap.add_argument("--min-k", type=int, default=5)
    ap.add_argument("--max-cand", type=int, default=40)
    ap.add_argument("--tag", default="screen")
    args = ap.parse_args()

    cands = []
    for p in args.specs.split(","):
        path = Path(p.strip())
        if not path.is_absolute():
            path = OUT / path if not path.exists() else path
        data = json.loads(path.read_text(encoding="utf-8"))
        for step in data["steps"]:
            if step["k"] >= args.min_k:
                cands.append(dict(tag=data.get("tag", path.stem), k=step["k"],
                                  name=f"{data.get('tag', path.stem)}K{step['k']}",
                                  legs=step["legs"], signed=step.get("signed") or {n: 1.0 for n in step["legs"]},
                                  s_i_mine=step.get("s_i_5y"), icir_mine=step.get("icir_5y"),
                                  turn_mine=step.get("turn10"), corr_size_mine=step.get("corr_size")))
    cands = cands[: args.max_cand]
    log(f"{len(cands)} candidates from {args.specs}")

    panels = pickle.load(PANELS.open("rb"))
    payload = pickle.load(REBUILD.open("rb"))
    dates = [pd.Timestamp(d) for d in payload["dates"]]
    seats = payload["scores"].reset_index(drop=True)
    signal_frame = payload["signal_frame"]
    seat_sum = seats.sum(axis=1).to_numpy(dtype="float64")
    date_mask = {pd.Timestamp(d): (signal_frame["date"] == d).to_numpy() for d in dates}
    C = panels["close"]
    cal = list(C.index)
    pos = {d: i for i, d in enumerate(cal)}
    rets = [C.iloc[pos[d] + 1 + CYCLE].to_numpy(dtype="float64") /
            C.iloc[pos[d] + 1].to_numpy(dtype="float64") - 1.0 for d in dates]
    cap = panels["mcap"].reindex(index=dates)
    log("panels+payload ready")

    stock_pos = {c: j for j, c in enumerate(C.columns.astype(str))}
    seat_finite = np.isfinite(seats.to_numpy(dtype="float64")).all(axis=1)
    date_take = {}
    for d in dates:
        mrow = date_mask[d]
        inst = signal_frame.loc[mrow, "instrument"].astype(str).to_numpy()
        date_take[d] = (mrow, np.array([stock_pos.get(s2, -1) for s2 in inst], dtype=np.int64))

    # 5 席池基线换手（合并 top-decile）
    prev_pool = None
    pool_turn = []
    for d in dates:
        m = date_mask[d]
        inst_d = signal_frame.loc[m, "instrument"].astype(str).to_numpy()
        held = {inst_d[i] for i in top_decile_held(seat_sum[m])}
        if prev_pool is not None and held:
            pool_turn.append(1.0 - len(held & prev_pool) / len(held))
        prev_pool = held
    t5_baseline = float(np.mean(pool_turn))
    log(f"5 席池基线换手/次 = {t5_baseline:.4f}（平台实测 {T5_POOL:.4f}）")

    raw = build_raw_legs(panels)
    rank_cache: dict[str, pd.DataFrame] = {}

    def rankpct(name: str) -> pd.DataFrame:
        if name not in rank_cache:
            rank_cache[name] = raw[name].rank(axis=1, pct=True).astype("float32")
        return rank_cache[name]

    rows = []
    for cand in cands:
        comp = None
        for leg, sign in cand["signed"].items():
            r = rankpct(leg)
            v = r * float(sign)
            comp = v if comp is None else comp + v
        comp = (comp / len(cand["signed"])).reindex(index=dates)
        ics, turns, corrs, dturns = [], [], [], []
        prev = None
        prev_pool = None
        prev_oldmap = None
        for k, d in enumerate(dates):
            x = comp.iloc[k].to_numpy(dtype="float64")
            y = rets[k]
            m = np.isfinite(x) & np.isfinite(y)
            if m.sum() >= 100:
                ics.append(float(np.corrcoef(pd.Series(x[m]).rank(), pd.Series(y[m]).rank())[0, 1]))
            held = top_decile_held(x)
            if prev is not None and held:
                turns.append(1.0 - len(held & prev) / len(held))
            prev = held
            b = cap.iloc[k].to_numpy(dtype="float64")
            m2 = np.isfinite(x) & np.isfinite(b)
            if m2.sum() >= 200:
                corrs.append(float(np.corrcoef(pd.Series(x[m2]).rank(), pd.Series(b[m2]).rank())[0, 1]))
            mrow, take = date_take[d]
            cvals = np.full(len(take), np.nan)
            ok = take >= 0
            cvals[ok] = x[take[ok]]
            ok = seat_finite[mrow] & np.isfinite(cvals)
            idx = np.flatnonzero(ok)
            if len(idx) >= 100:
                v = cvals[idx]
                lo, hi = np.quantile(v, [0.01, 0.99])
                clipped = np.clip(v, lo, hi)
                std = clipped.std(ddof=0)
                z = (clipped - clipped.mean()) / std if std > 1e-12 else np.zeros(len(v))
                ssum = seat_sum[mrow][idx]
                new_sum = ssum + z
                inst_d = signal_frame.loc[mrow, "instrument"].astype(str).to_numpy()
                q = (len(idx) * (GROUPS - 1)) // GROUPS
                hn = set(inst_d[idx[np.argpartition(new_sum, q)[q:]]])
                ho = set(inst_d[idx[np.argpartition(ssum, q)[q:]]])
                if prev_pool is not None and hn and ho:
                    dturns.append((1.0 - len(hn & prev_pool) / len(hn)) - (1.0 - len(ho & prev_oldmap) / len(ho)))
                prev_pool = hn
                prev_oldmap = ho
        ics = np.asarray(ics)
        mean = float(ics.mean()); sd = float(ics.std(ddof=1))
        icir = abs(mean) / sd if sd > 0 else 0.0
        win = float((ics > 0.02).mean()) if mean >= 0 else float((ics < -0.02).mean())
        s_i = abs(mean) * icir * win
        turn = float(np.mean(turns)) if turns else np.nan
        dT = float(np.mean(dturns)) if dturns else np.nan
        corr_size = float(np.mean(corrs)) if corrs else np.nan
        t6 = t5_baseline + dT
        d_na = 12.5 * ((SEAT_SUM_S + s_i) / 6.0 - SEAT_MEAN_S)
        d_a = A_UNIT_POOL * (s_i - SEAT_MEAN_S)
        f_t = max(T5_POOL, 0.30) / max(t6, 0.30)
        rows.append(dict(name=cand["name"], tag=cand["tag"], k=cand["k"], periods=len(ics),
                         s_i=s_i, icir=icir, ic=abs(mean), win=win, turn=turn,
                         corr_size=corr_size, pred_dturn=dT, t6_est=t6,
                         d_na=d_na, d_a_pred=d_a,
                         s_i_calib=s_i * 1.162, d_a_calib=A_UNIT_POOL * (s_i * 1.162 - SEAT_MEAN_S),
                         t_factor=f_t, rawc_drop=f_t - 1.0,
                         legs="+".join(cand["legs"])))
        log(f"[{cand['name']:>16}] s_i={s_i:.4f} icir={icir:.3f} win={win:.3f} turn={turn:.3f} "
            f"corrSz={corr_size:+.2f} dT={dT:+.4f} T6={t6:.3f} dA={d_a:+,.0f}")
        del comp
        gc.collect()

    df = pd.DataFrame(rows)
    # C 段纯换手通道情景（固定 Rex/SR/DD；rawC6 = rawC5 x f_t）
    for rc in (0.60, 0.70, 0.80, 0.90, 1.00):
        df[f"dC_Tonly_rc{int(rc*100)}"] = [
            44000.0 * W_C * (min(rc * f / C_ANCHOR, 1.0) - min(rc / C_ANCHOR, 1.0)) for f in df.t_factor]
    df = df.sort_values("d_a_pred", ascending=False)
    path = OUT / f"{args.tag}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 300)
    cols = ["name", "k", "s_i", "icir", "win", "turn", "corr_size", "pred_dturn", "t6_est",
            "d_na", "d_a_pred", "d_a_calib", "dC_Tonly_rc70", "dC_Tonly_rc80", "dC_Tonly_rc90", "dC_Tonly_rc100"]
    print(df[cols].round(4).to_string(index=False))
    log(f"written {path} ({len(df)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
