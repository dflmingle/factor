# -*- coding: utf-8 -*-
"""Entry 59: put the three platform-confirmed B-safe pools (2026-10-05) next to the
anchors we already own, and separate the A-segment gain (mean seat s_i) from the
C-side damage (measured long-decile Rex / turnover / SR / DD).

Zero platform spend: every input is an already-paid platform number.
"""
import csv
import io
import os

DIR = os.path.join("research_reports", "platform_alignment", "bclock-ledger-20261005")
CYCLE, ONE_WAY = 10, 0.003
COST_K = 2.0 * ONE_WAY * (252.0 / CYCLE)
NC_PTS = 19800.0             # 分/月 per 1.0 NC (0.01 NC = 198)

# seats: live 5 = t10/E/F/impact60/size_only (platform per-seat s_i, board snapshot 2026-09-30)
LIVE = {"t10": 0.059267, "E": 0.021011, "F": 0.022068, "impact60": 0.017983, "size_only": 0.009136}
ADD4 = {"K10": 0.0673, "K20": 0.0527, "STD20": 0.0557, "AMTDISP": 0.0505}
TOPMIX = 0.0610


def raw_a(seats):
    return sum(seats.values()) / len(seats)


# name, seats(or None = unknown mix), rex(gross %), turn(%/rebalance), rank_ic, icir, mono, sr, dd(%), win
POOLS = [
    ("CTRL live 5", dict(LIVE), 22.32, 13.39, 0.0919, 0.3675, None, 1.0648, 31.64, 65.0),
    ("swap1 -F +K10 (5)", {k: v for k, v in LIVE.items() if k != "F"} | {"K10": ADD4["K10"]},
     23.48, 20.36, 0.1038, 0.4066, None, 1.0979, 32.19, 65.0),
    ("add4 keep5 +4 (9)", LIVE | ADD4, 21.13, 21.30, 0.1073, 0.4184, 1.00, 1.0458, 31.11, 65.0),
    ("S1 keep4 -size_only +4 (8)", {k: v for k, v in LIVE.items() if k != "size_only"} | ADD4,
     20.18, 22.56, 0.1105, 0.4262, 1.00, 1.0371, 29.58, 65.0),
    ("S3 keep4 -impact60 +5 (9)", {k: v for k, v in LIVE.items() if k != "impact60"} | ADD4 | {"TOPMIX": TOPMIX},
     20.33, 26.47, 0.1146, 0.4586, 1.00, 1.0496, 40.36, 63.79),
    ("L6 rebuild swap4 (5)", None, 19.43, 31.00, 0.1181, 0.4634, 0.98, 1.0142, 28.49, 65.0),
    ("L2c rebuild (5)", None, 19.15, 31.61, 0.1149, 0.4656, 0.99, 1.0303, 39.12, None),
]

base_a = raw_a(LIVE)
base_na = min(base_a / 0.08, 0.70)


def rawC(rex, turn, sr, dd):
    # Same diagnostic proxy the 2026-09-30 swap1 report used, so columns stay comparable.
    return rex / max(3.0 * (turn / 100.0), 0.30) * sr * (1.0 - 1.2 * (dd / 100.0))


rows, ctrl_c = [], None
for name, seats, rex, turn, ric, icir, mono, sr, dd, win in POOLS:
    cost = turn * COST_K
    net = rex - cost
    ra = raw_a(seats) if seats else None
    d_na = (min(ra / 0.08, 0.70) - base_na) if ra else None
    d_a = (d_na / 0.01 * 88.0) if d_na is not None else None
    rc = rawC(rex, turn, sr, dd)
    if ctrl_c is None:
        ctrl_c = rc
    ratio = rc / ctrl_c
    rows.append(dict(name=name, seats=(len(seats) if seats else None), rex=rex, turn=turn,
                     cost=round(cost, 4), net=round(net, 4), d_net=round(net - 20.30, 4),
                     rank_ic=ric, icir=icir, mono=mono, sr=sr, dd=dd,
                     raw_a=(round(ra, 6) if ra else None),
                     delta_NA=(round(d_na, 6) if d_na is not None else None),
                     delta_A=(round(d_a, 1) if d_a is not None else None),
                     rawC=round(rc, 4), rawC_ratio=round(ratio, 4),
                     c_free_live_rc=round(0.60 / ratio, 4),
                     break_even_live_rc=((round((1.0 - d_a / NC_PTS) / ratio, 4)) if d_a is not None else None)))

hdr = ["name", "seats", "rex", "turn", "cost", "net", "d_net", "rank_ic", "icir", "mono", "sr", "dd",
       "raw_a", "delta_NA", "delta_A", "rawC", "rawC_ratio", "c_free_live_rc", "break_even_live_rc"]


def fmt(v, width=8, prec=2):
    return f"{'--' if v is None else format(v, '.%df' % prec):>{width}}"


print(f"{'pool':<28}{'席':>3}{'毛%':>8}{'换手%':>8}{'净%':>8}{'Δ净pp':>8}{'RankIC':>8}"
      f"{'ΔNA':>8}{'ΔA分/月':>10}{'rawC比':>8}{'C免费rc':>9}{'均衡rc':>8}")
for r in rows:
    print(f"{r['name']:<28}{r['seats'] or 0:>3}{r['rex']:>8.2f}{r['turn']:>8.2f}{r['net']:>8.2f}"
          f"{r['d_net']:>+8.2f}{r['rank_ic']:>8.4f}{fmt(r['delta_NA'], 8, 4)}{fmt(r['delta_A'], 10, 0)}"
          f"{r['rawC_ratio']:>8.3f}{r['c_free_live_rc']:>9.3f}{fmt(r['break_even_live_rc'], 8, 3)}")

os.makedirs(DIR, exist_ok=True)
out = os.path.join(DIR, "platform_bsafe_eval_20261005.csv")
with io.open(out, "w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=hdr, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: ("" if r[k] is None else r[k]) for k in hdr})
print("wrote", out)