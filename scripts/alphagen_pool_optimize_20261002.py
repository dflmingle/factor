#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AlphaGen pool optimiser (2026-10-02, side line, zero platform compute).

Ports the AlphaPROBE-bundled `alphagen` pool objective to our local panels
(no qlib / StockData needed):

    loss(w) = w^T IC_mut w - 2 w^T IC_ret + 1 + alpha * ||w||_1
    Adam(lr=5e-4) until 500 non-improving steps (best-IC weights kept)

plus a deterministic greedy forward selector (capacity <= 6, weights
re-optimised inside every trial).  Candidate library: the five live seats
from the 09-25 rebuilt payload, the current 5th seat LAMD10-K5V2 rebuilt
from the platform formula, and the 42 legmix legs (rank pct, directions
left to the optimiser).

Usage (easyrl4rec env only; memory watchdog aborts at 9.5 GB):
  D:\\anaconda3\\envs\\easyrl4rec\\python.exe scripts/alphagen_pool_optimize_20261002.py opt
  D:\\anaconda3\\envs\\easyrl4rec\\python.exe scripts/alphagen_pool_optimize_20261002.py ledger --limit 6
"""
from __future__ import annotations

import argparse
import gc
import json
import pickle
import sys
import threading
import time
from itertools import count
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
from legmix_next_legs_20260929 import build_raw_legs  # noqa: E402
OUT = ROOT / "research_reports/platform_alignment/alphagen-pool-opt-20261002"
REBUILD = ROOT / "research_reports/platform_alignment/ab-batch-20260925/seat_panels_rebuilt.pkl"
PANELS = ROOT / "research_reports/platform_alignment/e-decomp-20260929/panels_cache.pkl"
TRAIN_END = pd.Timestamp("2024-09-06")
MEM_LIMIT_GB = 9.5
SEATS = ["size_only", "impact60", "t10_size_plus_impact_bm",
         "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]
SWAPPED_OUT = "book_to_market_lf_plus_impact"   # replaced 09-30 by LAMD10-K5V2
LAMD = "LAMD10-K5V2"
A_UNIT_POOLRULE = 40000.0 * 1.1 * 0.20 * 12.5 / 6.0
ALPHAS = [5e-3, 2e-2, 5e-2, 1e-1]
T0 = time.time()
_ORIG_STDOUT = sys.stdout
_ORIG_STDOUT_BUFFER = getattr(sys.stdout, "buffer", None)
_KEEP_STDOUT = []


def log(msg: str) -> None:
    print(f"[{time.time() - T0:7.1f}s] {msg}", flush=True)


def _watchdog(stop: threading.Event) -> None:
    proc = psutil.Process()
    while not stop.wait(10):
        rss = proc.memory_info().rss / 1e9
        if rss > MEM_LIMIT_GB:
            log(f"!! watchdog: RSS {rss:.1f} GB > {MEM_LIMIT_GB} GB, aborting")
            import os
            os._exit(3)


def start_watchdog() -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=_watchdog, args=(stop,), daemon=True).start()
    return stop


# ----------------------------------------------------------------------------
# data loading / wide panels
# ----------------------------------------------------------------------------
def load_payload() -> dict:
    payload = pickle.load(REBUILD.open("rb"))
    log(f"payload: scores {payload['scores'].shape}, dates {len(payload['dates'])}")
    return payload


def build_grid(payload: dict):
    dates = [pd.Timestamp(d) for d in payload["dates"]]
    sf = payload["signal_frame"]
    stocks = sorted(sf["instrument"].astype(str).unique())
    elig = (sf.assign(_v=1.0)
              .pivot(index="date", columns="instrument", values="_v")
              .reindex(index=dates, columns=stocks)
              .notna().to_numpy())
    tgt = (payload["returns"]
           .pivot(index="date", columns="instrument", values="forward_return")
           .reindex(index=dates, columns=stocks)
           .astype("float32"))
    log(f"grid: {len(dates)} signal dates x {len(stocks)} stocks")
    return dates, stocks, tgt, elig


def seats_wide(payload: dict, dates, stocks) -> dict:
    sf = payload["signal_frame"]
    out = {}
    for seat, series in payload["raw"].items():
        frame = sf.copy()
        frame["_v"] = series.to_numpy(dtype=float)
        out[seat] = (frame.pivot(index="date", columns="instrument", values="_v")
                     .reindex(index=dates, columns=stocks)
                     .astype("float32"))
    return out


def lamd10_k5v2_components(panels: dict) -> dict:
    """Raw (pre-rank) components of the platform formula, full daily grid."""
    C = panels["close"].astype("float32")
    O = panels["open"].astype("float32")
    A = panels["amount"].astype("float32")
    V = panels["volume"].astype("float32")
    T = (panels["turn"] if "turn" in panels else panels["turnover"]).astype("float32")
    ret1 = C.pct_change(fill_method=None)
    return {
        "amt60": -A.rolling(60).mean(),
        "intr20": -((C - O) / O).rolling(20).mean(),
        "tstd20": -T.rolling(20).std(),
        "amihud20": (ret1.abs() / A).rolling(20).mean(),
        "vs756": -(V.rolling(6).std() / V.rolling(756).std()),
    }


def lamd10_k5v2_slice(panels: dict, dates, stocks) -> pd.DataFrame:
    comps = lamd10_k5v2_components(panels)
    ranks = [comps[k].reindex(index=dates, columns=stocks)
             .rank(axis=1, pct=True).astype("float32")
             for k in ("amt60", "intr20", "tstd20", "amihud20", "vs756")]
    mixed = (ranks[0] + ranks[1] + ranks[2] + ranks[3]) / 5.0 + ranks[4] / 5.0
    del comps, ranks
    gc.collect()
    return mixed


def legs_wide(panels: dict, dates, stocks) -> dict:
    from legmix_next_legs_20260929 import build_raw_legs
    raw = build_raw_legs(panels)
    out = {}
    for name, frame in raw.items():
        sliced = frame.reindex(index=dates, columns=stocks)
        out[name] = sliced.rank(axis=1, pct=True).astype("float32")
        del sliced
    n = len(out)
    del raw
    gc.collect()
    log(f"legs ready: {n}")
    return out


# ----------------------------------------------------------------------------
# alphagen port (pure torch, masked)
# ----------------------------------------------------------------------------
def masked_norm(x: torch.Tensor) -> torch.Tensor:
    """Cross-sectional z-score per day, NaN kept (alphagen _normalize_by_day)."""
    fin = torch.isfinite(x)
    n = fin.sum(dim=1, keepdim=True).clamp_min(1)
    mean = torch.where(fin, x, torch.zeros_like(x)).sum(dim=1, keepdim=True) / n
    dev = torch.where(fin, x - mean, torch.zeros_like(x))
    std = (dev * dev).sum(dim=1, keepdim=True).div(n).sqrt().clamp_min(1e-12)
    return (x - mean) / std


def batch_pearsonr(x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    """Masked per-day Pearson correlation (port of alphagen.utils.correlation)."""
    mask = torch.isfinite(x) & torch.isfinite(y)
    xs = torch.where(mask, x, torch.zeros_like(x))
    ys = torch.where(mask, y, torch.zeros_like(y))
    n = mask.sum(dim=1, keepdim=True).clamp_min(1)
    mx = xs.sum(dim=1, keepdim=True) / n
    my = ys.sum(dim=1, keepdim=True) / n
    vx = (xs * xs).sum(dim=1, keepdim=True) / n - mx * mx
    vy = (ys * ys).sum(dim=1, keepdim=True) / n - my * my
    cov = (xs * ys).sum(dim=1, keepdim=True) / n - mx * my
    den = (vx.clamp_min(0).sqrt() * vy.clamp_min(0).sqrt()).clamp_min(1e-9)
    r = cov / den
    r[(vx < 1e-12) | (vy < 1e-12)] = 0.0
    r[~torch.isfinite(r)] = 0.0
    return r.squeeze(1)


def day_matrix(values: list, target: torch.Tensor):
    """Per-day pearson IC vs target and pairwise day corr between candidates."""
    n = len(values)
    d = int(target.shape[0])
    day_ic = np.zeros((n, d))
    pair_day = np.zeros((n, n, d))
    for i, value in enumerate(values):
        series = batch_pearsonr(value, target)
        day_ic[i] = series.numpy()
        pair_day[i, i] = 1.0
    for i in range(n):
        for j in range(i + 1, n):
            series = batch_pearsonr(values[i], values[j]).numpy()
            pair_day[i, j] = pair_day[j, i] = series
    return day_ic, pair_day


def window_matrices(day_ic, pair_day, rows: np.ndarray):
    singles = day_ic[:, rows].mean(axis=1)
    mut = pair_day[:, :, rows].mean(axis=2)
    np.fill_diagonal(mut, 1.0)
    return singles, mut


def optimize_weights(singles, mut, idx, alpha, lr=5e-4, n_iter=500) -> np.ndarray:
    """alpha ver. of AlphaPool._optimize (force_load initialises w = single ICs)."""
    ics_ret = torch.from_numpy(np.asarray(singles[idx], dtype=np.float32))
    ics_mut = torch.from_numpy(np.asarray(mut[np.ix_(idx, idx)], dtype=np.float32))
    init = np.asarray(singles[idx], dtype=np.float32).copy()
    weights = torch.from_numpy(init).requires_grad_()
    optim = torch.optim.Adam([weights], lr=lr)
    loss_ic_min = 1e9 + 7
    best_weights = weights.detach().numpy().copy()
    iter_cnt = 0
    for it in count():
        ret_ic_sum = (weights * ics_ret).sum()
        mut_ic_sum = (torch.outer(weights, weights) * ics_mut).sum()
        loss_ic = mut_ic_sum - 2 * ret_ic_sum + 1
        loss_ic_curr = loss_ic.item()
        loss_l1 = torch.norm(weights, p=1)
        loss = loss_ic + alpha * loss_l1
        optim.zero_grad()
        loss.backward()
        optim.step()
        if loss_ic_min - loss_ic_curr > 1e-6:
            iter_cnt = 0
        else:
            iter_cnt += 1
        if loss_ic_curr < loss_ic_min:
            best_weights = weights.detach().numpy().copy()
            loss_ic_min = loss_ic_curr
        if iter_cnt >= n_iter or it >= 10000:
            break
    return best_weights


def normalise_weights(weights: np.ndarray) -> np.ndarray:
    total = float(np.abs(weights).sum())
    return weights / total if total > 1e-12 else weights


def ensemble_tensor(values: list, idx, weights) -> torch.Tensor:
    acc = None
    for k, i in enumerate(idx):
        part = values[i] * float(weights[k])
        acc = part if acc is None else acc + part
    return masked_norm(acc)


def ensemble_ic(values: list, idx, weights, target: torch.Tensor) -> float:
    return float(batch_pearsonr(ensemble_tensor(values, idx, weights), target).mean())


def greedy_select(names, values, target, singles, mut, capacity=6, alpha=5e-3):
    remaining = list(range(len(names)))
    chosen: list[int] = []
    path = []
    for _ in range(capacity):
        best = None
        for cand in remaining:
            idx = chosen + [cand]
            weights = optimize_weights(singles, mut, idx, alpha)
            score = ensemble_ic(values, idx, weights, target)
            if best is None or score > best[0]:
                best = (score, cand, weights)
        score, cand, weights = best
        chosen.append(cand)
        remaining.remove(cand)
        refit = optimize_weights(singles, mut, chosen, alpha)
        path.append({
            "step": len(chosen),
            "add": names[cand],
            "trial_ic": score,
            "refit_ic": ensemble_ic(values, chosen, refit, target),
            "members": [names[i] for i in chosen],
            "weights": [float(x) for x in refit],
        })
    return chosen, path
# ----------------------------------------------------------------------------
# wide-block IC stats / combo assembly
# ----------------------------------------------------------------------------
def stats_block(x: np.ndarray, y: np.ndarray, elig: np.ndarray, rows: np.ndarray) -> dict:
    xs = np.where(elig, x, np.nan)
    ys = np.where(elig, y, np.nan)
    rics, pcs = [], []
    for i in range(xs.shape[0]):
        if not rows[i]:
            continue
        a, b = xs[i], ys[i]
        m = np.isfinite(a) & np.isfinite(b)
        if int(m.sum()) < 100:
            continue
        ar = pd.Series(a[m]).rank().to_numpy()
        br = pd.Series(b[m]).rank().to_numpy()
        rics.append(float(np.corrcoef(ar, br)[0, 1]))
        pcs.append(float(np.corrcoef(a[m], b[m])[0, 1]))
    if not rics:
        return {}
    arr = np.asarray(rics)
    mean = float(arr.mean())
    std = float(arr.std(ddof=1)) if arr.size > 1 else 0.0
    ir = mean / std if std > 0 else 0.0
    win = float((arr > 0.02).mean()) if mean >= 0 else float((arr < -0.02).mean())
    return {"rank_ic": mean, "ric_ir": ir, "win": win,
            "pearson_ic": float(np.mean(pcs)), "n": int(arr.size)}


def combo_wide(cands: dict, pairs) -> pd.DataFrame:
    comp = None
    for name, weight in pairs:
        part = cands[name] * float(weight)
        comp = part if comp is None else comp + part
    return comp


def top_pairs(names, idx, weights, limit=6):
    pairs = [(names[i], float(weights[k])) for k, i in enumerate(idx)
             if abs(float(weights[k])) > 1e-6]
    pairs.sort(key=lambda item: -abs(item[1]))
    return pairs[:limit]


def combo_record(cid, source, pairs, cands, target, elig, dates):
    total = sum(abs(w) for _, w in pairs)
    pairs_n = [(n, w / total) for n, w in pairs] if total > 1e-12 else list(pairs)
    arr = combo_wide(cands, pairs_n).to_numpy(dtype=np.float32)
    rows_full = np.ones(len(dates), dtype=bool)
    rows_train = np.array([d <= TRAIN_END for d in dates])
    stats = {
        "full": stats_block(arr, target, elig, rows_full),
        "train": stats_block(arr, target, elig, rows_train),
        "val": stats_block(arr, target, elig, ~rows_train),
    }
    signed = [(n, float(np.sign(w))) for n, w in pairs_n]
    signed = [(n, w) for n, w in signed if w != 0.0]
    stats_s = stats_block(combo_wide(cands, signed).to_numpy(dtype=np.float32),
                          target, elig, rows_full)
    return dict(id=cid, source=source, kind="weighted",
                pairs=[[n, float(w)] for n, w in pairs_n],
                signed_pairs=[[n, float(w)] for n, w in signed],
                stats=stats, signed_full=stats_s)


def max_seat_corr(values_norm, names, pairs, seat_idx):
    idx = [names.index(n) for n, _ in pairs]
    weights = np.array([float(w) for _, w in pairs])
    ens = ensemble_tensor(values_norm, idx, weights)
    corrs = [float(batch_pearsonr(ens, values_norm[j]).mean()) for j in seat_idx]
    return max(abs(c) for c in corrs) if corrs else float("nan")


# ----------------------------------------------------------------------------
# stage: opt
# ----------------------------------------------------------------------------
def stage_opt(args) -> int:
    start_watchdog()
    payload = load_payload()
    dates, stocks, target_wide, elig = build_grid(payload)
    target_np = target_wide.to_numpy(dtype=np.float32)
    panels = pickle.load(PANELS.open("rb"))
    log("panels ready")
    cands: dict[str, pd.DataFrame] = {}
    for name, wide in seats_wide(payload, dates, stocks).items():
        cands[f"seat:{name}"] = wide
    cands[f"mix:{LAMD}"] = lamd10_k5v2_slice(panels, dates, stocks)
    for name, wide in legs_wide(panels, dates, stocks).items():
        cands[f"leg:{name}"] = wide
    del panels
    gc.collect()
    names = list(cands)
    log(f"library: {len(names)} candidates")

    elig_t = torch.from_numpy(elig)
    values_norm = []
    for name in names:
        raw = torch.from_numpy(cands[name].to_numpy(dtype=np.float32).copy())
        values_norm.append(masked_norm(raw.masked_fill(~elig_t, float("nan"))))
    target_t = masked_norm(
        torch.from_numpy(target_np.copy()).masked_fill(~elig_t, float("nan")))
    day_ic, pair_day = day_matrix(values_norm, target_t)
    log("ic matrices done")

    rows_train = np.array([d <= TRAIN_END for d in dates])
    rows_val = ~rows_train
    singles_tr, mut_tr = window_matrices(day_ic, pair_day, rows_train)
    singles_full, mut_full = window_matrices(day_ic, pair_day, np.ones(len(dates), bool))
    log(f"train dates {int(rows_train.sum())}, val dates {int(rows_val.sum())}")

    seat_idx = [i for i, n in enumerate(names) if n.startswith("seat:")]
    lib_rows = []
    rows_full = np.ones(len(dates), dtype=bool)
    for i, name in enumerate(names):
        arr = cands[name].to_numpy(dtype=np.float32)
        tr = stats_block(arr, target_np, elig, rows_train)
        va = stats_block(arr, target_np, elig, rows_val)
        fu = stats_block(arr, target_np, elig, rows_full)
        lib_rows.append(dict(candidate=name, kind=name.split(":")[0],
                             ric_train=tr.get("rank_ic"), ric_val=va.get("rank_ic"),
                             ric_full=fu.get("rank_ic"), pearson_full=fu.get("pearson_ic"),
                             win_full=fu.get("win"),
                             max_mut_vs_seats=max(abs(mut_full[i, j]) for j in seat_idx)))
    pd.DataFrame(lib_rows).to_csv(OUT / "library_stats.csv", index=False,
                                  encoding="utf-8-sig")

    pure_leg_idx = [i for i, n in enumerate(names) if n.startswith("leg:")]
    combos, weight_rows = [], []
    for tag, subset in (("all", list(range(len(names)))), ("legs", pure_leg_idx)):
        for alpha in ALPHAS:
            w = normalise_weights(optimize_weights(singles_tr, mut_tr, subset, alpha))
            pairs = top_pairs(names, subset, w)
            combos.append(combo_record(f"AG{'A' if tag == 'all' else 'L'}-a{alpha:g}",
                                       f"{tag}_alpha{alpha:g}", pairs, cands,
                                       target_np, elig, dates))
            for i, weight in zip(subset, w):
                weight_rows.append(dict(tag=tag, alpha=alpha, candidate=names[i],
                                        weight=float(weight)))
    pd.DataFrame(weight_rows).to_csv(OUT / "weights_alpha.csv", index=False,
                                     encoding="utf-8-sig")

    greedy_rows = []
    for tag, subset in (("all", list(range(len(names)))), ("legs", pure_leg_idx)):
        subset_names = [names[i] for i in subset]
        subset_values = [values_norm[i] for i in subset]
        chosen, path = greedy_select(
            subset_names, subset_values, target_t,
            singles_tr[subset], mut_tr[np.ix_(subset, subset)], capacity=args.capacity)
        tag_c = "AGA" if tag == "all" else "AGL"
        for entry in path:
            pairs = [(n, w) for n, w in zip(entry["members"], entry["weights"])
                     if abs(w) > 1e-6]
            combos.append(combo_record(f"{tag_c}-g{entry['step']}", f"{tag}_greedy",
                                       pairs, cands, target_np, elig, dates))
            greedy_rows.append(dict(tag=tag, step=entry["step"], add=entry["add"],
                                    trial_ic=entry["trial_ic"], refit_ic=entry["refit_ic"],
                                    members=json.dumps(entry["members"], ensure_ascii=False),
                                    weights=json.dumps([round(x, 6) for x in entry["weights"]])))
    pd.DataFrame(greedy_rows).to_csv(OUT / "greedy_path.csv", index=False,
                                     encoding="utf-8-sig")

    def leg_key(record):
        return frozenset(n for n, _ in record["pairs"] if n.startswith("leg:"))

    leg_combos = [rc for rc in combos
                  if rc["pairs"] and all(n.startswith("leg:") for n, _ in rc["pairs"])]
    ranked, seen = [], []
    for rc in sorted(leg_combos, key=lambda r: -(r["stats"]["val"].get("rank_ic") or -9)):
        key = leg_key(rc)
        if any(len(key & k2) / max(1, len(key | k2)) > 0.65 for k2 in seen):
            continue
        seen.append(key)
        ranked.append(rc)
    for rank, rc in enumerate(ranked, 1):
        rc["agp_id"] = f"AGP{rank:02d}"
        rc["seat_corr_max"] = max_seat_corr(values_norm, names, rc["pairs"], seat_idx)

    specs = []
    for rc in ranked[: args.specs]:
        legs_w = {n.split(":", 1)[1]: round(w, 6) for n, w in rc["pairs"]}
        legs_s = {n.split(":", 1)[1]: w for n, w in rc["signed_pairs"]}
        specs.append({"name": f"{rc['agp_id']}W", "base": "composite", "signed": legs_w})
        specs.append({"name": f"{rc['agp_id']}S", "base": "composite", "signed": legs_s})
    (OUT / "specs_alphagen.json").write_text(
        json.dumps(specs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for rc in combos:
        rc.setdefault("agp_id", "")
    (OUT / "combos.json").write_text(
        json.dumps(combos, ensure_ascii=False, indent=2, default=float) + "\n",
        encoding="utf-8")

    lines = [
        "# AlphaGen pool optimiser - opt stage (2026-10-02, zero platform compute)",
        "",
        f"- library: {len(names)} candidates = 5 seats + {LAMD} + {len(pure_leg_idx)} legs",
        f"- train <= {TRAIN_END.date()} ({int(rows_train.sum())} dates), "
        f"val = rest ({int(rows_val.sum())} dates)",
        "- objective: alphagen AlphaPool loss (Adam, l1) + greedy forward selection",
        "",
        "## Legs-only combos (ranked by valid-window RankIC)",
        "",
        "| id | n | ric_train | ric_val | ric_full | signed_full | max|corr seats| | legs |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for rc in ranked[:14]:
        pairs_txt = "; ".join(f"{n.split(':', 1)[1]}({w:+.2f})" for n, w in rc["pairs"])
        lines.append(
            f"| {rc['agp_id']} | {len(rc['pairs'])} "
            f"| {rc['stats']['train'].get('rank_ic', float('nan')):.4f} "
            f"| {rc['stats']['val'].get('rank_ic', float('nan')):.4f} "
            f"| {rc['stats']['full'].get('rank_ic', float('nan')):.4f} "
            f"| {rc['signed_full'].get('rank_ic', float('nan')):.4f} "
            f"| {rc.get('seat_corr_max', float('nan')):.3f} | {pairs_txt} |")
    lines += ["", "## Greedy paths", "", "| tag | step | add | trial_ic | refit_ic | members |",
              "|---|---:|---|---:|---:|---|"]
    for row in greedy_rows:
        lines.append(f"| {row['tag']} | {row['step']} | {row['add']} | {row['trial_ic']:.4f} "
                     f"| {row['refit_ic']:.4f} | {row['members']} |")
    (OUT / "report_opt.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"opt done; ranked legs-only combos: {[rc['agp_id'] for rc in ranked[:12]]}")
    return 0


# ----------------------------------------------------------------------------
# stage: ledger (market / monthly ledger, seed = live swapf pool)
# ----------------------------------------------------------------------------
def build_panels_local(market) -> dict:
    cache = ROOT / "research_reports/platform_alignment/e-decomp-20260929/panels_cache.pkl"
    if cache.exists():
        log("panels from cache")
        return pickle.load(cache.open("rb"))
    raise FileNotFoundError(f"missing panels cache: {cache}")


def stage_ledger(args) -> int:
    start_watchdog()
    import e_decomp_20260928 as ed
    import exhaustive_representative_combination as e
    _KEEP_STDOUT.append(sys.stdout)

    combos_path = Path(args.combos) if args.combos else OUT / "combos.json"
    combos = json.loads(combos_path.read_text(encoding="utf-8"))
    ranked = [rc for rc in combos
              if rc["pairs"] and all(n.startswith("leg:") for n, _ in rc["pairs"])]
    ranked.sort(key=lambda r: -(r["stats"]["val"].get("rank_ic") or -9))
    picked, seen = [], []
    for rc in ranked:
        train_ric = rc["stats"]["train"].get("rank_ic") or 0.0
        if train_ric < args.min_train:
            continue
        key = frozenset(n for n, _ in rc["pairs"])
        if any(len(key & k2) / max(1, len(key | k2)) > 0.65 for k2 in seen):
            continue
        seen.append(key)
        picked.append(rc)
        if len(picked) >= args.limit:
            break
    log(f"ledger candidates: {[(rc['id'], len(rc['pairs'])) for rc in picked]}")

    payload = pickle.load(REBUILD.open("rb"))
    device = torch.device("cpu")
    market = ed.Market(payload, device)
    panels = build_panels_local(market)
    raw_legs = build_raw_legs(panels)
    eval_dates = [pd.Timestamp(x) for x in market.data._evaluation_dates]
    stocks = [str(x) for x in market.data._stock_ids]
    signal_dates = set(pd.Timestamp(x) for x in market.dates)
    cap_signal = panels["mcap"].reindex(index=[d for d in eval_dates if d in signal_dates])

    def orient(frame):
        panel = frame.reindex(index=eval_dates, columns=stocks).astype("float32")
        values = torch.from_numpy(panel.to_numpy().copy())
        stats = ed.rank_ic_stats(market.context, values)
        chosen = 1
        if not stats or stats["rank_ic"] < 0:
            stats_neg = ed.rank_ic_stats(market.context, -values)
            if stats_neg and (not stats or stats_neg["rank_ic"] > stats["rank_ic"]):
                stats, chosen = stats_neg, -1
        if chosen == -1:
            panel = (-panel).astype("float32")
        return panel, stats, chosen

    lamd = None
    comps = lamd10_k5v2_components(panels)
    for key in ("amt60", "intr20", "tstd20", "amihud20", "vs756"):
        part = comps[key].reindex(index=eval_dates, columns=stocks).rank(axis=1, pct=True)
        lamd = part if lamd is None else lamd + part
    lamd = (lamd / 5.0).astype("float32")
    del comps
    gc.collect()
    lamd_panel, lamd_stats, lamd_dir = orient(lamd)
    lamd_flat = lamd_panel.stack(dropna=False).reindex(market.signal_index)
    lamd_score = e._competition_cross_sectional_scores(
        market.signal_frame, {"lamd": lamd_flat},
        [{"key": "lamd", "handler": "lamd", "direction": 1}])
    base = market.seats.drop(columns=[SWAPPED_OUT])
    seed_frame = pd.concat([base, lamd_score], axis=1)
    seed_keys = list(seed_frame.columns)
    b_s, o_s, fs_s, fr_s = market.make_blocks(seed_frame, seed_keys)
    seed_ledger = market.scenario_ledger(b_s, o_s, fs_s, fr_s,
                                         np.ones(len(seed_keys), dtype=np.int64))
    seed_curve = market.build_daily(seed_ledger)
    seed_table = market.monthly_table(seed_curve, seed_ledger)
    log(f"[seed swapsf 5 seats] E={seed_table.e_term.mean():.4f} NC={seed_table.nc.mean():.3f} "
        f"T={seed_table.turnover_month.mean():.3f}")

    rows = []
    for rc in picked:
        comp = None
        for name, weight in rc["pairs"]:
            leg = name.split(":", 1)[1]
            part = raw_legs[leg].rank(axis=1, pct=True).astype("float32") * float(weight)
            comp = part if comp is None else comp + part
        frame = (comp / len(rc["pairs"])).astype("float32")
        del comp
        panel, stats, chosen = orient(frame)
        flat = panel.stack(dropna=False).reindex(market.signal_index)
        cand_score = e._competition_cross_sectional_scores(
            market.signal_frame, {"cand": flat},
            [{"key": "cand", "handler": "cand", "direction": 1}])
        six_frame = pd.concat([seed_frame, cand_score], axis=1)
        keys6 = seed_keys + ["cand"]
        b6, o6, fs6, fr6 = market.make_blocks(six_frame, keys6)
        led = market.scenario_ledger(b6, o6, fs6, fr6, np.ones(len(keys6), dtype=np.int64))
        curve = market.build_daily(led)
        table = market.monthly_table(curve, led)
        merged = seed_table.merge(table, on=["year", "month"], suffixes=("_seed", "_six"))
        merged["d_e"] = merged.e_term_six - merged.e_term_seed
        merged["d_t"] = merged.turnover_month_six - merged.turnover_month_seed
        merged["d_nc"] = merged.nc_six - merged.nc_seed
        merged["d_c_points"] = 44000.0 * ed.W_C * merged.d_nc
        merged.to_csv(OUT / f"monthly_{rc['agp_id']}.csv", index=False,
                      encoding="utf-8-sig")
        s_local = stats["s_i_rank"]
        d_c = float(merged.d_c_points.mean())
        d_a_uplift = ed.A_UNIT * ed.UPLIFT * (s_local - ed.MEAN_S_LOCAL)
        d_a_poolrule = A_UNIT_POOLRULE * (s_local - ed.MEAN_S_PLAT)
        cs_vals = []
        for d in cap_signal.index:
            if d not in panel.index:
                continue
            a = panel.loc[d].to_numpy(dtype="float64")
            b = cap_signal.loc[d].to_numpy(dtype="float64")
            m = np.isfinite(a) & np.isfinite(b)
            if int(m.sum()) < 200:
                continue
            ar = pd.Series(a[m]).rank().to_numpy()
            br = pd.Series(b[m]).rank().to_numpy()
            cs_vals.append(float(np.corrcoef(ar, br)[0, 1]))
        corr_size = float(np.mean(cs_vals)) if cs_vals else float("nan")
        turn_intrinsic = float(led.turnover[led.valid].mean())
        rows.append(dict(
            id=rc["agp_id"], source=rc["source"], n_legs=len(rc["pairs"]),
            legs=";".join(f"{n.split(':', 1)[1]}:{w:.3f}" for n, w in rc["pairs"]),
            direction=chosen,
            ric_train=rc["stats"]["train"].get("rank_ic"),
            ric_val=rc["stats"]["val"].get("rank_ic"),
            s_i_local=s_local, rank_ic=stats["rank_ic"], ic_ir=stats["rank_ic_ir"],
            win=stats["rank_ic_win"], corr_size=corr_size, turn_intrinsic=turn_intrinsic,
            d_e_mean=float(merged.d_e.mean()), d_t_mean=float(merged.d_t.mean()),
            d_nc_mean=float(merged.d_nc.mean()), d_c_points=d_c,
            d_a_uplift=d_a_uplift, d_comb_uplift=d_a_uplift + d_c,
            d_a_poolrule=d_a_poolrule, d_comb_poolrule=d_a_poolrule + d_c,
            pos_months=int((merged.d_c_points > 0).sum()), months=len(merged)))
        log(f"[{rc['agp_id']}] s_i={s_local:.4f} corrSz={corr_size:+.2f} "
            f"dE={merged.d_e.mean():+.4f} dT={merged.d_t.mean():+.3f} "
            f"dNC={merged.d_nc.mean():+.4f} dC={d_c:+,.0f} dComb_up={d_a_uplift + d_c:+,.0f}")
        del panel, frame, flat, cand_score, six_frame, b6, fs6, fr6, merged
        gc.collect()

    summary = pd.DataFrame(rows).sort_values("d_comb_uplift", ascending=False)
    summary.to_csv(OUT / "ledger_summary.csv", index=False, encoding="utf-8-sig")
    seed_info = dict(seed_e=float(seed_table.e_term.mean()),
                     seed_nc=float(seed_table.nc.mean()),
                     seed_turn_month=float(seed_table.turnover_month.mean()),
                     seed_turn_per_reb=float(seed_ledger.turnover[seed_ledger.valid].mean()),
                     lamd_stats=lamd_stats, lamd_dir=int(lamd_dir))
    (OUT / "seed_summary.json").write_text(
        json.dumps(seed_info, ensure_ascii=False, indent=2, default=float) + "\n",
        encoding="utf-8")
    print(summary.round(3).to_string(index=False))
    log("ledger done")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_opt = sub.add_parser("opt")
    p_opt.add_argument("--capacity", type=int, default=6)
    p_opt.add_argument("--specs", type=int, default=8)
    p_led = sub.add_parser("ledger")
    p_led.add_argument("--limit", type=int, default=6)
    p_led.add_argument("--min-train", type=float, default=0.02)
    p_led.add_argument("--combos", type=str, default="")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.cmd == "opt":
        return stage_opt(args)
    return stage_ledger(args)


if __name__ == "__main__":
    raise SystemExit(main())