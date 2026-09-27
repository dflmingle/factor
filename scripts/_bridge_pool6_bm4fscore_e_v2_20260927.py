import io, json, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
OUT = Path(r"D:\factor\platform_pool_tests_20260926")
POINTS = 44000.0
BASE = dict(gross=0.2232, net=0.2030, turn=0.1339, sr=1.0648, dd=0.3164, rankic=0.0919, icir=0.3675, ra=0.025893)
CAND = {
 "POOL6-BM4FSCORE-E-V2-20260927": dict(gross=0.2399, turn=0.1766, sr=1.0912, dd=0.3236, rankic=0.0950, icir=0.3906),
}

def k_mix(net, turn, sr, dd):
    base = max(net,0)*sr*max(0,1-1.2*dd)/0.6
    ncs = {k: min(1.0, base/max(k*turn,0.30)) for k in (1,2,3)}
    return (7*ncs[1]+46*ncs[2]+7*ncs[3])/60, ncs

def flat(net, turn, sr, dd):
    base = max(net,0)*sr*max(0,1-1.2*dd)/0.6
    return min(1.0, base/max(2*turn,0.30))

def k_mix_dd(net, turn, sr, dd_m):
    base = max(net,0)*sr*max(0,1-1.2*dd_m)/0.6
    ncs = {k: min(1.0, base/max(k*turn,0.30)) for k in (1,2,3)}
    return (7*ncs[1]+46*ncs[2]+7*ncs[3])/60, ncs

def na(ra): return min(max(ra/0.08,0.0),0.70)
def nb(ra): return min(max(ra/0.06,0.0),1.0)

base_mix,_ = k_mix(BASE["net"], BASE["turn"], BASE["sr"], BASE["dd"])
base_flat = flat(BASE["net"], BASE["turn"], BASE["sr"], BASE["dd"])
base_mix_dd,_ = k_mix_dd(BASE["net"], BASE["turn"], BASE["sr"], 0.0459)
print(f"base net {BASE['net']:.4f} NCmix {base_mix:.4f} NCflat {base_flat:.4f} NCmix_dd {base_mix_dd:.4f}")

rows = []
for name, c in CAND.items():
    net = c["gross"] - c["turn"]*2*0.003*25.2
    mix,_ = k_mix(net, c["turn"], c["sr"], c["dd"])
    fl = flat(net, c["turn"], c["sr"], c["dd"])
    dd_m = 0.0459 * (c["dd"]/BASE["dd"])
    mix_dd,_ = k_mix_dd(net, c["turn"], c["sr"], dd_m)
    ra = BASE["ra"] * (c["rankic"]*c["icir"])/(BASE["rankic"]*BASE["icir"])
    dna = na(ra)-na(BASE["ra"]); dnb = nb(ra)-nb(BASE["ra"])
    dnc = mix-base_mix; dncf = fl-base_flat; dnc_dd = mix_dd-base_mix_dd
    print(f"\n{name}")
    print(f"  net {net:.4f} ({net-BASE['net']:+.4f}) turn {c['turn']:.4f} ({c['turn']-BASE['turn']:+.4f}) sr {c['sr']:.4f} dd {c['dd']:.4f}")
    print(f"  raw_a {ra:.6f} dNA {dna:+.4f} dNB {dnb:+.4f} | NCmix {mix:.4f} dNC {dnc:+.4f} | NCflat {fl:.4f} dNCf {dncf:+.4f} | dd_m {dd_m:.5f} NCmix_dd {mix_dd:.4f} dNC_dd {dnc_dd:+.4f}")
    print(f"  dComb now(NB=0) {(0.20*dna+0.45*dnc)*POINTS:+.0f} | withNB {(0.20*dna+0.35*dnb+0.45*dnc)*POINTS:+.0f} | flatC {(0.20*dna+0.45*dncf)*POINTS:+.0f} | monthDD(NB=0) {(0.20*dna+0.45*dnc_dd)*POINTS:+.0f} | monthDD(NB) {(0.20*dna+0.35*dnb+0.45*dnc_dd)*POINTS:+.0f}")
    rows.append(dict(name=name, gross=c["gross"], net=net, turn=c["turn"], sr=c["sr"], dd=c["dd"], rankic=c["rankic"], icir=c["icir"],
                     ra=ra, dna=dna, dnb=dnb, nc_mix=mix, dnc=dnc, nc_flat=fl, nc_flat_=dncf, mix_dd=mix_dd, dnc_dd=dnc_dd,
                     pts_now=(0.20*dna+0.45*dnc)*POINTS, pts_nb=(0.20*dna+0.35*dnb+0.45*dnc)*POINTS,
                     pts_flat=(0.20*dna+0.45*dncf)*POINTS, pts_dd=(0.20*dna+0.45*dnc_dd)*POINTS,
                     pts_dd_nb=(0.20*dna+0.35*dnb+0.45*dnc_dd)*POINTS))
(OUT / "platform_bridge_pool6_bm4fscore_e_v2.json").write_text(json.dumps({"base": BASE, "candidates": rows}, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print("\nsaved platform_bridge_pool6_bm4fscore_e_v2.json")