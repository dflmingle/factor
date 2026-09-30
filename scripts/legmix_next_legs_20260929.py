"""LEGMIX-NEXT 腿库（2026-09-29）：与 legmix_mine_20260928 同一定义 + volstab 长窗腿。

共享给挖掘脚本与池级账本（e_decomp_direct）扩展使用。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FORMULA = {
    "intr20": "MA((CLOSE-OPEN)/OPEN,20)",
    "amt60": "MA(AMOUNT,60)",
    "maxret20": "TS_MAX(RETURNS(CLOSE,1),20)",
    "retrev5": "RETURNS(CLOSE,5)",
    "retrev10": "RETURNS(CLOSE,10)",
    "retrev20": "RETURNS(CLOSE,20)",
    "pvcorr20": "CORR(HIGH,VOLUME,20)",
    "t_std10_60": "DIV(STD(TURNOVER,10),STD(TURNOVER,60))",
    "amihud20": "MA(ABS(RETURNS(CLOSE,1))/AMOUNT,20)",
    "vs_250": "DIV(STDDEV(VOLUME,6),STDDEV(VOLUME,250))",
    "vs_500": "DIV(STDDEV(VOLUME,6),STDDEV(VOLUME,500))",
    "vs_756": "DIV(STDDEV(VOLUME,6),STDDEV(VOLUME,756))",
}


def build_raw_legs(panels: dict) -> dict:
    """未定向、未排名的原始腿（>39+3 条）。"""
    C = panels["close"].astype("float32")
    O = panels["open"].astype("float32")
    H = panels["high"].astype("float32")
    L = panels["low"].astype("float32")
    V = panels["volume"].astype("float32")
    A = panels["amount"].astype("float32")
    T = (panels["turn"] if "turn" in panels else panels["turnover"]).astype("float32")
    vwap = panels["vwap"].astype("float32") if "vwap" in panels else (A * 10.0 / V)
    ret1 = C.pct_change(fill_method=None)
    hl = (H - L) / C
    intr = (C - O) / O
    drift = (C - vwap) / vwap

    raw: dict[str, pd.DataFrame] = {}
    raw["t_lvl"] = -T
    raw["t_ma5"] = -T.rolling(5).mean()
    raw["t_ma20"] = -T.rolling(20).mean()
    raw["t_rel_ma5_60"] = -(T.rolling(5).mean() / T.rolling(60).mean())
    raw["t_rel_ma20_60"] = -(T.rolling(20).mean() / T.rolling(60).mean())
    raw["t_std10"] = -T.rolling(10).std()
    raw["t_std20"] = -T.rolling(20).std()
    raw["t_std10_60"] = -(T.rolling(10).std() / T.rolling(60).std())
    raw["t_std20_60"] = -(T.rolling(20).std() / T.rolling(60).std())
    raw["v_std10_60"] = -(V.rolling(10).std() / V.rolling(60).std())
    raw["v_std20_60"] = -(V.rolling(20).std() / V.rolling(60).std())
    raw["a_std20_60"] = -(A.rolling(20).std() / A.rolling(60).std())
    raw["v_ma5_60"] = -(V.rolling(5).mean() / V.rolling(60).mean())
    raw["v_ma20_60"] = -(V.rolling(20).mean() / V.rolling(60).mean())
    raw["retrev5"] = -(C / C.shift(5) - 1)
    raw["retrev10"] = -(C / C.shift(10) - 1)
    raw["retrev20"] = -(C / C.shift(20) - 1)
    raw["retmom60"] = C / C.shift(60) - 1
    raw["cstd20"] = -C.rolling(20).std()
    raw["cstd20_60"] = -(C.rolling(20).std() / C.rolling(60).std())
    raw["retstd20"] = -ret1.rolling(20).std()
    raw["retstd20_60"] = -(ret1.rolling(20).std() / ret1.rolling(60).std())
    raw["maxret20"] = -ret1.rolling(20).max()
    raw["minret20"] = -ret1.rolling(20).min()
    raw["hl20"] = -hl.rolling(20).mean()
    raw["amp20"] = -(H.rolling(20).max() / L.rolling(20).min() - 1)
    raw["intr5"] = -intr.rolling(5).mean()
    raw["intr20"] = -intr.rolling(20).mean()
    raw["drift5"] = -drift.rolling(5).mean()
    raw["drift20"] = -drift.rolling(20).mean()
    raw["closepos20"] = -(C - L.rolling(20).min()) / (H.rolling(20).max() - L.rolling(20).min())
    raw["pvcorr20"] = H.astype("float64").rolling(20).corr(V.astype("float64")).astype("float32")
    raw["vretcorr20"] = ret1.rolling(20).corr(V.rolling(1).mean())
    raw["amihud20"] = -(ret1.abs() / A).rolling(20).mean()
    raw["amt60"] = -A.rolling(60).mean()
    raw["skew20"] = -ret1.rolling(20).skew()
    raw["downup"] = -(ret1.where(ret1 < 0, 0.0).rolling(20).std() / ret1.where(ret1 > 0, 0.0).rolling(20).std())
    raw["vdiff"] = -(V - V.rolling(20).mean()) / V.rolling(20).std()
    raw["tdiff"] = -(T - T.rolling(20).mean()) / T.rolling(20).std()
    # volstab 长窗腿（窗口 ≤756，平台可完整预热；经 2026-09-29 三因子实测确认 750 窗可用）
    raw["vs_250"] = -(V.rolling(6).std() / V.rolling(250).std())
    raw["vs_500"] = -(V.rolling(6).std() / V.rolling(500).std())
    raw["vs_756"] = -(V.rolling(6).std() / V.rolling(756).std())
    return raw


def build_composite(panels: dict, signed: dict) -> pd.DataFrame:
    """按 {腿: ±1} 构建复合：mean_i( sign_i · rank_pct(leg_i) )。"""
    raw = build_raw_legs(panels)
    comp = None
    for name, sign in signed.items():
        df = (float(sign) * raw[name]).rank(axis=1, pct=True).astype("float32")
        comp = df if comp is None else comp + df
    if comp is None:
        raise ValueError("empty composite")
    return comp / float(len(signed))
