# -*- coding: utf-8 -*-
"""技术指标目录腿库（2026-10-03，本地零平台算力）。

字段实现直接复用 pandaai_fields_local._catalog_technical_panel（与平台目录 1:1 命名，
平台公式可直接用裸字段名 + RANK）；日线输入用 e_decomp 的 panels 注入。
方向取自 technical_prelim.csv 的择优方向（leg = 原始值 x direction），
组合腿 = 成员截面 pct-rank 等权平均。

用法（经 _caltech_screen_20261003.py 注入 e_decomp_direct 的 get_raw_legs）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "quantlab" / "third_party" / "AlphaPROBE" / "src"))

import pandaai_fields_local as f  # noqa: E402

LEG_FIELDS = {
    # --- tier 1 (s_i >= .025) ---
    "ct_amt_std20": ("cal_20d_amt_std", -1),
    "ct_amt_ma20": ("cal_20d_amt_ma", -1),
    "ct_davol5": ("davol5", -1),
    "ct_vol_std10": ("cal_10d_vol_std", -1),
    "ct_tor_ratio10_120": ("cal_10d_120d_turnover_ratio", -1),
    # --- tier 2 ---
    "ct_vol3": ("vol3", -1),
    "ct_amp10": ("amp10", -1),
    "ct_vol5": ("vol5", -1),
    "ct_dpo": ("dpo", -1),
    "ct_macd_diff": ("macd_diff", -1),
    "ct_close_avg30": ("cal_30d_close_avg_ratio", 1),
    "ct_ar": ("ar", -1),
    "ct_vol10": ("vol10", -1),
    "ct_vol_std20": ("cal_20d_vol_std", -1),
    "ct_tapi": ("tapi", -1),
    "ct_cyf": ("cyf", -1),
    "ct_pvcorr30": ("cal_30d_price_vol_corr", -1),
    # --- low-churn extras ---
    "ct_obv": ("obv", -1),
    "ct_vol30": ("vol30", -1),
}

COMPOSITES = {
    "ct_comp_activity": ["ct_amt_std20", "ct_amt_ma20", "ct_vol_std10", "ct_vol_std20"],
    "ct_comp_turnover": ["ct_tor_ratio10_120", "ct_vol5", "ct_vol10", "ct_vol3"],
    "ct_comp_topmix": ["ct_amt_std20", "ct_amt_ma20", "ct_vol_std10", "ct_vol_std20",
                       "ct_tor_ratio10_120", "ct_vol5", "ct_davol5", "ct_amp10"],
    "ct_comp_amtdisp": ["ct_amt_std20", "ct_amt_ma20"],
}

_STORES: dict = {}


def _store_for(panels: dict):
    key = id(panels)
    store = _STORES.get(key)
    if store is not None:
        return store

    class _StubData:
        pass

    stub = _StubData()
    dates = [pd.Timestamp(x) for x in panels["close"].index]
    stub._pre_dates = []
    stub._evaluation_dates = dates
    stub._post_dates = []
    stub._pre_padding = 0
    stub.n_stocks = int(panels["close"].shape[1])
    stub._stock_ids = [str(x) for x in panels["close"].columns]
    import torch
    stub.data = torch.zeros((len(dates), 1, stub.n_stocks), dtype=torch.float32)
    frame = pd.DataFrame({"date": [], "instrument": []})
    store = f.PandaAIFieldStore(data=stub, frame=frame, financial_root=None,
                                max_cached_fields=2, max_cached_arrays=4)
    columns = {
        "open_qfq": panels["open"], "open": panels["open"],
        "close_qfq": panels["close"], "close": panels["close"],
        "high_qfq": panels["high"], "high": panels["high"],
        "low_qfq": panels["low"], "low": panels["low"],
        "volume": panels["volume"], "amount": panels["amount"],
        "turnover": panels["turn"] if "turn" in panels else panels["turnover"],
        "total_mv": panels["mcap"],
    }

    def _daily_panel(column, *, fill="none"):
        candidates = (column,) if isinstance(column, str) else column
        for candidate in candidates:
            if candidate in columns:
                result = columns[candidate].to_numpy(dtype=np.float32, copy=True)
                if fill == "ffill":
                    result = pd.DataFrame(result).ffill().to_numpy(dtype=np.float32)
                elif fill == "zero":
                    result = np.nan_to_num(result, nan=0.0)
                return result
        return np.full((len(dates), stub.n_stocks), np.nan, dtype=np.float32)

    store._daily_panel = _daily_panel
    store._daily_available = lambda column: True
    _STORES[key] = store
    return store


def _field(panels: dict, name: str) -> pd.DataFrame:
    store = _store_for(panels)
    array = np.asarray(store._named_array(name), dtype=np.float32)
    return pd.DataFrame(array, index=panels["close"].index, columns=panels["close"].columns)


def build_caltech_legs(panels: dict) -> dict:
    raw = {}
    for leg, (field, direction) in LEG_FIELDS.items():
        raw[leg] = (_field(panels, field) * float(direction)).astype("float32")
    for leg, members in COMPOSITES.items():
        parts = [raw[member].rank(axis=1, pct=True) for member in members]
        raw[leg] = (sum(parts) / float(len(parts))).astype("float32")
    return raw


def build_all(panels: dict) -> dict:
    return build_caltech_legs(panels)