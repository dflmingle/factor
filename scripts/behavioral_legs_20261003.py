# -*- coding: utf-8 -*-
"""行为金融腿库（2026-10-03，本地零平台算力初筛）。

在 legmix_next_legs_20260929.build_raw_legs（39+3 条）基础上新增 9 条行为金融腿。
所有腿都核对过平台算子可平移（operators.md：TS_MAX / TS_SKEW / SUMIF / DELAY / MA / SUM 等）。

腿与文献：
  near52w      52 周高点接近度（George & Hwang 2004，锚定/反应不足）
  mom250_20    12-1 动量（Jegadeesh & Titman 1993）
  on20         隔夜收益反转（Lou, Polk & Skouras 2019）
  on_minus_id  隔夜−日内收益差（同上，"tug of war"）
  cgo500       资本利得悬置/处置效应（Grinblatt & Han 2005，换手加权参考成本价）
  limitup20    涨停/极端收益频率（彩票偏好、关注效应；Bali et al. 的频次版）
  illq_t20     换手版 Amihud 非流动性（Amihud 2002 的 turnover 分母变体）
  vwt20        成交量加权收益（资金流/羊群代理）
  skew60       长窗收益率偏度（彩票偏好，Boyer et al. 2010）
"""
from __future__ import annotations

import pandas as pd

from legmix_next_legs_20260929 import build_raw_legs as build_base


def build_behavioral_legs(panels: dict) -> dict:
    C = panels["close"].astype("float32")
    O = panels["open"].astype("float32")
    H = panels["high"].astype("float32")
    V = panels["volume"].astype("float32")
    A = panels["amount"].astype("float32")
    T = (panels["turn"] if "turn" in panels else panels["turnover"]).astype("float32")
    vwap = panels["vwap"].astype("float32") if "vwap" in panels else (A * 10.0 / V)
    ret1 = C.pct_change(fill_method=None)

    ret64 = ret1.astype("float64")
    T64 = T.astype("float64")
    V64 = V.astype("float64")
    vwap64 = vwap.astype("float64")

    raw: dict[str, pd.DataFrame] = {}
    raw["near52w"] = (C / H.rolling(250).max()).astype("float32")
    raw["mom250_20"] = (C.shift(20) / C.shift(250) - 1.0).astype("float32")

    on = O / C.shift(1) - 1.0
    idr = C / O - 1.0
    raw["on20"] = (-on.rolling(20).mean()).astype("float32")
    raw["on_minus_id"] = (on.rolling(20).mean() - idr.rolling(20).mean()).astype("float32")

    ref = (T64 * vwap64).rolling(500).sum() / T64.rolling(500).sum()
    raw["cgo500"] = (C.astype("float64") / ref - 1.0).astype("float32")

    raw["limitup20"] = (-(ret1 >= 0.095).astype("float32").rolling(20).sum()).astype("float32")
    raw["illq_t20"] = (-(ret1.abs() / T).rolling(20).mean()).astype("float32")
    raw["vwt20"] = ((V64 * ret64).rolling(20).sum() / V64.rolling(20).sum()).astype("float32")
    raw["skew60"] = (-ret1.rolling(60).skew()).astype("float32")
    return raw


def build_all(panels: dict) -> dict:
    """原腿库 + 行为金融腿（键不冲突时后者覆盖）。"""
    raw = build_base(panels)
    raw.update(build_behavioral_legs(panels))
    return raw