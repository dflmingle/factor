"""Analytic preview of the qualitygate4 amplitude-aware IC-series gate.

The amplitude-normalised residual standard deviation has a closed form:
with beta = rho * sigma_p / sigma_l, Var(beta*local - platform) = sigma_p^2 (1 - rho^2),
so the scaled difference depends only on the saved correlation rho and the platform
chart standard deviation sigma_p (both measurable from the saved artifacts).

This does not replace a re-run: it only estimates how many saved records change
verdict once the new fields exist.

Output: research_reports/platform_alignment/fnet01-alignment-20260924/qualitygate4_preview.json
"""
from __future__ import annotations

import glob
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from platform_aligned_factor_compare import read_platform_run  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "quantlab/.quantlab/cache/research/cn_equity/reports/all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_turnoverdiag1_qualitygate3"
OUT = PROJECT_ROOT / "research_reports/platform_alignment/fnet01-alignment-20260924"
MEAN_ABS_FACTOR = 0.93  # calibrated on the two F-NET01 records (0.0517 / 0.0556)


def chart_sigmas() -> dict[str, float]:
    sigmas: dict[str, float] = {}
    for path in glob.glob(str(PROJECT_ROOT / "*results/*.json")):
        try:
            run_id = json.loads(Path(path).read_text(encoding="utf-8-sig")).get("factor_run_id")
        except Exception:
            continue
        if not run_id:
            continue
        try:
            platform = read_platform_run(Path(path))
        except Exception:
            continue
        values = np.array([np.nan if v is None else float(v) for v in platform.get("rank_ic_values", [])], dtype=float)
        if np.isfinite(values).sum() > 5:
            sigmas.setdefault(run_id, float(np.nanstd(values, ddof=1)))
    return sigmas


def main() -> int:
    data = json.loads((REPORT_DIR / "all_factor_local_compare.json").read_text())
    rows = data["results"]
    sigmas = chart_sigmas()
    print("platform runs with chart series:", len(sigmas), flush=True)

    changed, unchanged_blocked, already_ok, unknown = [], [], [], []
    for row in rows:
        status = row.get("alignment_quality")
        corr = row.get("ic_series_corr")
        delta = row.get("ic_series_mean_abs_delta")
        run_id = row.get("platform_run_id")
        entry = {"id": row.get("id"), "status": status, "corr": corr, "delta": delta,
                 "flags": row.get("alignment_quality_flags")}
        if status == "aligned":
            already_ok.append(entry)
            continue
        if status != "field_or_path_mismatch" or corr is None or delta is None:
            continue
        blocking = [f for f in (row.get("alignment_quality_flags") or [])
                    if f in {"large_ic_series_delta", "low_ic_series_corr"}]
        other_blockers = [f for f in (row.get("alignment_quality_flags") or [])
                          if f in {"large_net_delta", "large_gross_delta", "large_rank_ic_delta",
                                   "turnover_not_comparable", "unexplained_net_delta",
                                   "missing_period_coverage", "low_period_coverage",
                                   "missing_net_delta", "missing_gross_delta", "missing_rank_ic"}]
        sigma_p = sigmas.get(run_id)
        if sigma_p is None:
            unknown.append({**entry, "reason": "no saved chart series"})
            continue
        if "low_ic_series_corr" in blocking:
            unchanged_blocked.append({**entry, "reason": "correlation below 0.50"})
            continue
        if "large_ic_series_delta" not in blocking:
            continue
        scaled = MEAN_ABS_FACTOR * sigma_p * math.sqrt(max(0.0, 1.0 - min(1.0, corr) ** 2))
        record = {**entry, "sigma_platform": sigma_p, "scaled_delta_estimate": scaled,
                  "other_blockers": other_blockers}
        if scaled <= 0.06 and not other_blockers:
            changed.append(record)
        else:
            unchanged_blocked.append({**entry, "sigma_platform": sigma_p, "scaled_delta_estimate": scaled,
                                      "reason": "scaled delta above 0.06" if scaled > 0.06 else "other blocking flags"})

    summary = {
        "n_records": len(rows),
        "already_aligned": len(already_ok),
        "would_flip_to_aligned": len(changed),
        "stay_blocked_by_ic_delta": len(unchanged_blocked),
        "unassessable_without_chart": len(unknown),
        "flipped_records": sorted(changed, key=lambda r: r["id"] or ""),
        "stay_blocked_records": sorted(unchanged_blocked, key=lambda r: r["id"] or "")[:40],
        "unassessable_records": sorted(unknown, key=lambda r: r["id"] or ""),
    }
    print(json.dumps({k: v for k, v in summary.items() if not isinstance(v, list)}, ensure_ascii=False, indent=1), flush=True)
    for r in summary["flipped_records"]:
        print("  FLIP  %-46s corr=%.3f delta=%.4f sigma=%.4f scaled~%.4f" % (r["id"], r["corr"], r["delta"], r["sigma_platform"], r["scaled_delta_estimate"]), flush=True)
    for r in summary["stay_blocked_records"]:
        print("  STAY  %-46s corr=%.3f delta=%.4f sigma=%s scaled~%s (%s)" % (
            r["id"], r["corr"] or float("nan"), r["delta"] or float("nan"), r.get("sigma_platform"),
            ("%.4f" % r["scaled_delta_estimate"]) if r.get("scaled_delta_estimate") is not None else None, r["reason"]), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "qualitygate4_preview.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print("saved", OUT / "qualitygate4_preview.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
