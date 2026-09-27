import io, sys, json, itertools
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor")
OUT = ROOT / "research_reports/platform_alignment/bm-core-extension-20260927"
OUT.mkdir(parents=True, exist_ok=True)

seat = pd.read_csv(ROOT / "research_reports/platform_alignment/rebuild-3window-20260926/seat_windows.csv",
                   encoding="utf-8-sig").set_index("name")
print("seats:", len(seat))

def model_of(names):
    d = seat.loc[names]
    return dict(net=float(d["net_5y"].mean()), turn=float(d["turn"].mean()),
                sr=float(d["sr_5y"].mean()), dd=float(d["dd_5y"].mean()), ra=float(d["s_i_5y"].mean()),
                n=len(names))

KNOWN = [
 ("INCUMBENT", ["SIZE-ONLY-20260911","H03-T10-SINGLE","VERIFY10-E260910-04","VERIFY10-F260910-12","T10-ADD-BM-20260911"], 0.2030, 0.1339, 1.0648, 0.3164, 0.025893),
 ("SWAPF",     ["SIZE-ONLY-20260911","H03-T10-SINGLE","VERIFY10-E260910-04","T10-ADD-BM-20260911","F-I10-01"], 0.2171, 0.1353, 1.0813, 0.3336, 0.024326),
 ("V4",        ["SIZE-ONLY-20260911","H03-T10-SINGLE","T10-ADD-AGG-IMPACT-20260911","T10-ADD-G13-20260911","F-I10-01"], 0.2201, 0.1665, 1.0877, 0.3322, 0.024444),
 ("PARTT10",   ["SIZE-ONLY-20260911","H03-T10-SINGLE","VERIFY10-E260910-04","T10-ADD-AGG-IMPACT-20260911","T10-ADD-G13-20260911"], 0.2208, 0.1755, 1.1043, 0.3294, 0.026938),
 ("BM4SEAT",   ["SIZE-ONLY-20260911","H03-T10-SINGLE","T10-ADD-BM-20260911","F-I10-01"], 0.2244, 0.1448, 1.0929, 0.3376, 0.023883),
]
rows = []
for name, names, net_t, turn_t, sr_t, dd_t, ra_t in KNOWN:
    m = model_of(names)
    rows.append(dict(name=name, n=m["n"], m_net=m["net"], net_t=net_t, dnet=net_t-m["net"],
                     m_turn=m["turn"], turn_t=turn_t, dturn=turn_t-m["turn"],
                     m_sr=m["sr"], sr_t=sr_t, dsr=sr_t-m["sr"],
                     m_dd=m["dd"], dd_t=dd_t, ddd=dd_t-m["dd"],
                     m_ra=m["ra"], ra_t=ra_t, kra=ra_t/m["ra"]))
cal = pd.DataFrame(rows)
cal.to_csv(OUT / "calibration.csv", index=False, encoding="utf-8-sig")
with pd.option_context("display.width", 220, "display.float_format", lambda v: f"{v:.4f}"):
    print(cal[["name","n","m_net","net_t","dnet","m_turn","turn_t","dturn","m_sr","sr_t","dsr","m_dd","dd_t","ddd","m_ra","ra_t","kra"]].to_string(index=False))

DN  = float(cal["dnet"].median());  DN_LO = float(cal["dnet"].min())
DT  = float(cal["dturn"].median()); DT_HI = float(cal["dturn"].max())
DSR = float(cal["dsr"].median());   DSR_LO = float(cal["dsr"].min())
DDD = float(cal["ddd"].median());   DDD_HI = float(cal["ddd"].max())
KRA = float(cal["kra"].median());   KRA_LO = float(cal["kra"].min())
print(f"\ncenter deltas: dnet {DN:+.4f} dturn {DT:+.4f} dsr {DSR:+.4f} ddd {DDD:+.4f} kra {KRA:.4f}")
print(f"worst-endpoint: dnet {DN_LO:+.4f} dturn {DT_HI:+.4f} dsr {DSR_LO:+.4f} ddd {DDD_HI:+.4f} kra {KRA_LO:.4f}")

BASE = dict(net=0.2030, turn=0.1339, sr=1.0648, dd=0.3164, ra=0.025893)
def nc_mix(T, turn):
    return (7*min(1.0, T/max(1*turn,0.30)) + 46*min(1.0, T/max(2*turn,0.30)) + 7*min(1.0, T/max(3*turn,0.30)))/60
BASE_NC  = nc_mix(BASE["net"]*BASE["sr"]*(1-1.2*BASE["dd"])/0.6, BASE["turn"])
BASE_NCD= nc_mix(BASE["net"]*BASE["sr"]*(1-1.2*0.0459)/0.6, BASE["turn"])
BASE_NA = min(BASE["ra"]/0.08, 0.70)
print(f"base NCmix {BASE_NC:.4f} NCmix_dd {BASE_NCD:.4f} NA {BASE_NA:.4f}")

def pre_bridge(names, dn, dt, dsr, ddd, kra):
    m = model_of(names)
    net = m["net"]+dn; turn = m["turn"]+dt; sr = m["sr"]+dsr; dd = m["dd"]+ddd; ra = m["ra"]*kra
    T   = max(net,0)*sr*max(0.0,1-1.2*dd)/0.6
    dd_m = 0.0459*(dd/BASE["dd"])
    Tdd = max(net,0)*sr*max(0.0,1-1.2*dd_m)/0.6
    dna = min(ra/0.08,0.70) - BASE_NA
    dk  = (0.20*dna + 0.45*(nc_mix(T,turn)-BASE_NC))*44000
    dkdd= (0.20*dna + 0.45*(nc_mix(Tdd,turn)-BASE_NCD))*44000
    return dict(net=net, turn=turn, sr=sr, dd=dd, ra=ra, dk=dk, dkdd=dkdd, dna=dna)

core = ["SIZE-ONLY-20260911","H03-T10-SINGLE","T10-ADD-BM-20260911","F-I10-01"]
others = [n for n in seat.index if n not in core]
print("candidate seats to add:", len(others))

def run_enum(k_add, tag):
    results = []
    for combo in itertools.combinations(others, k_add):
        names = core + list(combo)
        c = pre_bridge(names, DN, DT, DSR, DDD, KRA)
        w = pre_bridge(names, DN_LO, DT_HI, DSR_LO, DDD_HI, KRA_LO)
        results.append(dict(seats=" + ".join(combo), n=k_add+4, turn_model=float(seat.loc[names]["turn"].mean()),
                            net_c=c["net"], turn_c=c["turn"], dk=c["dk"], dkdd=c["dkdd"],
                            dk_worst=w["dk"], dkdd_worst=w["dkdd"]))
    df = pd.DataFrame(results)
    df.to_csv(OUT / f"{tag}_all.csv", index=False, encoding="utf-8-sig")
    return df

df5 = run_enum(1, "ext5")
df6 = run_enum(2, "ext6")
print("5-add combos:", len(df5), " 6-add combos:", len(df6))

def show(df, tag, topn=25):
    good = df[(df["dk"] > 0) & (df["dkdd"] > 0)].sort_values("dk", ascending=False)
    print(f"\n== {tag}: two-basis positive: {len(good)} / {len(df)} ==")
    cols = ["seats","turn_model","net_c","turn_c","dk","dkdd","dk_worst","dkdd_worst"]
    with pd.option_context("display.width", 220, "display.float_format", lambda v: f"{v:.1f}"):
        print(good[cols].head(topn).to_string(index=False))
    return good

good5 = show(df5, "5 seats (BM4 + 1)")
good6 = show(df6, "6 seats (BM4 + 2)")

good5.to_csv(OUT / "shortlist5.csv", index=False, encoding="utf-8-sig")
good6.to_csv(OUT / "shortlist6.csv", index=False, encoding="utf-8-sig")
print("\nwritten:", OUT)