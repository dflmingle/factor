"""Approved bounded offline reconstruction. Never imports platform API clients."""
from __future__ import annotations
import os
for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_key] = "1"
import argparse
import ast
import csv
import gc
import hashlib
import importlib.util
import json
import pickle
from pathlib import Path
import sys
import threading
import time
import warnings

import lightgbm as lgb
import numpy as np
import pandas as pd
import psutil
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from platform_alignment_rules import ALIGNMENT_RULE_VERSION, alignment_config_snapshot, validate_alignment_config
from platform_score_rules import raw_c_value, score_nc, score_na
from search_field_policy import load_field_exclusion_policy
OUT = HERE / "search"
OPS = {"Neg": 1, "Rank": 1, "Add": 2, "Sub": 2, "Mul": 2, "ProtectedDiv": 2, "Abs": 1}
START = time.monotonic()
STOP = threading.Event()
PEAK = {"rss_gib": 0., "available_gib_min": 1000.}
warnings.filterwarnings("ignore", category=RuntimeWarning)


def clean(v):
    if isinstance(v, dict): return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (pd.Index, np.ndarray)): return [clean(x) for x in v.tolist()]
    if isinstance(v, (list, tuple)): return [clean(x) for x in v]
    if isinstance(v, (np.integer, np.bool_)): return v.item()
    if isinstance(v, (float, np.floating)): return float(v) if np.isfinite(v) else None
    if isinstance(v, (pd.Timestamp, pd.Period)): return str(v)
    return v


def save(name, value):
    target = OUT / name
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temporary.replace(target)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""): h.update(b)
    return h.hexdigest()


def log(v): print(f"[{time.monotonic()-START:.1f}s] {v}", flush=True)


def guard():
    rss = psutil.Process().memory_info().rss / 2**30
    available = psutil.virtual_memory().available / 2**30
    PEAK["rss_gib"] = max(PEAK["rss_gib"], rss)
    PEAK["available_gib_min"] = min(PEAK["available_gib_min"], available)
    if rss > 2.25 or available < 1.25:
        raise MemoryError(f"resource boundary: RSS={rss:.3f}, available={available:.3f} GiB")


def watchdog():
    while not STOP.wait(.5):
        try: guard()
        except MemoryError as e:
            save("memory_stop.json", {"reason": str(e), "memory": PEAK})
            os._exit(78)


def rank(x):
    a = np.asarray(x)
    n = np.isfinite(a).sum(1, keepdims=True)
    return np.ascontiguousarray(rankdata(a, axis=1, method="average", nan_policy="omit") / np.maximum(n, 1) - .5, dtype=np.float32)


def corr(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    x, y = np.where(ok, a, np.nan).astype(float), np.where(ok, b, np.nan).astype(float)
    x -= np.nanmean(x, 1, keepdims=True); y -= np.nanmean(y, 1, keepdims=True)
    den = np.sqrt(np.nansum(x*x, 1)*np.nansum(y*y, 1))
    return np.divide(np.nansum(x*y, 1), den, out=np.full(len(x), np.nan), where=(den > 1e-15) & (ok.sum(1) >= 100))


def build_atoms(fields, positions):
    names = list(json.loads((HERE / "search_protocol.json").read_text())["terminals"])
    out = {k: np.full((len(positions), fields["close"].shape[1]), np.nan, np.float32) for k in names}
    for begin in range(0, fields["close"].shape[1], 192):
        guard(); sl = slice(begin, begin+192)
        c, a, v, t = [pd.DataFrame(np.ascontiguousarray(fields[k][:, sl]), dtype=float) for k in ("close", "amount", "volume", "turnover")]
        r = c/c.shift(1)-1
        diff = c.diff(); up = diff.clip(lower=0).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
        down = (-diff.clip(upper=0)).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
        rsi = 100*up/(up+down)
        values = {
            "illiquidity20": (r.abs()/a.clip(lower=1)).rolling(20, min_periods=20).mean(),
            "illiquidity60": (r.abs()/a.clip(lower=1)).rolling(60, min_periods=60).mean(),
            "lowturn5": -t.rolling(5, min_periods=5).mean(),
            "lowturn20": -t.rolling(20, min_periods=20).mean(),
            "lowvol20": -r.rolling(20, min_periods=20).std(),
            "lowvol60": -r.rolling(60, min_periods=60).std(),
            "rsi_reversal14": -rsi,
            "reversal5": 1-c/c.shift(5), "reversal20": 1-c/c.shift(20), "reversal60": 1-c/c.shift(60),
            "low_price_volume_corr20": -c.rolling(20, min_periods=20).corr(v),
            "lowamount20": -a.rolling(20, min_periods=20).mean(),
        }
        for k, val in values.items(): out[k][:, sl] = val.iloc[positions].to_numpy(np.float32)
        out["smallsize"][:, sl] = -fields["cap"][positions, sl]
    active = np.isfinite(fields["cap"][positions]) & (fields["cap"][positions] > 0)
    for k in out:
        out[k][~active | ~np.isfinite(out[k])] = np.nan
        out[k] = rank(out[k])
    return out


def tree_parse(formula):
    node = ast.parse(formula, mode="eval").body
    def convert(n):
        if isinstance(n, ast.Name): return n.id
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in OPS and len(n.args) == OPS[n.func.id] and not n.keywords:
            return (n.func.id, *(convert(x) for x in n.args))
        raise ValueError("invalid expression")
    return convert(node)


def render(t): return t if isinstance(t, str) else t[0]+"("+",".join(render(a) for a in t[1:])+")"
def nodes(t): return 1 if isinstance(t, str) else 1+sum(nodes(a) for a in t[1:])


def expression(t, atoms):
    if isinstance(t, str): return atoms[t]
    name = t[0]; args = [expression(a, atoms) for a in t[1:]]
    if name == "Neg": return -args[0]
    if name == "Abs": return np.abs(args[0])
    if name == "Rank": return rank(args[0])
    if name == "Add": return args[0]+args[1]
    if name == "Sub": return args[0]-args[1]
    if name == "Mul": return args[0]*args[1]
    if name == "ProtectedDiv": return args[0]/(np.abs(args[1])+.1)
    raise ValueError(name)


def metrics(signal, y, cap, dates, cycle, fast=False, required_coverage=.95):
    valid = np.isfinite(signal) & np.isfinite(y) & np.isfinite(cap)
    base = np.isfinite(y) & np.isfinite(cap)
    coverage = valid.sum(1)/np.maximum(base.sum(1), 1)
    if np.any(coverage < required_coverage): raise ValueError("less than required per-date universe coverage")
    x, target = np.where(valid, signal, np.nan), np.where(valid, y, np.nan)
    rx, ry = rank(x), rank(target); rho = corr(rx, ry)
    if not np.isfinite(rho).all(): raise ValueError("constant or invalid cross-section")
    rows = []; previous = None
    for i, date in enumerate(dates):
        ids = np.flatnonzero(valid[i]); order = ids[np.argsort(signal[i, ids], kind="stable")]
        bins = np.ceil(np.arange(1, len(ids)+1)*10/len(ids)).astype(int)
        held = order[bins == 10]; members = set(held.tolist())
        turn = np.nan if previous is None else 1-len(members & previous)/len(members); previous = members
        rows.append({"date": date, "rank_ic": rho[i], "turnover": turn, "gross_excess": float(y[i, held].mean()-y[i, ids].mean()), "held": float(y[i, held].mean()), "benchmark": float(y[i, ids].mean()), "stocks": len(ids), "coverage": coverage[i]})
    p = pd.DataFrame(rows); mean = float(rho.mean()); std = float(rho.std(ddof=0)); ir = mean/std if std > 1e-12 else 0.
    turn = float(p.turnover.mean()); gross = float(p.gross_excess.mean()*252/cycle); win = float(np.mean(rho > .02))
    result = {"periods": len(p), "rank_ic": mean, "rank_ir": ir, "rank_win": win, "wins": int((rho > .02).sum()), "s_i": abs(mean*ir)*win, "gross_excess": gross, "turnover": turn, "net_excess": gross-turn*.006*252/cycle, "min_coverage": float(coverage.min())}
    if not fast:
        pc = corr(x, target); sc = corr(rx, rank(np.where(valid, cap, np.nan)))
        p["ic"] = pc; p["corr_size"] = sc
        result.update(pearson_ic=float(pc.mean()), corr_size=float(sc.mean()), mean_abs_size_corr=float(np.abs(sc).mean()))
    return result, p


def loss(stats, target, complexity):
    scale = np.asarray([.02, .20, .10])
    vec = np.asarray([stats["rank_ic"], stats["rank_ir"], stats["rank_win"]])
    return float(np.mean(((vec-target)/scale)**2)+.005*complexity+.1*max(stats["turnover"]-.4, 0))


class Search:
    def __init__(self, atoms, y, cap, dates, masks, target, tag):
        self.atoms, self.y, self.cap, self.dates, self.masks, self.target, self.tag = atoms, y, cap, dates, masks, target, tag
        self.records = {}; self.path = OUT / f"{tag}_evaluations.jsonl"
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                r = json.loads(line); self.records[r["formula"]] = r
        self.train_atoms = {k: np.ascontiguousarray(v[masks["train"]]) for k, v in atoms.items()}
        self.dev_atoms = {k: np.ascontiguousarray(v[masks["dev"]]) for k, v in atoms.items()}

    def assess(self, t):
        f = render(t)
        if f in self.records: return self.records[f]
        guard(); r = {"formula": f, "nodes": nodes(t), "loss": 1e9, "status": "invalid"}
        try:
            s, _ = metrics(expression(t, self.train_atoms), self.y[self.masks["train"]], self.cap[self.masks["train"]], self.dates[self.masks["train"]], 3, fast=True)
            r.update(s, loss=loss(s, self.target, nodes(t)), status="evaluated")
        except (ValueError, KeyError, FloatingPointError) as e: r["error"] = str(e)
        self.records[f] = r
        with self.path.open("a") as h: h.write(json.dumps(clean(r), ensure_ascii=False, allow_nan=False)+"\n")
        return r

    def select(self):
        top = sorted((r for r in self.records.values() if r["status"] == "evaluated"), key=lambda r: r["loss"])[:20]
        result = []
        for r in top:
            t = tree_parse(r["formula"])
            try:
                s, _ = metrics(expression(t, self.dev_atoms), self.y[self.masks["dev"]], self.cap[self.masks["dev"]], self.dates[self.masks["dev"]], 3, fast=True)
                result.append({"formula": r["formula"], "train_loss": r["loss"], "dev_loss": loss(s, self.target, nodes(t)), **s})
            except ValueError: continue
        pd.DataFrame(result).to_csv(OUT / f"{self.tag}_development.csv", index=False)
        eligible = [r for r in result if r["net_excess"] > 0]
        # Retain a documented failure if none passes; never silently change the gate.
        selected = min(eligible or result, key=lambda r: r["dev_loss"])
        return {"name": self.tag.upper(), "method": self.tag, "formula": selected["formula"], "development_positive_net": bool(eligible), "selection": selected}


def genetic(search, names):
    state_path = OUT / "gp_state.json"; rng = np.random.default_rng(20261012)
    def fresh(depth=0):
        if depth >= 3 or rng.random() < .45: return str(rng.choice(names))
        op = str(rng.choice(list(OPS))); return (op, *(fresh(depth+1) for _ in range(OPS[op])))
    def paths(t, prefix=()):
        out = [prefix]
        if not isinstance(t, str):
            for i, a in enumerate(t[1:], 1): out.extend(paths(a, prefix+(i,)))
        return out
    def at(t, p):
        for i in p: t = t[i]
        return t
    def replace(t, p, new):
        if not p: return new
        a = list(t); a[p[0]] = replace(a[p[0]], p[1:], new); return tuple(a)
    if state_path.exists():
        state = json.loads(state_path.read_text()); rng.bit_generator.state = state["rng"]
        population = [tree_parse(f) for f in state["population"]]; begin = state["next_generation"]
    else:
        population = list(names)+[("Mul", "reversal60", "lowvol60")]
        while len(population) < 64:
            t = fresh()
            if nodes(t) <= 15: population.append(t)
        begin = 0
    for generation in range(begin, 20):
        scored = [(search.assess(t), t) for t in population]
        scored.sort(key=lambda a: a[0]["loss"])
        with (OUT / "gp_attempts.jsonl").open("a") as f:
            for i, (r, _) in enumerate(scored): f.write(json.dumps({"generation": generation, "attempt": i, "formula": r["formula"], "loss": r["loss"]})+"\n")
        next_pop = [t for _, t in scored[:8]]
        while len(next_pop) < 64:
            parent = scored[int(rng.integers(24))][1]; where = paths(parent)[int(rng.integers(len(paths(parent))))]
            donor = fresh(1) if rng.random() < .55 else at(scored[int(rng.integers(24))][1], ())
            child = replace(parent, where, donor)
            if nodes(child) <= 15: next_pop.append(child)
        population = next_pop
        save("gp_state.json", {"next_generation": generation+1, "population": [render(t) for t in population], "rng": rng.bit_generator.state})
        log(f"GP generation{generation+1}/20, unique={len(search.records)}, loss={scored[0][0]['loss']:.5f}, best={scored[0][0]['formula']}")
    return search.select()


def symbolic(search, names):
    # Deterministic breadth/beam enumeration, no stochastic return-driven expansion outside declared budget.
    seeds = list(names)+[("Mul", "reversal60", "lowvol60")]
    for t in seeds: search.assess(t)
    round_number = 0
    while len(search.records) < 600:
        best = [tree_parse(r["formula"]) for r in sorted(search.records.values(), key=lambda r: r["loss"])[:20]]
        before = len(search.records)
        candidates = []
        for t in best:
            for op in ("Neg", "Rank", "Abs"): candidates.append((op, t))
            for name in names:
                for op in ("Add", "Sub", "Mul", "ProtectedDiv"): candidates.append((op, t, name))
        for t in candidates:
            if len(search.records) >= 600: break
            if nodes(t) <= 11: search.assess(t)
        round_number += 1
        log(f"symbolic expansion{round_number}, structures={len(search.records)}/600")
        if len(search.records) == before: break
    return search.select()


def fit_tree(x, label, cap, train, cfg):
    ok = np.isfinite(label) & np.isfinite(cap) & train[:, None]
    xx = np.nan_to_num(x[ok], nan=0.)
    weights = np.broadcast_to(1/np.maximum(ok.sum(1), 1)[:, None], ok.shape)[ok]
    weights *= len(weights)/weights.sum()
    params = {"objective": "regression", "num_leaves": cfg["num_leaves"], "max_depth": 3, "learning_rate": .03, "min_data_in_leaf": 2500, "lambda_l2": 100., "max_bin": 31, "feature_fraction": 1., "bagging_fraction": 1., "seed": 20261012, "num_threads": 1, "verbosity": -1, "deterministic": True, "force_col_wise": True}
    return lgb.train(params, lgb.Dataset(xx, label=label[ok], weight=weights), num_boost_round=cfg["num_boost_round"])


def tree_search(atoms, y, cap, dates, masks, configs):
    names = sorted(atoms); x = np.stack([atoms[k] for k in names], axis=-1); label = rank(y)
    results = []
    for i, cfg in enumerate(configs):
        path = OUT / f"tree_checkpoint_{i}.txt"
        if path.exists(): model = lgb.Booster(model_file=str(path))
        else:
            model = fit_tree(x, label, cap, masks["train"], cfg); model.save_model(str(path))
        dev_x = np.nan_to_num(x[masks["dev"]], nan=0.)
        signal = model.predict(dev_x.reshape(-1, len(names)), num_threads=1).reshape(dev_x.shape[:2]).astype(np.float32)
        signal[~np.isfinite(cap[masks["dev"]])] = np.nan
        s, _ = metrics(signal, y[masks["dev"]], cap[masks["dev"]], dates[masks["dev"]], 3)
        criterion = s["s_i"]+.1*min(s["net_excess"], 0)-.02*max(s["turnover"]-.4, 0)
        results.append({"checkpoint": i, **cfg, **s, "criterion": criterion})
        log(f"tree checkpoint{i+1}/6 devIC={s['rank_ic']:.5f}, devNet={s['net_excess']:.2%}")
    pd.DataFrame(results).to_csv(OUT / "tree_development.csv", index=False)
    eligible = [r for r in results if r["net_excess"] > 0]
    best = max(eligible or results, key=lambda r: r["criterion"])
    # Fixed early training only; no refit on internal development or final labels.
    model = lgb.Booster(model_file=str(OUT / f"tree_checkpoint_{best['checkpoint']}.txt"))
    model.save_model(str(OUT / "TREE_frozen.txt"))
    altered = label.copy(); altered[~masks["train"]] = 12345.
    check = fit_tree(x, altered, cap, masks["train"], {k: best[k] for k in ("num_leaves", "num_boost_round")})
    sample = np.nan_to_num(x[masks["dev"]][:2], nan=0.).reshape(-1, len(names))
    np.testing.assert_array_equal(model.predict(sample, num_threads=1), check.predict(sample, num_threads=1))
    del x, label, altered, check; gc.collect()
    return {"name": "TREE", "method": "shallow_tree", "features": names, "model": "TREE_frozen.txt", "model_sha256": sha(OUT / "TREE_frozen.txt"), "selection": best, "development_positive_net": bool(eligible), "unavailable_label_perturbation_bitwise_equal": True}


def daily_path(signal, y, cap, dates, calendar, close, cycle):
    records = []; turns = []; old = np.zeros(close.shape[1]); last = None
    for i, date in enumerate(dates):
        start = calendar.get_loc(date)+1; end = start+cycle
        if last is not None: assert start == last
        last = end
        ids = np.flatnonzero(np.isfinite(signal[i]) & np.isfinite(y[i]) & np.isfinite(cap[i]))
        order = ids[np.argsort(signal[i, ids], kind="stable")]
        bins = np.ceil(np.arange(1, len(ids)+1)*10/len(ids)).astype(int); held = order[bins == 10]
        new = np.zeros(close.shape[1]); new[held] = 1/len(held)
        buy = np.maximum(new-old, 0).sum(); sell = np.maximum(old-new, 0).sum(); turn = (buy+sell)/2
        block = close[start:end+1].astype(float)
        np.testing.assert_allclose(block[-1, ids]/block[0, ids]-1, y[i, ids], rtol=2e-6, atol=1e-7)
        pp = np.mean(block[:, held]/block[0, held], 1); bb = np.mean(block[:, ids]/block[0, ids], 1)
        records.append({"date": calendar[start], "portfolio": -.003*(buy+sell), "benchmark": 0., "turnover": turn})
        for j in range(cycle): records.append({"date": calendar[start+j+1], "portfolio": pp[j+1]/pp[j]-1, "benchmark": bb[j+1]/bb[j]-1, "turnover": 0.})
        old[:] = 0; value = block[-1, held]/block[0, held]; old[held] = value/value.sum()
        turns.append({"date": date, "entry": calendar[start], "turnover": turn, "buy": buy, "sell": sell, "fee": .003*(buy+sell)})
    daily = pd.DataFrame(records).groupby("date", sort=True).agg(portfolio=("portfolio", lambda a: np.prod(1+a)-1), benchmark=("benchmark", lambda a: np.prod(1+a)-1), turnover=("turnover", "sum"))
    months = []
    for month, f in daily.groupby(daily.index.to_period("M")):
        p, b = f.portfolio.to_numpy(), f.benchmark.to_numpy(); n = len(p)
        rex = float(np.prod(1+p)**(252/n)-np.prod(1+b)**(252/n))
        sr = float(p.mean()/p.std(ddof=1)*np.sqrt(252)) if n > 1 and p.std(ddof=1) > 0 else 0.
        nav = np.r_[1., np.cumprod(1+p)]; dd = float(1-np.min(nav/np.maximum.accumulate(nav)))
        t = float(f.turnover.sum()); raw = raw_c_value(annual_excess_return=rex, annual_sharpe=sr, monthly_turnover=t, monthly_max_drawdown=dd, sample_count=n)
        months.append({"month": str(month), "days": n, "rex": rex, "sr": sr, "max_dd": dd, "turnover": t, "raw_c": raw, "nc": score_nc(raw), "partial": month in (daily.index.min().to_period("M"), daily.index.max().to_period("M"))})
    nav = np.r_[1., np.cumprod(1+daily.portfolio.to_numpy())]
    stats = {"daily_net_nav_max_dd": float(1-np.min(nav/np.maximum.accumulate(nav))), "daily_net_nav_sharpe": float(daily.portfolio.mean()/daily.portfolio.std(ddof=1)*np.sqrt(252))}
    return stats, daily, pd.DataFrame(months), pd.DataFrame(turns)


def load_evaluator():
    path = ROOT / "research_reports/platform_alignment/nonlinear-walkforward-20261012/run.py"
    spec = importlib.util.spec_from_file_location("archived_peer_pool_evaluator", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def evaluate_frozen(finalists, atoms, dates, schedules, fields, calendar, stocks, proof):
    signals = {}
    for f in finalists:
        if "formula" in f: signals[f["name"]] = expression(tree_parse(f["formula"]), atoms)
        else:
            model = lgb.Booster(model_file=str(OUT / f["model"])); x = np.stack([atoms[k] for k in f["features"]], -1)
            signals[f["name"]] = model.predict(np.nan_to_num(x, nan=0.).reshape(-1, len(f["features"])), num_threads=1).reshape(x.shape[:2]).astype(np.float32)
            del x
        signals[f["name"]][~np.isfinite(fields["cap"][calendar.get_indexer(dates)])] = np.nan
        np.save(OUT / f"{f['name']}_all_signals.npy", signals[f["name"]])
    results = []; period_store = {}; monthly_store = {}
    for cycle, ds in schedules.items():
        index = dates.get_indexer(ds); pos = calendar.get_indexer(ds); cap = fields["cap"][pos]
        y = fields["close"][pos+cycle+1].astype(float)/fields["close"][pos+1]-1
        y[~np.isfinite(cap)] = np.nan
        for name, allsignal in signals.items():
            x = allsignal[index]
            for window, mask in [("formal_5y", np.ones(len(ds), bool)), ("recent_2026", ds >= "2026-01-01"), ("historical_final", ds >= "2025-08-22")]:
                s, p = metrics(x[mask], y[mask], cap[mask], ds[mask], cycle)
                risk, daily, monthly, turns = daily_path(x[mask], y[mask], cap[mask], ds[mask], calendar, fields["close"], cycle)
                tag = f"{name}_c{cycle}_{window}"
                p.to_csv(OUT / f"{tag}_periods.csv", index=False); daily.to_csv(OUT / f"{tag}_daily.csv")
                monthly.to_csv(OUT / f"{tag}_monthly.csv", index=False); turns.to_csv(OUT / f"{tag}_turns.csv", index=False)
                np.save(OUT / f"{tag}_signals.npy", x[mask])
                results.append({"candidate": name, "cycle": cycle, "window": window, **s, **risk, "mean_monthly_nc": float(monthly.loc[~monthly.partial, "nc"].mean())})
                period_store[(name, cycle, window)] = p; monthly_store[(name, cycle, window)] = monthly
                log(f"frozen {name} c{cycle} {window}: IC={s['rank_ic']:.5f}, IR={s['rank_ir']:.3f}, net={s['net_excess']:.2%}, DD={risk['daily_net_nav_max_dd']:.2%}")
    pd.DataFrame(results).to_csv(OUT / "single_results.csv", index=False)
    # Public-metric distances are retrospective descriptions, never further selection.
    targets = pd.read_csv(HERE / "factor_targets.csv"); targets = targets[(targets.period == "2026-10") & targets.display_name.isin(["不知所云队", "不抵灼灼目光", "Alpha猎手"])]
    distances = []
    for r in results:
        if r["cycle"] != 3 or r["window"] != "formal_5y": continue
        for t in targets.itertuples():
            distances.append({"candidate": r["candidate"], "opponent": t.display_name, "target": t.factor_name, "delta_rank_ic": r["rank_ic"]-t.ic_mean, "delta_ir": r["rank_ir"]-t.icir, "delta_win": r["rank_win"]-t.ic_win_rate, "public_periods": t.sample_count, "local_periods": r["periods"], "signal_identity_proven": False})
    pd.DataFrame(distances).to_csv(OUT / "target_metric_distances.csv", index=False)
    # Frozen three replacements of F, identical incumbent common universe.
    src = load_evaluator(); ds = schedules[10]; idx = dates.get_indexer(ds); pos = calendar.get_indexer(ds)
    cap = fields["cap"][pos]; y = fields["close"][pos+11].astype(float)/fields["close"][pos+1]-1
    seats = src.baseline_panels(ds, stocks); common = np.logical_and.reduce([np.isfinite(v) for v in seats.values()]) & np.isfinite(cap)
    if any(np.any(common & ~np.isfinite(v[idx])) for v in signals.values()):
        raise ValueError("candidate has missing signals inside fixed incumbent common universe")
    base = sum(seats.values())/5; base[~common] = np.nan
    pool_rows = []; deltas = []
    base_na = float(score_na(np.mean([metrics(v, y, cap, ds, 10, required_coverage=0.)[0]["s_i"] for v in seats.values()])))
    fkey = "book_to_market_lf_plus_impact"
    for window, mask in [("formal_5y", np.ones(len(ds), bool)), ("recent_2026", ds >= "2026-01-01")]:
        bs, _ = metrics(base[mask], y[mask], cap[mask], ds[mask], 10, required_coverage=0.)
        br, bd, bm, bt = daily_path(base[mask], y[mask], cap[mask], ds[mask], calendar, fields["close"], 10)
        neutral = src.size_neutral(base[mask], cap[mask]); bn, _ = metrics(neutral, y[mask], cap[mask], ds[mask], 10, required_coverage=0.)
        pool_rows.append({"candidate": "BASE", "window": window, **bs, **br, "size_neutral_net": bn["net_excess"], "na_proxy": base_na})
        bd.to_csv(OUT / f"POOL_BASE_{window}_daily.csv"); bm.to_csv(OUT / f"POOL_BASE_{window}_monthly.csv", index=False)
        for f in finalists:
            name = f["name"]; normalized = src.normalized(signals[name][idx]); pool = base+(normalized-seats[fkey])/5; pool[~common] = np.nan
            st, pp = metrics(pool[mask], y[mask], cap[mask], ds[mask], 10, required_coverage=0.)
            risk, daily, monthly, turns = daily_path(pool[mask], y[mask], cap[mask], ds[mask], calendar, fields["close"], 10)
            ns, _ = metrics(src.size_neutral(pool[mask], cap[mask]), y[mask], cap[mask], ds[mask], 10, required_coverage=0.)
            seat_si = [metrics(normalized if key == fkey else v, y, cap, ds, 10, required_coverage=0.)[0]["s_i"] for key, v in seats.items()]
            new_na = float(score_na(np.mean(seat_si))); dna = new_na-base_na
            mm = bm.merge(monthly, on="month", suffixes=("_base", "_new"), validate="one_to_one"); mm = mm[~mm.partial_base & ~mm.partial_new].copy()
            mm["delta_E"] = mm.rex_new-mm.rex_base; mm["delta_T"] = mm.turnover_new-mm.turnover_base; mm["delta_NC"] = mm.nc_new-mm.nc_base
            mm["delta_NA_fixed_5y"] = dna; mm["delta_AC_proxy"] = .2*dna+.45*mm.delta_NC
            mm["candidate"] = name; mm["window"] = window; deltas.append(mm)
            row = {"candidate": name, "window": window, **st, **risk, "size_neutral_net": ns["net_excess"], "na_proxy": new_na, "delta_NA_fixed_5y": dna, "delta_net": st["net_excess"]-bs["net_excess"], "delta_turnover": st["turnover"]-bs["turnover"], "delta_dd": risk["daily_net_nav_max_dd"]-br["daily_net_nav_max_dd"], "delta_abs_size_rho": abs(st["corr_size"])-abs(bs["corr_size"]), "delta_size_neutral_net": ns["net_excess"]-bn["net_excess"], "mean_delta_E": float(mm.delta_E.mean()), "mean_delta_T": float(mm.delta_T.mean()), "mean_delta_NC": float(mm.delta_NC.mean()), "mean_delta_AC_proxy": float(mm.delta_AC_proxy.mean()), "months": len(mm)}
            pool_rows.append(row)
            pp.to_csv(OUT / f"POOL_{name}_{window}_periods.csv", index=False); daily.to_csv(OUT / f"POOL_{name}_{window}_daily.csv")
            monthly.to_csv(OUT / f"POOL_{name}_{window}_monthly.csv", index=False); turns.to_csv(OUT / f"POOL_{name}_{window}_turns.csv", index=False)
            log(f"pool {name} {window}: deltaNet={row['delta_net']:.2%}, deltaDD={row['delta_dd']:.2%}, deltaAC={row['mean_delta_AC_proxy']:.6f}")
    pd.DataFrame(pool_rows).to_csv(OUT / "pool_results.csv", index=False); pd.concat(deltas).to_csv(OUT / "pool_monthly_deltas.csv", index=False)
    # Record strongest other clusters, retaining signed daily-mean Spearman and overlap counts.
    cluster_root = ROOT / "research_reports/platform_alignment/recent-factor-clusters-20261010-average-rank-v2"
    meta = json.loads((cluster_root / "metadata.json").read_text()); cd = pd.DatetimeIndex(meta["signal_dates"]); cs = pd.Index(meta["stock_ids"])
    ri, si = dates.get_indexer(cd), stocks.get_indexer(cs)
    refs = pd.read_csv(cluster_root / "references.csv"); new = pd.read_csv(cluster_root / "new_unanchored_clusters.csv").rename(columns={"new_cluster": "cluster"})
    refs = pd.concat([refs, new[["name", "formula", "cluster", "panel_id"]]], ignore_index=True)
    cr = []
    for name, v in signals.items():
        panel = np.full((len(cd), len(cs)), np.nan, np.float32); goodd = np.flatnonzero(ri >= 0); goods = np.flatnonzero(si >= 0)
        panel[np.ix_(goodd, goods)] = v[np.ix_(ri[goodd], si[goods])]
        for ref in refs.itertuples():
            path = cluster_root / "panels" / (ref.panel_id+".npy")
            if not path.exists(): continue
            other = np.load(path); valid = np.isfinite(panel) & np.isfinite(other)
            rho = corr(rank(np.where(valid, panel, np.nan)), rank(np.where(valid, other, np.nan)))
            if np.isfinite(rho).any(): cr.append({"candidate": name, "cluster": ref.cluster, "member": ref.name, "rho": float(np.nanmean(rho)), "abs_rho": abs(float(np.nanmean(rho))), "dates": int(np.isfinite(rho).sum())})
        log(f"cluster correlations completed for{name}")
    correlation = pd.DataFrame(cr).sort_values(["candidate", "abs_rho"], ascending=[True, False]); correlation.to_csv(OUT / "member_correlations.csv", index=False)
    correlation.groupby(["candidate", "cluster"], sort=False).head(1).to_csv(OUT / "cluster_correlations.csv", index=False)
    proof.update(finalists=3, platform_runs=0, fixed_common_universe_min_coverage=float(np.min(common.sum(1)/np.isfinite(cap).sum(1))), official_B_known=False, daily_path_label_checks=True)
    save("verification.json", proof)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--self-check", action="store_true"); parser.add_argument("--resume", action="store_true"); args = parser.parse_args()
    if args.self_check:
        a = {"x": np.asarray([[1., 1., 3.], [3., 2., 1.]], np.float32)}
        np.testing.assert_allclose(rank(a["x"]), [[0., 0., .5], [.5, 1/6, -1/6]], atol=1e-7)
        for f in ["Add(x,Neg(x))", "Rank(Abs(x))", "ProtectedDiv(x,x)"]:
            assert render(tree_parse(f)) == f
            assert expression(tree_parse(f), a).shape == a["x"].shape
        try: tree_parse("__import__('os')")
        except ValueError: pass
        else: raise AssertionError("unsafe AST accepted")
        print("safe grammar, average ranks and protected division passed"); return
    if not (HERE / "authorization.json").exists(): raise RuntimeError("This expanded search needs explicit user authorization")
    if (OUT / "complete.json").exists(): raise RuntimeError("Round already complete; report saved results")
    if OUT.exists() and not args.resume: raise RuntimeError("Use --resume for this approved interrupted round")
    OUT.mkdir(exist_ok=True)
    protocol = json.loads((HERE / "search_protocol.json").read_text()); validate_alignment_config(alignment_config_snapshot())
    policy = load_field_exclusion_policy(allow_version_mismatch=True)
    if policy.get("version_mismatch") and policy.get("blocked_fields"): raise ValueError("nonempty stale blocked-field policy")
    if set(policy.get("blocked_fields", [])) & {"amount", "close", "volume", "turnover", "market_cap"}: raise ValueError("required field blocked")
    market = ROOT / protocol["data"]["market_cache"]
    manifest = {"authorization": json.loads((HERE / "authorization.json").read_text()), "protocol_sha256": sha(HERE / "search_protocol.json"), "runner_sha256": sha(__file__), "market_sha256": sha(market), "evidence_sha256": sha(HERE / "evidence_manifest.json"), "alignment": ALIGNMENT_RULE_VERSION, "field_policy": policy, "loss_scales": [.02, .20, .10], "complexity_penalty": .005, "turnover_penalty": .1, "development_shortlist_per_symbolic_method": 20, "tree_refit": False, "tree_hyperparameters": "lambda_l2=100, lr=.03, min_data_in_leaf=2500, max_bin31; six approved leaves/rounds configs only"}
    if (OUT / "execution_protocol.json").exists():
        previous = json.loads((OUT / "execution_protocol.json").read_text())
        for k in ("protocol_sha256", "runner_sha256", "market_sha256", "evidence_sha256"):
            if previous[k] != manifest[k]: raise RuntimeError("Resume fingerprint changed: "+k)
    else: save("execution_protocol.json", manifest)
    threading.Thread(target=watchdog, daemon=True).start()
    with market.open("rb") as f: calendar, stocks, fields = pickle.load(f)
    calendar, stocks = pd.DatetimeIndex(calendar), pd.Index(stocks)
    assert all(str(s).endswith((".SH", ".SZ")) for s in stocks)
    active = np.isfinite(fields["cap"]) & (fields["cap"] > 0) & np.isfinite(fields["turnover"])
    fields["cap"][~active] = np.nan
    for k in ("close", "volume", "amount"):
        fields[k][~active | (fields[k] <= 0)] = np.nan
    fields["close"] = pd.DataFrame(fields["close"]).ffill().to_numpy(np.float32)
    fields = {k: fields[k] for k in ("close", "volume", "amount", "turnover", "cap")}
    native_pos = np.arange(calendar.get_loc(pd.Timestamp("2021-09-15")), len(calendar)-4, 3)
    reference = json.loads((ROOT / "research_reports/platform_alignment/nonlinear-walkforward-20261012/axes.json").read_text())
    formal = pd.DatetimeIndex(reference["signal_dates"])
    schedules = {3: calendar[native_pos], 10: formal}
    dates = pd.DatetimeIndex(sorted(set(schedules[3]) | set(formal))); positions = calendar.get_indexer(dates)
    save("axes.json", {"dates": dates, "symbols": stocks.tolist(), "native_cycle3_dates": schedules[3], "formal_cycle10_dates": formal, "local_latest": calendar[-1]})
    log(f"loading approved atoms on{len(dates)} signal dates, {len(stocks)} stocks")
    if (OUT / "atoms.npz").exists():
        with np.load(OUT / "atoms.npz") as z: atoms = {k: z[k] for k in z.files}
    else:
        atoms = build_atoms(fields, positions); np.savez_compressed(OUT / "atoms.npz", **atoms)
    proof = {"raw_prefix_checks": [], "public_metrics_are_not_signals": True, "historical_validation_previously_viewed": True}
    for cutoff in ("2023-06-30", "2025-06-30"):
        end = calendar.searchsorted(pd.Timestamp(cutoff), side="right"); selected = positions[positions < end][-2:]
        part = build_atoms({k: v[:end] for k, v in fields.items()}, selected)
        ii = np.flatnonzero(np.isin(positions, selected))
        for k in atoms: np.testing.assert_array_equal(part[k], atoms[k][ii])
        proof["raw_prefix_checks"].append({"cutoff": cutoff, "dates": len(ii), "features": len(atoms), "bitwise_equal": True})
        log(f"raw prefix check passed:{cutoff}")
    ni = dates.get_indexer(schedules[3]); nd = schedules[3]; cap = fields["cap"][native_pos]
    y = fields["close"][native_pos+4].astype(float)/fields["close"][native_pos+1]-1; y[~np.isfinite(cap)] = np.nan
    exits = calendar[native_pos+4]
    masks = {"train": (nd < "2024-01-01") & (exits < "2024-01-01"), "dev": (nd >= "2024-01-01") & (nd < "2025-08-22") & (exits < "2025-08-22"), "final": nd >= "2025-08-22"}
    assert np.all(exits[masks["train"]] < pd.Timestamp("2024-01-01")) and np.all(exits[masks["dev"]] < pd.Timestamp("2025-08-22"))
    save("split.json", {k: {"periods": int(v.sum()), "signal_first": nd[v].min(), "signal_last": nd[v].max(), "label_exit_last": exits[v].max()} for k, v in masks.items()})
    native_atoms = {k: np.ascontiguousarray(v[ni]) for k, v in atoms.items()}; target_rows = pd.read_csv(HERE / "factor_targets.csv")
    def target(name):
        row = target_rows[(target_rows.period == "2026-10") & (target_rows.factor_name == name)].iloc[0]
        return np.asarray([row.ic_mean, row.icir, row.ic_win_rate])
    if (OUT / "frozen_candidates.json").exists(): finalists = json.loads((OUT / "frozen_candidates.json").read_text())["candidates"]
    else:
        gp = Search(native_atoms, y, cap, nd, masks, target("probe-illiquidity"), "gp"); f1 = genetic(gp, sorted(atoms)); del gp; gc.collect()
        beam = Search(native_atoms, y, cap, nd, masks, target("oos-f_c_rev60_lv60_oos"), "symbolic"); f2 = symbolic(beam, sorted(atoms)); del beam; gc.collect()
        f3 = tree_search(native_atoms, y, cap, nd, masks, protocol["methods"][2]["configs"]); finalists = [f1, f2, f3]
        save("frozen_candidates.json", {"candidates": finalists, "frozen_before_final_evaluation": True, "validation_is_pristine": False})
        save("frozen_hashes.json", {"candidates": sha(OUT / "frozen_candidates.json"), "tree": sha(OUT / "TREE_frozen.txt")})
    del native_atoms; gc.collect(); log("Three candidates frozen; evaluating historical final and both cycle diagnostics")
    evaluate_frozen(finalists, atoms, dates, schedules, fields, calendar, stocks, proof)
    attempts = sum(1 for _ in (OUT / "gp_attempts.jsonl").open()); beam_count = sum(1 for _ in (OUT / "symbolic_evaluations.jsonl").open())
    assert attempts <= 1280 and beam_count <= 600
    save("complete.json", {"status": "complete", "gp_attempts": attempts, "symbolic_structures": beam_count, "tree_configs": 6, "internal_comparisons": attempts+beam_count+6, "finalists": 3, "platform_compute": 0, "seconds": time.monotonic()-START, "memory": PEAK})
    STOP.set(); log("Approved round complete")


if __name__ == "__main__": main()
