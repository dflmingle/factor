"""Extended pool search over every locally reproducible 10-day factor.

The earlier screen used ten representative members.  The qualitygate3 catalog
marks 149 records as reproducible, of which 54 distinct handlers have a
ten-day platform record.  This script builds those signals locally (cached to
``built_signals.pkl``), then evaluates single-seat swaps and single additions
against the current best pool using the documented score shape:

    Comb = 0.20 * NA + 0.35 * NB_proxy + 0.45 * NC

NA uses each member's saved platform A input, NB_proxy the composite's own
recent-window IC statistics, and NC the composite's full-window return,
turnover, Sharpe and drawdown.  Offline only.
"""
from __future__ import annotations

import glob
import json
import pickle
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import exhaustive_representative_combination as e  # noqa: E402
from financial_factor_local import load_financial_cache  # noqa: E402

CATALOG = Path(
    "quantlab/.quantlab/cache/research/cn_equity/reports/"
    "all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_"
    "turnoverdiag1_qualitygate3/all_factor_local_compare.json"
)
SIGNALS = Path("research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl")
OUT = Path("research_reports/platform_alignment/pool-extended-search-20260922")
CACHE = OUT / "built_signals.pkl"
SEED = [
    "size_only",
    "impact60",
    "chip250",
    "book_to_market_lf_minus_size",
    "book_to_market_lf_plus_impact",
]

RUN_FILES: dict[str, Path] = {}
for _pattern in ("*.results/*.json", "*/*.results/*.json", "*/*/*.results/*.json"):
    for _path in glob.glob(_pattern):
        RUN_FILES.setdefault(Path(_path).stem, Path(_path))


def _num(value):
    if value is None:
        return None
    text = str(value).strip()
    try:
        return float(text.rstrip("%")) / 100 if text.endswith("%") else float(text)
    except ValueError:
        return None


def _indicators(payload):
    def walk(obj):
        if isinstance(obj, dict):
            if isinstance(obj.get("factor_data_analysis"), list):
                return obj["factor_data_analysis"]
            for value in obj.values():
                found = walk(value)
                if found:
                    return found
        if isinstance(obj, str) and obj.lstrip().startswith("{"):
            try:
                return walk(json.loads(obj))
            except ValueError:
                return None
        return None

    rows = walk(payload)
    if not rows:
        return None
    return {row["indicator"]: row.get("factor1", row.get("factor_value")) for row in rows}


def platform_si(record: dict) -> float | None:
    path = RUN_FILES.get(str(record.get("platform_run_id")))
    if path is None:
        return None
    indicators = _indicators(json.loads(path.read_text()))
    if not indicators:
        return None
    rank_ic, ic_ir = _num(indicators.get("Rank_IC")), _num(indicators.get("IC_IR"))
    direction = str(record.get("platform_factor_direction"))
    win = _num(indicators.get("P(IC<-0.02)")) if direction == "0" else _num(indicators.get("P(IC>0.02)"))
    if None in (rank_ic, ic_ir, win):
        return None
    return abs(rank_ic) * abs(ic_ir) * win


def build_members():
    catalog = json.loads(CATALOG.read_text())["results"]
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in catalog:
        if row.get("local_mining_eligible") and row.get("cycle") == 10 and row.get("handler"):
            grouped[str(row["handler"])].append(row)
    members = []
    for handler, rows in grouped.items():
        best = max(rows, key=lambda r: r.get("platform_net_excess_pct") or -99)
        si = platform_si(best)
        if si is None:
            continue
        members.append(
            dict(
                key=handler,
                handler=handler,
                direction=int(float(best.get("platform_factor_direction") or 1)),
                name=best["name"],
                platform_net=best.get("platform_net_excess_pct"),
                si=si,
            )
        )
    members.sort(key=lambda m: -(m["platform_net"] or -99))
    print(f"members available: {len(members)}", flush=True)

    sf, raw_base, returns, dates = pickle.load(SIGNALS.open("rb"))
    print("loading full-A panel", flush=True)
    frame = e.load_full_a_data(e.DEFAULT_PRICE_ROOT, e.DEFAULT_CAP_ROOT, e.DATA_START, e.END)
    frame = e.select_market_cap(frame, "total_mv").sort_values(["instrument", "date"], ignore_index=True)
    financial = load_financial_cache(e.DEFAULT_FINANCIAL_ROOT)
    mask = frame["date"].isin(dates)

    raw = {}
    built = []
    for member in members:
        handler = member["handler"]
        if handler in raw_base:
            raw[member["key"]] = pd.Series(np.asarray(raw_base[handler], dtype=float))
            built.append(member)
            continue
        try:
            values = e.build_factor(frame, handler, financial=financial, signal_dates=dates)
            raw[member["key"]] = pd.to_numeric(values.loc[mask].reset_index(drop=True), errors="coerce")
            built.append(member)
        except Exception as exc:  # noqa: BLE001 - report and skip unbuildable members
            print(f"  skip {member['name']} [{handler}]: {exc}", flush=True)
    print(f"built locally: {len(built)}", flush=True)

    candidates = [dict(key=m["key"], handler=m["handler"], direction=m["direction"], name=m["name"]) for m in built]
    scores = e._competition_cross_sectional_scores(sf, raw, candidates)
    OUT.mkdir(parents=True, exist_ok=True)
    with CACHE.open("wb") as fh:
        pickle.dump(dict(built=built, scores=scores), fh)
    return sf, returns, dates, built, scores


def run_search(sf, returns, dates, built, scores):
    keys = [m["key"] for m in built]
    si = {m["key"]: m["si"] for m in built}
    blocks = e._build_blocks(sf, scores, returns, dates, keys)
    ds, offsets, fs, fr, fi, _ = e._flatten_blocks(blocks, len(keys))

    def evaluate(selection: list[str]) -> dict | None:
        idx = [keys.index(k) for k in selection]
        if not idx:
            return None
        combo_mask = np.zeros(len(keys), dtype=bool)
        combo_mask[idx] = True
        masks = combo_mask.reshape(1, -1)
        sizes = np.array([len(idx)], dtype=np.int64)
        held, gross, turn, counts, valid = e._evaluate_combinations_numba(fs, fr, fi, offsets, masks, sizes)
        summary = {}
        for window, wmask in (
            ("full", np.ones(len(ds), bool)),
            ("test", ds > e.TRAIN_END.to_datetime64()),
            ("recent", ds >= e.RECENT_START.to_datetime64()),
        ):
            summary[window] = e._summary(held[0], gross[0], turn[0], counts[0], valid[0].astype(bool), ds, 10, window, wmask)
        rank_ics, ics = e._exact_period_ics(tuple(idx), blocks)
        recent_mask = ds >= e.RECENT_START.to_datetime64()
        r = rank_ics[recent_mask]
        c = ics[recent_mask]
        r = r[np.isfinite(r)]
        c = c[np.isfinite(c)]
        s_recent = 0.0
        if len(r) and len(c) > 2 and np.std(c, ddof=1) > 0:
            s_recent = (
                abs(float(np.mean(r)))
                * abs(float(np.mean(c) / np.std(c, ddof=1)))
                * float(np.mean(np.abs(c) > 0.02))
            )
        full = summary["full"]
        raw_c = (
            max(full["net_excess_pct"], 0)
            / 100
            / max(2 * full["turnover_pct"] / 100, 0.3)
            * full["sharpe_after_cost"]
            * (1 - 1.2 * full["max_drawdown_pct"] / 100)
        )
        raw_a = float(np.mean([si[k] for k in selection]))
        na = min(raw_a / 0.08, 1.0)
        nb = min(s_recent / 0.06, 1.0)
        nc = min(max(raw_c / 0.6, 0), 1.0)
        return dict(
            selection="+".join(selection),
            size=len(selection),
            comb=0.20 * na + 0.35 * nb + 0.45 * nc,
            na=na,
            nb=nb,
            nc=nc,
            net=full["net_excess_pct"],
            turnover=full["turnover_pct"],
            test=summary["test"]["net_excess_pct"],
            recent=summary["recent"]["net_excess_pct"],
            s_recent=s_recent,
            raw_a=raw_a,
        )

    seed = [k for k in SEED if k in keys]
    base = evaluate(seed)
    print(
        f"\nseed {seed}: Comb {base['comb']:.3f} (NA {base['na']:.3f} NB {base['nb']:.3f} NC {base['nc']:.3f}) "
        f"net {base['net']:.2f}% turnover {base['turnover']:.2f}%",
        flush=True,
    )
    results = [dict(base, change="seed")]
    for seat in seed:
        for member in built:
            if member["key"] in seed:
                continue
            outcome = evaluate([k for k in seed if k != seat] + [member["key"]])
            if outcome:
                results.append(dict(outcome, change=f"swap {seat} -> {member['key']}"))
    for member in built:
        if member["key"] in seed:
            continue
        outcome = evaluate(seed + [member["key"]])
        if outcome:
            results.append(dict(outcome, change=f"add {member['key']}"))
    results.sort(key=lambda r: -r["comb"])
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(OUT / "extended_search.csv", index=False)
    print(f"\nEvaluated {len(results)} pools. Top 18 by Comb:")
    for row in results[:18]:
        print(
            f"  {row['comb']:.3f} | NA {row['na']:.3f} NB {row['nb']:.3f} NC {row['nc']:.3f} | "
            f"net {row['net']:5.2f}% turn {row['turnover']:5.2f}% test {row['test']:5.2f}% recent {row['recent']:5.2f}% | "
            f"{row['change']}"
        )


def main() -> None:
    sf, _raw_base, returns, dates = pickle.load(SIGNALS.open("rb"))
    if CACHE.exists():
        cached = pickle.load(CACHE.open("rb"))
        print(f"reusing cached signals ({len(cached['built'])} members)")
        run_search(sf, returns, dates, cached["built"], cached["scores"])
        return
    sf, returns, dates, built, scores = build_members()
    run_search(sf, returns, dates, built, scores)


if __name__ == "__main__":
    main()
