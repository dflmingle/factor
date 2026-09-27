import io, sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor")
seat = pd.read_csv(ROOT / "research_reports/platform_alignment/rebuild-3window-20260926/seat_windows.csv",
                   encoding="utf-8-sig").set_index("name")

def model_of(names):
    d = seat.loc[names]
    return dict(net=float(d["net_5y"].mean()), turn=float(d["turn"].mean()),
                sr=float(d["sr_5y"].mean()), dd=float(d["dd_5y"].mean()), ra=float(d["s_i_5y"].mean()))

def nc_mix(T, turn):
    return (7*min(1.0, T/max(1*turn,0.30)) + 46*min(1.0, T/max(2*turn,0.30)) + 7*min(1.0, T/max(3*turn,0.30)))/60

BASE = dict(net=0.2030, turn=0.1339, sr=1.0648, dd=0.3164, ra=0.025893)
BASE_NC  = nc_mix(BASE["net"]*BASE["sr"]*(1-1.2*BASE["dd"])/0.6, BASE["turn"])
BASE_NCD = nc_mix(BASE["net"]*BASE["sr"]*(1-1.2*0.0459)/0.6, BASE["turn"])
BASE_NA  = min(BASE["ra"]/0.08, 0.70)

def bridge_from(net, turn, sr, dd, ra):
    T   = max(net,0)*sr*max(0.0,1-1.2*dd)/0.6
    dd_m = 0.0459*(dd/BASE["dd"])
    Tdd = max(net,0)*sr*max(0.0,1-1.2*dd_m)/0.6
    dna = min(ra/0.08,0.70) - BASE_NA
    return ((0.20*dna + 0.45*(nc_mix(T,turn)-BASE_NC))*44000,
            (0.20*dna + 0.45*(nc_mix(Tdd,turn)-BASE_NCD))*44000)

K = [
 ("INCUMBENT", ["SIZE-ONLY-20260911","H03-T10-SINGLE","VERIFY10-E260910-04","VERIFY10-F260910-12","T10-ADD-BM-20260911"], 0.2030, 0.1339, 1.0648, 0.3164, 0.025893),
 ("SWAPF",     ["SIZE-ONLY-20260911","H03-T10-SINGLE","VERIFY10-E260910-04","T10-ADD-BM-20260911","F-I10-01"], 0.2171, 0.1353, 1.0813, 0.3336, 0.024326),
 ("V4",        ["SIZE-ONLY-20260911","H03-T10-SINGLE","T10-ADD-AGG-IMPACT-20260911","T10-ADD-G13-20260911","F-I10-01"], 0.2201, 0.1665, 1.0877, 0.3322, 0.024444),
 ("PARTT10",   ["SIZE-ONLY-20260911","H03-T10-SINGLE","VERIFY10-E260910-04","T10-ADD-AGG-IMPACT-20260911","T10-ADD-G13-20260911"], 0.2208, 0.1755, 1.1043, 0.3294, 0.026938),
 ("BM4SEAT",   ["SIZE-ONLY-20260911","H03-T10-SINGLE","T10-ADD-BM-20260911","F-I10-01"], 0.2244, 0.1448, 1.0929, 0.3376, 0.023883),
]
act = {x[0]: bridge_from(x[2], x[3], x[4], x[5], x[6]) for x in K}

rows = []
for x in K:
    name = x[0]
    others = [y for y in K if y[0] != name]
    dn  = float(np.median([y[2] - model_of(y[1])["net"]  for y in others]))
    dt  = float(np.median([y[3] - model_of(y[1])["turn"] for y in others]))
    dsr = float(np.median([y[4] - model_of(y[1])["sr"]   for y in others]))
    ddd = float(np.median([y[5] - model_of(y[1])["dd"]   for y in others]))
    kra = float(np.median([y[6] / model_of(y[1])["ra"]   for y in others]))
    m = model_of(x[1])
    pdk, pdkdd = bridge_from(m["net"]+dn, m["turn"]+dt, m["sr"]+dsr, m["dd"]+ddd, m["ra"]*kra)
    adk, adkdd = act[name]
    rows.append(dict(name=name, pre_dk=pdk, act_dk=adk, err_dk=pdk-adk, pre_dd=pdkdd, act_dd=adkdd, err_dd=pdkdd-adkdd))
    print(f"  {name:<10} pre_k {pdk:+8.0f} act_k {adk:+8.0f} err {pdk-adk:+7.0f} | pre_dd {pdkdd:+8.0f} act_dd {adkdd:+8.0f} err {pdkdd-adkdd:+7.0f}")

cal = pd.DataFrame(rows)
print()
print("LOO err: dk mean %+.0f (sd %.0f) | dkdd mean %+.0f (sd %.0f)" % (cal["err_dk"].mean(), cal["err_dk"].std(), cal["err_dd"].mean(), cal["err_dd"].std()))
cal.to_csv(ROOT / "research_reports/platform_alignment/bm-core-extension-20260927/loo_check.csv", index=False, encoding="utf-8-sig")