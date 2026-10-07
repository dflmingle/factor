# -*- coding: utf-8 -*-
"""Entry 59 / 11-01~03 决策表：所有 B 安全（k<=1 换席，或只加席）形态的 A 阶梯 + 换手地板检查。

口径全部用已付费的平台数字：
- A 段 = 逐席平台 s_i 均值（09-30 快照 + CAL 族 10-03 实测），ΔA 分/月 = Δraw_a/0.08*8800 = ΔNA*8800。
- C 段 = 平台五年净额（已测形态）+ 月换手地板 max(Turn_month, 0.30)（2 调仓月 = 2x每次换手）。
零平台算力。
"""
import csv
import io
import os

DIR = "research_reports/platform_alignment/bclock-ledger-20261005"
A_RATE = 8800.0  # = 0.08 * 110000: 分/月 per +1.0 NA
FLOOR = 0.30

SI = {"t10": 0.05926662119415439, "E": 0.021011254255464188, "F": 0.022068061621976547,
      "impact60": 0.017982594724007532, "size_only": 0.009135508656026116,
      "K10": 0.0673, "K20": 0.0527, "TOPMIX": 0.0610, "STD20": 0.0557, "AMTDISP": 0.0505}

# 已平台实测形态：name -> (net%, turn%/次)
MEASURED = {
    "hold 现役 5 席": (20.30, 13.39),
    "F->K10 (已确认)": (20.40, 20.36),
    "F->K20 (已确认)": (20.45, 19.44),
    "F->AMTDISP (已确认)": (20.03, 16.81),
    "add +K10 (6 席, 09-29)": (19.53, 18.16),
    "add4 keep5+4 (9 席)": (17.91, 21.30),
    "S1 keep4(-size)+4 (8 席)": (16.77, 22.56),
    "S3 keep4(-impact)+5 (9 席)": (16.33, 26.47),
    "L5 换席 (5 席)": (13.14, 34.52),
    "L6 换 4 席 (5 席)": (14.74, 31.00),
}
MEASURED_BY_DELTA = {
    ("-F", "+K10"): "F->K10 (已确认)",
    ("-F", "+K20"): "F->K20 (已确认)",
    ("-F", "+AMTDISP"): "F->AMTDISP (已确认)",
    ("keep5", "+K10"): "add +K10 (6 席, 09-29)",
}

LIVE = ["t10", "E", "F", "impact60", "size_only"]
base_mean = sum(SI[k] for k in LIVE) / len(LIVE)
base_na = min(base_mean / 0.08, 0.70)


def na(raw_a):
    return min(raw_a / 0.08, 0.70)


rows = []
for out in LIVE:
    if out == "t10":
        continue                       # 换掉最强席一定掉 A，不进表
    for new in ["K10", "K20", "STD20", "TOPMIX", "AMTDISP"]:
        seats = [k for k in LIVE if k != out] + [new]
        raw_a = sum(SI[k] for k in seats) / len(seats)
        d_na = na(raw_a) - base_na
        key = ("-" + out, "+" + new)
        rows.append(dict(kind="swap", delta=f"-{out} +{new}", n=5, raw_a=round(raw_a, 6),
                         d_NA=round(d_na, 5), d_A=round(d_na * A_RATE, 0),
                         measured=MEASURED_BY_DELTA.get(key, ""), d_delay_days=0))
for new in ["K10", "K20", "STD20", "TOPMIX", "AMTDISP"]:
    seats = LIVE + [new]
    raw_a = sum(SI[k] for k in seats) / len(seats)
    d_na = na(raw_a) - base_na
    rows.append(dict(kind="add", delta=f"keep5 +{new}", n=6, raw_a=round(raw_a, 6),
                     d_NA=round(d_na, 5), d_A=round(d_na * A_RATE, 0),
                     measured=MEASURED_BY_DELTA.get(("keep5", "+" + new), ""), d_delay_days=0))

rows.sort(key=lambda r: -r["d_A"])
for r in rows:
    m = MEASURED.get(r["measured"])
    r["net_pct"] = round(m[0], 2) if m else None
    r["turn_per_reb"] = round(m[1], 2) if m else None
    r["turn_month2"] = round(2 * m[1] / 100.0, 4) if m else None
    if m:
        r["floor_breach"] = "BREACH" if (2 * m[1] / 100.0) > FLOOR else "free"
    else:
        r["floor_breach"] = "?"

hdr = ["kind", "delta", "n", "raw_a", "d_NA", "d_A", "measured", "net_pct",
       "turn_per_reb", "turn_month2", "floor_breach", "d_delay_days"]
print(f"现役 5 席 raw_a {base_mean:.6f} / NA {base_na:.4f}；月换手地板 {FLOOR:.2f}"
      f"（现役 2x13.39% = {2*0.1339:.4f} -> 免费）")
print(f"{'形态':<22}{'席':>3}{'ΔNA':>9}{'ΔA分/月':>10}{'实测净%':>9}{'换手/次':>9}{'2调仓月T':>10}{'地板':>8}")
for r in rows:
    print(f"{r['delta']:<22}{r['n']:>3}{r['d_NA']:>+9.4f}{r['d_A']:>+10.0f}"
          f"{(r['net_pct'] if r['net_pct'] is not None else float('nan')):>9.2f}"
          f"{(r['turn_per_reb'] if r['turn_per_reb'] is not None else float('nan')):>9.2f}"
          f"{(r['turn_month2'] if r['turn_month2'] is not None else float('nan')):>10.4f}"
          f"{r['floor_breach']:>8}")

out = os.path.join(DIR, "bsafe_dA_ladder_20261005.csv")
with io.open(out, "w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=hdr, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: ("" if r[k] is None else r[k]) for k in hdr})
print("wrote", out)