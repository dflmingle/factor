#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify platform formula text against the local composite (side line, zero compute).

Emulates CLOSE/OPEN/VWAP/MA/STD/STDDEV/RETURNS/RANK with pandas and checks that
each candidate formula in a candidates.txt reproduces the corresponding local
composite from the legmix_next leg library (per-date cross-sectional rank corr
~ 1.0), i.e. the W/S -> platform-formula transcription is faithful.

Usage:
  python scripts/_alphagen_formula_verify_20261002.py <candidates.txt> [--specs specs_alphagen.json]
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from legmix_next_legs_20260929 import build_raw_legs  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PANELS = ROOT / "research_reports/platform_alignment/e-decomp-20260929/panels_cache.pkl"
DEFAULT_SPECS = ROOT / "research_reports/platform_alignment/alphagen-pool-opt-20261002/specs_alphagen.json"


def parse_candidates(path: Path):
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("~")]
        if len(parts) != 3:
            raise ValueError(f"bad candidate line: {raw!r}")
        out.append((parts[0], parts[1], parts[2]))
    return out


def build_ns(panels: dict) -> dict:
    close = panels["close"].astype("float64")
    open_ = panels["open"].astype("float64")
    high = panels["high"].astype("float64")
    low = panels["low"].astype("float64")
    volume = panels["volume"].astype("float64")
    amount = panels["amount"].astype("float64")
    turnover = (panels["turn"] if "turn" in panels else panels["turnover"]).astype("float64")
    vwap = (panels["vwap"].astype("float64") if "vwap" in panels
            else amount * 10.0 / volume)

    def RANK(x):
        return x.rank(axis=1, pct=True)

    def MA(x, n):
        return x.rolling(int(n)).mean()

    def STD(x, n):
        return x.rolling(int(n)).std()

    def STDDEV(x, n):
        return x.rolling(int(n)).std()

    def RETURNS(x, n):
        return x / x.shift(int(n)) - 1.0

    ns = dict(CLOSE=close, OPEN=open_, HIGH=high, LOW=low, VOLUME=volume,
              AMOUNT=amount, TURNOVER=turnover, VWAP=vwap,
              RANK=RANK, MA=MA, STD=STD, STDDEV=STDDEV, RETURNS=RETURNS, ABS=abs)
    return ns


def local_composite(raw_legs: dict, spec: dict) -> pd.DataFrame:
    if spec["name"].endswith("S"):
        return _signed(raw_legs, spec["signed"])
    return _weighted(raw_legs, spec["signed"])


def _signed(raw_legs: dict, signed: dict) -> pd.DataFrame:
    comp = None
    for name, sign in signed.items():
        part = (float(sign) * raw_legs[name]).rank(axis=1, pct=True).astype("float32")
        comp = part if comp is None else comp + part
    return (comp / float(len(signed))).astype("float32")


def _weighted(raw_legs: dict, weights: dict) -> pd.DataFrame:
    comp = None
    for name, weight in weights.items():
        part = raw_legs[name].rank(axis=1, pct=True).astype("float32") * float(weight)
        comp = part if comp is None else comp + part
    return (comp / len(weights)).astype("float32")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidates")
    ap.add_argument("--specs", default=str(DEFAULT_SPECS))
    args = ap.parse_args()

    cands = parse_candidates(Path(args.candidates))
    specs = {s["name"]: s for s in json.loads(Path(args.specs).read_text(encoding="utf-8"))}
    panels = pickle.load(PANELS.open("rb"))
    raw_legs = build_raw_legs(panels)
    ns = build_ns(panels)

    ok = True
    for name, formula, direction in cands:
        spec = specs[name.split("-")[0]]
        local = local_composite(raw_legs, spec)
        emu = eval(formula, {"__builtins__": {}}, ns)
        if not isinstance(emu, pd.DataFrame):
            emu = pd.DataFrame(emu)
        common_idx = local.index.intersection(emu.index)
        common_cols = local.columns.intersection(emu.columns)
        a = local.loc[common_idx, common_cols].to_numpy(dtype="float64")
        b = np.asarray(emu.loc[common_idx, common_cols], dtype="float64")
        corrs = []
        for i in range(a.shape[0]):
            x, y = a[i], b[i]
            m = np.isfinite(x) & np.isfinite(y)
            if int(m.sum()) < 50:
                continue
            xr = pd.Series(x[m]).rank().to_numpy()
            yr = pd.Series(y[m]).rank().to_numpy()
            corrs.append(float(np.corrcoef(xr, yr)[0, 1]))
        arr = np.asarray(corrs)
        verdict = "PASS" if arr.min() > 0.999 else "FAIL"
        if verdict == "FAIL":
            ok = False
        print(f"[{verdict}] {name}: rank-corr mean {arr.mean():.6f} min {arr.min():.6f} "
              f"(days {arr.size}, dir {direction})")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
