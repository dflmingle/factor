# -*- coding: utf-8 -*-
"""CAL 族储备批（2026-10-06）：ACTIVITY 免费取回落盘 + 三条平台 s_i 复算（零算力）。"""
import io, json, shutil, sys
from pathlib import Path
import numpy as np

ROOT = Path(r"D:\factor")
sys.path.insert(0, str(ROOT / "vendor" / "skill-pandaai-factor-online" / "scripts"))
import batch  # noqa: E402

DIR = ROOT / "research_reports" / "platform_alignment" / "caltech-reserve-20261006"
STATE = DIR / "candidates_calres.txt.state.json"
TMP = Path(r"C:\Users\58302\AppData\Local\Temp\_calres_activity.json")

LOCAL_SI = {"CT-COMP-ACTIVITY-20261006": 0.0477331966500963,
            "CT-COMP-TURNOVER-20261006": 0.025724854456191337,
            "CT-VOL-STD10-20261006": 0.02496300982217248}


def analyze(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    fa = payload.get("factor_analysis")
    if not isinstance(fa, dict):
        fa = (payload.get("results") or {}).get("factor_analysis") or {}
    chart = fa.get("query_rank_ic_sequence_chart") or {}
    series = None
    for entry in chart.get("y") or []:
        if str(entry.get("name", "")).lower().replace(" ", "_") in ("rank_ic", "rankic"):
            series = np.asarray([np.nan if v is None else float(v) for v in entry.get("data") or []], dtype=float)
            break
    if series is None:
        return None
    finite = series[np.isfinite(series)]
    mean = float(finite.mean()); std = float(finite.std(ddof=1)); ir = mean / std
    aligned = finite if mean >= 0 else -finite
    win = float((aligned > 0.02).mean())
    ind = {}
    for row in fa.get("query_factor_analysis_data") or []:
        if isinstance(row, dict) and "indicator" in row:
            ind[str(row["indicator"])] = row.get("factor1", row.get("factor_value"))
    return dict(n=int(finite.size), rank_ic=mean, ir=ir, win=win,
                s_i=abs(mean) * abs(ir) * win, ind=ind, fa=fa)


def main():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    name = "CT-COMP-ACTIVITY-20261006"
    entry = state[name]
    target = DIR / "candidates_calres.results" / (entry["run_id"] + ".json")
    if not entry.get("recovered_from"):
        payload = json.loads(TMP.read_text(encoding="utf-8-sig"))
        try:
            metrics = batch.extract(payload, "1", 10)
        except Exception as exc:
            print("group metrics unavailable:", exc, flush=True)
            metrics = None
        shutil.copyfile(TMP, target)
        entry["raw_result"] = "candidates_calres.results/" + entry["run_id"] + ".json"
        if metrics:
            entry["metrics"] = metrics
        entry["recovered_from"] = "factor_result"
        entry.pop("error", None)
        batch.save(STATE, state)
        print("ACTIVITY recovered;" + (" group metrics OK" if metrics else " group_returns=None (平台侧未返回分组收益)"), flush=True)

    rows = []
    for key, ent in state.items():
        d = analyze(DIR / ent["raw_result"])
        d["name"] = key
        d["local_si"] = LOCAL_SI.get(key)
        d["transfer"] = d["s_i"] / d["local_si"] if d["local_si"] else None
        m = ent.get("metrics") or {}
        d["turn_pct"] = m.get("turnover")
        d["net_pct"] = m.get("long_excess")
        d["mono"] = m.get("monotonicity")
        d["ic_ir_reported"] = d["ind"].get("IC_IR")
        rows.append(d)
    hdr = f"{'name':30s} {'n':>4s} {'RankIC':>8s} {'IR':>7s} {'win':>6s} {'s_i':>8s} {'local':>8s} {'xfer':>6s} {'turn%':>7s} {'net%':>7s}"
    print(hdr)
    for r in sorted(rows, key=lambda x: -x["s_i"]):
        print(f"{r['name']:30s} {r['n']:4d} {r['rank_ic']:8.4f} {r['ir']:7.4f} {r['win']:6.3f} {r['s_i']:8.4f} "
              f"{(r['local_si'] or 0):8.4f} {(r['transfer'] or 0):6.3f} {r['turn_pct'] or 0:7.2f} {r['net_pct'] or 0:7.2f}")
    with io.open(DIR / "platform_calres_si_20261006.csv", "w", encoding="utf-8-sig", newline="\n") as fh:
        fh.write("name,n_periods,rank_ic,rank_ic_ir,win,s_i,local_s_i,transfer,turnover_pct,long_excess_pct,monotonicity,ic_ir_reported\n")
        for r in rows:
            fh.write("%s,%d,%.6f,%.6f,%.6f,%.6f,%s,%s,%s,%s,%s,%s\n" % (
                r["name"], r["n"], r["rank_ic"], r["ir"], r["win"], r["s_i"],
                r["local_si"], r["transfer"], r["turn_pct"], r["net_pct"], r["mono"], r["ic_ir_reported"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())