import io, sys
from pathlib import Path
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

seat = pd.read_csv(r"D:\factor\research_reports\platform_alignment\rebuild-3window-20260926\seat_windows.csv", encoding="utf-8-sig").set_index("name")
WINS = ["5y", "1y", "3m"]
INC = ["SIZE-ONLY-20260911", "H03-T10-SINGLE", "VERIFY10-E260910-04", "VERIFY10-F260910-12", "T10-ADD-BM-20260911"]
BASE_DD = 0.3164

def nc_mix(net, turn, sr, dd):
    base = max(net, 0.0) * sr * max(0.0, 1 - 1.2 * dd) / 0.6
    ncs = {k: min(1.0, base / max(k * turn, 0.30)) for k in (1, 2, 3)}
    return (7 * ncs[1] + 46 * ncs[2] + 7 * ncs[3]) / 60

def ev(names):
    d = seat.loc[names]
    nc3 = 0.0
    for w in WINS:
        nc3 += nc_mix(float(d[f"net_{w}"].mean()), float(d["turn"].mean()), float(d[f"sr_{w}"].mean()), float(d[f"dd_{w}"].mean()))
    nc3 /= 3.0
    ra5 = float(d["s_i_5y"].mean()); ra1 = float(d["s_i_1y"].mean()); ra3 = float(d["s_i_3m"].mean())
    na5 = min(max(ra5 / 0.08, 0), 0.70)
    na3w = min(max(((ra1 + ra5 + ra3) / 3) / 0.08, 0), 0.70)
    pts5 = (0.20 * na5 + 0.45 * nc3) * 44000
    pt3w = (0.20 * na3w + 0.45 * nc3) * 44000
    dd_m = 0.0459 * (float(d["dd_5y"].mean()) / BASE_DD)
    net5 = float(d["net_5y"].mean()); sr5 = float(d["sr_5y"].mean())
    tstar = max(net5, 0) * sr5 * max(0.0, 1 - 1.2 * dd_m) / 0.6
    ncs = {k: min(1.0, tstar / max(k * float(d["turn"].mean()), 0.30)) for k in (1, 2, 3)}
    mix_o = (7 * ncs[1] + 46 * ncs[2] + 7 * ncs[3]) / 60
    pts_o = (0.20 * na5 + 0.45 * mix_o) * 44000
    return dict(net5=net5, sr5=sr5, dd5=float(d["dd_5y"].mean()), turn=float(d["turn"].mean()),
                nc3=nc3, na5=na5, na3w=na3w, pts5=pts5, pt3w=pt3w, ddm=dd_m, tstar=tstar, mix_o=mix_o, pts_o=pts_o)

base = ev(INC)
print("== incumbent 3-basis ==")
print(f"  net5 {base['net5']:+.2%} sr5 {base['sr5']:.3f} dd5 {base['dd5']:.2%} turn {base['turn']:.2%}")
print(f"  [pt3w] {base['pt3w']:.0f} | [pts5] {base['pts5']:.0f} | [officialDD] {base['pts_o']:.0f}  (dd_m {base['ddm']:.4%}, T* {base['tstar']:.4f}, E[NC] {base['mix_o']:.4f})")
print()
cans = {
 "PARTT10      (SIZE+H03+E+AGG+G13)": ["SIZE-ONLY-20260911", "H03-T10-SINGLE", "VERIFY10-E260910-04", "T10-ADD-AGG-IMPACT-20260911", "T10-ADD-G13-20260911"],
 "PARTT10-over (SIZE+H03+AGG+G13)": ["SIZE-ONLY-20260911", "H03-T10-SINGLE", "T10-ADD-AGG-IMPACT-20260911", "T10-ADD-G13-20260911"],
 "AGG-T10      (SIZE+H03+E+BM+AGG)": ["SIZE-ONLY-20260911", "H03-T10-SINGLE", "VERIFY10-E260910-04", "T10-ADD-BM-20260911", "T10-ADD-AGG-IMPACT-20260911"],
 "BM4seat      (SIZE+H03+BM+F-I10-01)": ["SIZE-ONLY-20260911", "H03-T10-SINGLE", "T10-ADD-BM-20260911", "F-I10-01"],
 "SWAPF        (SIZE+H03+E+BM+F-I10-01)": ["SIZE-ONLY-20260911", "H03-T10-SINGLE", "VERIFY10-E260910-04", "T10-ADD-BM-20260911", "F-I10-01"],
}
for nm, s in cans.items():
    e = ev(s)
    print(nm)
    print(f"  net5 {e['net5']:+.2%} turn {e['turn']:.2%} nc3 {e['nc3']:.3f} na5 {e['na5']:.3f} na3w {e['na3w']:.3f}")
    print(f"  pt3w {e['pt3w']:.0f} (d{e['pt3w']-base['pt3w']:+.0f}) | pts5 {e['pts5']:.0f} (d{e['pts5']-base['pts5']:+.0f}) | officialDD {e['pts_o']:.0f} (d{e['pts_o']-base['pts_o']:+.0f})")