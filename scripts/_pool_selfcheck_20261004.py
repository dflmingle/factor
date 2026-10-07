# -*- coding: utf-8 -*-
"""池级候选自查（2026-10-04，零平台算力）：用 09-30/10-04 反解并 305 池全量验证的
na/nb/nc 真公式，对已有本地整池账（pool-family-20261004）重算 A/C 段与稳态月度得分。

输入（全部仓库内已有产物）：
- research_reports/platform_alignment/board-snapshot-20260930/board_live.json
- research_reports/platform_alignment/board-details-20261004-period202609/{all_pool_details.json,factors_all.csv}
- research_reports/platform_alignment/board-20260928/board_live.json（denominator_b 月末 tick 证据）
- research_reports/platform_alignment/pool-family-20261004/{pool_monthly_*.csv,pool_summary.csv,seat_stats.csv,ledger_meta.json}

真公式（2026-10-04 反解，305 池 0 失配）：
  na = min(raw_a/0.08, 0.70)，raw_a = 席位 s_i_a 均值（denominator_a = 席位数）
  nb = clip(raw_b/0.06, 0, 1)，raw_b = 被计数席位 b_i 均值（席位级样本外时钟，月末 tick）
  nc = clip(raw_c/0.60, 0, 1)，raw_c = max(annual_rex,0)/max(turn,0.30)*annual_sr*(1-1.2*max_dd)
  comb = 0.20*na + 0.35*nb + 0.45*nc， points = comb * 40000 * newbie_factor(1.1)
C 段两个口径：
  v030：分母 max(turn_month, 0.30)（与本地账、e_decomp 一致；CSV 已验证同式）
  v050：分母 max(turn_month, 0.50)（平台 turn 字段观测下界 0.5；对低换手月更贴近平台）
输出：research_reports/platform_alignment/pool-family-20261004/selfcheck/
"""
from __future__ import annotations

import csv
import io
import json
import math
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PA = ROOT / "research_reports" / "platform_alignment"
POOL = PA / "pool-family-20261004"
OUT = POOL / "selfcheck"
OUT.mkdir(parents=True, exist_ok=True)
T0 = time.time()
LOG = []


def log(msg: str) -> None:
    line = f"[{time.time() - T0:6.1f}s] {msg}"
    print(line, flush=True)
    LOG.append(line)


def read_json(p: Path):
    return json.load(io.open(p, encoding="utf-8"))


def read_csv(p: Path):
    return list(csv.DictReader(io.open(p, encoding="utf-8-sig")))


def clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def main() -> int:
    live = read_json(PA / "board-snapshot-20260930" / "board_live.json")
    det = read_json(PA / "board-details-20261004-period202609" / "all_pool_details.json")
    live28 = read_json(PA / "board-20260928" / "board_live.json")
    rows = live["rows"]
    lmap = {r["participant_id"]: r for r in rows}
    l28 = {r["participant_id"]: r for r in live28["rows"]}

    # ---------- 1) 公式链验证（305 池） ----------
    ver = {"n_pools": len(rows), "mismatch": {}}
    bad = {}
    for r in rows:
        m = r["metrics"]
        pid = r["participant_id"]
        fac = det[pid]["factor_pool_details"]
        na = min(m["raw_a"] / 0.08, 0.70)
        nb = clip(m["raw_b"] / 0.06)
        nc = clip(m["raw_c"] / 0.60)
        comb = 0.20 * na + 0.35 * nb + 0.45 * nc
        pts = comb * 40000.0 * m["newbie_factor"]
        rawc = max(m["annual_rex"], 0.0) / max(m["turn"], 0.30) * m["annual_sr"] * (1 - 1.2 * m["max_dd"])
        checks = {
            "na": abs(na - m["na"]) < 1e-9,
            "nb": abs(nb - m["nb"]) < 1e-9,
            "nc": abs(nc - m["nc"]) < 1e-9,
            "comb": abs(comb - m["comb"]) < 1e-9,
            "points": abs(pts - r["score"]) < 1e-6,
            "raw_c(max rex,0)": abs(rawc - m["raw_c"]) < 1e-6,
            "raw_a=mean(s_i_a)": abs(sum(f["s_i_a"] for f in fac) / len(fac) - m["raw_a"]) < 1e-9,
            "denominator_a=nfac": m["denominator_a"] == len(fac),
        }
        for k, ok in checks.items():
            if not ok:
                bad[k] = bad.get(k, 0) + 1
    ver["mismatch"] = bad
    ver["ok"] = (sum(bad.values()) == 0)

    turns = [r["metrics"]["turn"] for r in rows]
    ver["turn_min"] = min(turns)
    ver["turn_at_floor_0p5"] = sum(1 for t in turns if abs(t - 0.5) < 1e-9)
    tr = [(l28[pid]["display_name"], l28[pid]["metrics"]["denominator_b"], lmap[pid]["metrics"]["denominator_b"])
          for pid in l28 if pid in lmap
          and l28[pid]["metrics"]["denominator_b"] != lmap[pid]["metrics"]["denominator_b"]]
    ver["denom_b_flips_0924_to_0930"] = len(tr)
    ver["denom_b_flip_sample"] = tr[:10]
    log(f"[chain] mismatches={bad or 'NONE'} ; turn_min={ver['turn_min']:.6f} ; denom_b flips 09-24->09-30 = {len(tr)}")

    # ---------- 2) 候选池自查（真公式重算） ----------
    meta = read_json(POOL / "ledger_meta.json")
    plat_si = meta["plat_si"]
    psum = {r["pool"]: r for r in read_csv(POOL / "pool_summary.csv")}
    seed_actual = lmap["70c703ce0eba4038bd8b4a9ebbc46ff6"]["metrics"]  # 09-30 平台实测（含建仓期）
    SEED_NA = min(seed_actual["raw_a"] / 0.08, 0.70)

    def nc_variant(rows_m, tag, floor):
        rex = [float(r[f"rex_ann_{tag}"]) for r in rows_m]
        sr = [float(r[f"sr_ann_{tag}"]) for r in rows_m]
        dd = [float(r[f"max_dd_{tag}"]) for r in rows_m]
        tn = [float(r[f"turnover_month_{tag}"]) for r in rows_m]
        raws = [max(x, 0.0) / max(t, floor) * s * (1 - 1.2 * d) for x, s, d, t in zip(rex, sr, dd, tn)]
        ncs = [clip(v / 0.60) for v in raws]
        return raws, ncs

    monthly_rows = []
    table = []
    for path in sorted(POOL.glob("pool_monthly_*.csv")):
        name = path.stem.replace("pool_monthly_", "")
        mrows = read_csv(path)
        srow = psum.get(name, {})
        seats = srow.get("seats", "").split("|")
        si = [plat_si.get(k, float("nan")) for k in seats]
        have_si = all(not (isinstance(v, float) and math.isnan(v)) for v in si)
        raw_a_new = sum(si) / len(si) if have_si else float("nan")
        na_new = min(raw_a_new / 0.08, 0.70) if have_si else float("nan")
        d_a = (na_new - SEED_NA) * 0.20 * 40000.0 * 1.1 if have_si else float("nan")

        r030_s, n030_s = nc_variant(mrows, "seed", 0.30)
        r030_p, n030_p = nc_variant(mrows, "p", 0.30)
        r050_s, n050_s = nc_variant(mrows, "seed", 0.50)
        r050_p, n050_p = nc_variant(mrows, "p", 0.50)

        # 与 CSV 自身列交叉验证（v030 应逐月完全一致）
        chk = max(abs(a - float(r["raw_c_seed"])) for a, r in zip(r030_s, mrows))
        chk_p = max(abs(a - float(r["raw_c_p"])) for a, r in zip(r030_p, mrows))

        def mean(x):
            return sum(x) / len(x)

        dnc030 = mean(n030_p) - mean(n030_s)
        dnc050 = mean(n050_p) - mean(n050_s)
        d_c030 = 0.45 * 40000.0 * 1.1 * dnc030
        d_c050 = 0.45 * 40000.0 * 1.1 * dnc050
        nc_p030 = mean(n030_p)
        comb = (0.20 * na_new + 0.35 * 0.0 + 0.45 * nc_p030) if have_si else float("nan")
        pts = comb * 40000.0 * 1.1 if have_si else float("nan")
        seed_comb = 0.20 * SEED_NA + 0.35 * 0.0 + 0.45 * mean(n030_s)
        seed_pts = seed_comb * 40000.0 * 1.1
        pen = sum(1 for a, b in zip(n030_p, n030_s) if a < b - 1e-12)
        worst = min(b - a for a, b in zip(n030_p, n030_s))
        table.append(dict(
            pool=name, seats="|".join(seats),
            raw_a_new=raw_a_new, na_new=na_new, d_a_points=d_a,
            nc_seed=mean(n030_s), nc_new=nc_p030, dnc030=dnc030, d_c030=d_c030,
            dnc050=dnc050, d_c050=d_c050,
            d_comb_ac=(d_a + d_c030) if have_si else float("nan"),
            combo_steady=comb, points_steady=pts,
            d_points_steady=(pts - seed_pts) if have_si else float("nan"),
            d_points_firstmonth=(d_a + d_c050 * 0.0 + 0.0) if have_si else float("nan"),  # 首月 C≈1 假设（建仓期），仅 A 计入
            penalty_months=pen, worst_dnc=worst, d_b_per_unit_nb=0.35 * 40000.0 * 1.1,
            csv_check_rawc_seed=chk, csv_check_rawc_p=chk_p,
        ))
        for i, r in enumerate(mrows):
            monthly_rows.append(dict(
                pool=name, year=r["year"], month=r["month"],
                nc_seed=n030_s[i], nc_new=n030_p[i], dnc=n030_p[i] - n030_s[i],
                nc_seed_f50=n050_s[i], nc_new_f50=n050_p[i], dnc_f50=n050_p[i] - n050_s[i],
                raw_c_seed=r030_s[i], raw_c_new=r030_p[i],
                turn_seed=float(r["turnover_month_seed"]), turn_new=float(r["turnover_month_p"]),
            ))
    seed_row = dict(
        pool="CTRL_seed(现役)", seats="|".join(meta["plat_si"] and ["t10", "bm_minus", "bm_plus", "impact60", "size"]),
        raw_a_new=seed_actual["raw_a"], na_new=SEED_NA, d_a_points=0.0,
        nc_seed=mean(n030_s), nc_new=mean(n030_s), dnc030=0.0, d_c030=0.0, dnc050=0.0, d_c050=0.0,
        d_comb_ac=0.0, combo_steady=seed_comb, points_steady=seed_pts, d_points_steady=0.0,
        d_points_firstmonth=0.0, penalty_months=0, worst_dnc=0.0, d_b_per_unit_nb=0.35 * 40000.0 * 1.1,
        csv_check_rawc_seed=0.0, csv_check_rawc_p=0.0,
    )
    table.insert(0, seed_row)
    table_sorted = sorted(table, key=lambda r: (r["d_points_steady"] if r["d_points_steady"] == r["d_points_steady"] else -1e9), reverse=True)

    with io.open(OUT / "candidate_selfcheck.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0].keys()))
        w.writeheader()
        for r in table_sorted:
            w.writerow(r)
    with io.open(OUT / "candidate_monthly.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(monthly_rows[0].keys()))
        w.writeheader()
        w.writerows(monthly_rows)
    (OUT / "chain_verification.json").write_text(json.dumps(ver, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "run.log").write_text("\n".join(LOG) + "\n", encoding="utf-8")

    log("=== 稳态月度得分（真公式，nb=0） ===")
    log(f"{'pool':22s} {'na':>6s} {'dA':>7s} {'nc_new':>7s} {'dNC30':>7s} {'dC30':>8s} {'dC50':>8s} {'comb':>7s} {'pts/mo':>8s} {'dpts':>7s}  penalty")
    for r in table_sorted:
        log(f"{r['pool']:22s} {r['na_new']:6.3f} {r['d_a_points']:7,.0f} {r['nc_new']:7.4f} {r['dnc030']:+7.4f} "
            f"{r['d_c030']:+8,.0f} {r['d_c050']:+8,.0f} {r['combo_steady']:7.4f} {r['points_steady']:8,.0f} "
            f"{r['d_points_steady']:+7,.0f}  {r['penalty_months']:2d}m worstdNC={r['worst_dnc']:+.2f}")
    log(f"seed comb={seed_comb:.4f} pts={seed_pts:,.0f}/mo ; seed actual 09-30 pts={seed_actual['comb']*44000:,.0f}/mo (nc=1.0 建仓期)")
    log(f"platform s_i used: " + json.dumps({k: v for k, v in plat_si.items() if isinstance(v, float) and v == v}, ensure_ascii=False))
    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())