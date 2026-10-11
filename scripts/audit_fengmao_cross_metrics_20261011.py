"""Audit saved signals and public snapshots only; no fitting or platform calls."""
from __future__ import annotations

import os
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from platform_alignment_rules import ALIGNMENT_RULE_VERSION
from platform_score_rules import seat_stats

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research_reports/platform_alignment"
GP = BASE / "fengmao-target-rankic-20261011"
ML = BASE / "fengmao-target-ml-20261011"
OUT = BASE / "fengmao-cross-metric-audit-20261011"
PID = "a3cb7c71ba694ada99abf2c78d99d042"


def read_json(path):
    return json.loads(path.read_text(encoding="utf8"))


def summarize(frame, candidate, window):
    r = frame.rank_ic.to_numpy()
    s = seat_stats(r)
    pearson = frame.ic.to_numpy()
    roll = pd.Series(r).rolling(12, min_periods=12).mean().dropna()
    turn = float(frame.turnover.mean())
    gross = float(frame.gross_excess.mean() * 25.2)
    sizecol = "corr_size" if "corr_size" in frame else "size_corr"
    return dict(candidate=candidate, window=window, periods=len(frame),
        first=str(frame.date.iloc[0]), last=str(frame.date.iloc[-1]),
        rank_ic=s.ic_mean, rank_std=float(r.std(ddof=0)), rank_ir=s.icir,
        wins=int(np.sum(r > .02)), win_rate=s.win_rate, s_i=s.s_i_a,
        pearson_ic=float(pearson.mean()), pearson_ir=float(pearson.mean()/pearson.std(ddof=0)),
        rank_min=float(r.min()), rank_p10=float(np.quantile(r, .1)),
        negative_periods=int(np.sum(r < 0)),
        rolling12_min=float(roll.min()) if len(roll) else None,
        rolling12_max=float(roll.max()) if len(roll) else None,
        gross_excess=gross, turnover=turn, annual_cost=turn*.006*25.2,
        net_excess=gross-turn*.006*25.2, mean_size_corr=float(frame[sizecol].mean()))


def signal_diagnostics(family):
    """Common-universe correlation/size-control diagnostics, not new candidates."""
    axisfile = "axes.json" if family == "target" else "axes_formal.json"
    dates = read_json(GP / axisfile)["dates"]
    with np.load(GP / ("atoms.npz" if family == "target" else "atoms_formal.npz")) as data:
        y, cap = data["target"], data["market_cap"]
    signals = {
        "GP_CEM": np.load(GP/f"FM_TARGET_03_{family}_signals.npy", mmap_mode="r"),
        "ML": np.load(ML/f"FM_ML_{family}_signals.npy", mmap_mode="r"),
    }
    assert all(x.shape == y.shape == cap.shape for x in signals.values())
    rows, previous = [], {}
    for at, date in enumerate(dates):
        valid = np.isfinite(y[at]) & np.isfinite(cap[at])
        for x in signals.values():
            valid &= np.isfinite(x[at])
        ids = np.flatnonzero(valid)
        f = pd.DataFrame({k: v[at, ids].astype(float) for k, v in signals.items()}, index=ids)
        f["return"] = y[at, ids].astype(float)
        f["size"] = cap[at, ids].astype(float)
        ranks = f.rank(method="average", pct=True)
        # Size-quantile buckets use present cross-sectional size, never future returns.
        buckets = np.minimum((f["size"].rank(method="first", pct=True)*20).apply(np.ceil).astype(int), 20)
        residual = ranks - ranks.groupby(buckets).transform("mean")
        mutual = float(f.GP_CEM.corr(f.ML, method="spearman"))
        for candidate in signals:
            ordered = f[candidate].sort_values(ascending=False, kind="stable").index
            row = dict(family=family, date=date, candidate=candidate, stocks=len(f),
                common_rank_ic=float(f[candidate].corr(f["return"], method="spearman")),
                mutual_signal_rank_corr=mutual,
                size_rank_corr=float(f[candidate].corr(f["size"], method="spearman")),
                size_bucket_partial_rank_ic=float(residual[candidate].corr(residual["return"])))
            for n in (10, 20):
                members = set(ordered[:n])
                key = candidate, n
                row[f"top{n}_retention"] = (len(members & previous[key])/n if key in previous else np.nan)
                previous[key] = members
            rows.append(row)
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    meta = read_json(GP/"metadata.json")
    assert meta["rule"] == ALIGNMENT_RULE_VERSION
    assert read_json(GP/"verification.json")["status"] == "passed"
    assert read_json(ML/"verification.json")["status"] == "passed"
    stats, yearly, rolls, deciles = [], [], [], []
    for candidate, folder, prefix in (("GP_CEM", GP, "FM_TARGET_03"), ("ML", ML, "FM_ML")):
        for window in ("target_119_fit", "formal_5y", "recent_2026"):
            suffix = "independent_periods" if candidate == "ML" else "periods"
            p = pd.read_csv(folder/f"{prefix}_{window}_{suffix}.csv")
            assert p.date.is_monotonic_increasing and not p.date.duplicated().any()
            stats.append(summarize(p, candidate, window))
            for year, part in p.groupby(p.date.str[:4]):
                row = summarize(part.reset_index(drop=True), candidate, window)
                row["year"] = year
                yearly.append(row)
            rr = p.rank_ic.rolling(12).mean()
            rolls.extend(dict(candidate=candidate, window=window, date=d, rolling12_rank_ic=float(v))
                         for d, v in zip(p.date, rr) if np.isfinite(v))
            if window == "formal_5y":
                tiny = p[p.date > meta["last_target_exit"]].reset_index(drop=True)
                if len(tiny):
                    stats.append(summarize(tiny, candidate, "post_target_label_end_tiny_diagnostic"))
            saved = pd.read_csv(folder/"deciles.csv")
            groups = saved[saved.window.eq(window)]
            if "candidate" in groups.columns and candidate == "GP_CEM":
                groups = groups[groups.candidate.eq(prefix)]
            groups = groups.sort_values("group")
            assert len(groups) == 10
            deciles.append(dict(candidate=candidate, window=window,
                gross_monotonicity=float(groups.group.corr(groups.gross_excess, method="spearman")),
                net_monotonicity=float(groups.group.corr(groups.net_excess, method="spearman")),
                increasing_gross_steps=int(np.sum(np.diff(groups.gross_excess)>0)),
                top_gross=float(groups.gross_excess.iloc[-1]), top_net=float(groups.net_excess.iloc[-1])))
    diag = pd.DataFrame(signal_diagnostics("target") + signal_diagnostics("formal"))
    compact = diag.groupby(["family", "candidate"]).mean(numeric_only=True).reset_index()
    stats = pd.DataFrame(stats)
    for name, value in (("cross_metrics", stats), ("years", pd.DataFrame(yearly)),
                        ("rolling12", pd.DataFrame(rolls)), ("decile_monotonicity", pd.DataFrame(deciles)),
                        ("signal_diagnostics_periods", diag), ("signal_diagnostics_summary", compact)):
        value.to_csv(OUT/f"{name}.csv", index=False)

    boardpath = ROOT/"research_reports/literature/competition-optimization-20261010/board-live/board_live.json"
    board = read_json(boardpath)
    row = next(r for r in board["rows"] if r["participant_id"] == PID)
    detailpath = BASE/"board-details-20261004-period202609/all_pool_details.json"
    detail = read_json(detailpath)[PID]
    target = next(f for f in detail["factor_pool_details"] if f["factor_name"] == "xplr-d3c-r6-grpvol")
    target_sd = target["ic_mean"]/target["icir"]
    assert abs(target["ic_mean"]*target["icir"]*target["ic_win_rate"]-target["s_i_a"]) < 1e-12
    assert abs(target["ic_win_rate"]*119-111) < 1e-10
    pub = dict(board_meta=board["meta"], current_saved_pool=row,
        historical_factor_details_source=str(detailpath.relative_to(ROOT)),
        historical_factor_details=detail, target_implied_rank_std=target_sd,
        s_i_is_derived_not_independent=True,
        absent_target_metrics=["Pearson IC", "yearly RankIC", "period RankIC series", "decile returns",
                               "per-stock signal", "factor turnover", "single-factor B"])
    (OUT/"public_evidence.json").write_text(json.dumps(pub, ensure_ascii=False, indent=2), encoding="utf8")
    paths = [boardpath, detailpath, GP/"metadata.json", ML/"metadata.json",
             GP/"FM_TARGET_03_target_signals.npy", ML/"FM_ML_target_signals.npy",
             GP/"FM_TARGET_03_formal_signals.npy", ML/"FM_ML_formal_signals.npy"]
    provenance = dict(rule=ALIGNMENT_RULE_VERSION, cost_platform=0, fitting=False, backtesting=False,
        scope="Reaggregate already saved results and correlations of frozen cached signals only",
        windows_are_not_independent_oos=True, inferred_target_dates=True,
        recent_saved_date_end=meta["recent"][1],
        cautions=["formal/recent overlap fitted labels", "tiny post-label slice is insufficient evidence",
                  "size residual diagnostic is not a new tradable factor", "public B/C are pool-level"],
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    (OUT/"provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf8")
    print(stats.to_string(index=False))
    print(pd.DataFrame(deciles).to_string(index=False))
    print(compact.to_string(index=False))
    print("TARGET IMPLIED RANK STD", target_sd)
    print("PUBLIC BOARD", board["meta"])
    print("PUBLIC POOL METRICS", row["metrics"])


if __name__ == "__main__":
    main()
