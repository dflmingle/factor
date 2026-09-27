import io, json, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
OUT = Path(r"D:\factor\platform_pool_tests_20260926")
POINTS = 44000.0
BASE = dict(gross=0.2232, net=0.2030, turn=0.1339, sr=1.0648, dd=0.3164, rankic=0.0919, icir=0.3675, ra=0.025893)
CAND = {
 "POOL5-3WIN-FI10-V4-20260926": dict(gross=0.2453, turn=0.1665, sr=1.0877, dd=0.3322, rankic=0.0850, icir=0.3751),
 "POOL5-SWAPF-FI10-20260926": dict(gross=0.2376, turn=0.1353, sr=1.0813, dd=0.3336, rankic=0.0870, icir=0.3647),
}

def k_mix(net, turn, sr, dd):
    base = max(net,0)*sr*max(0,1-1.2*dd)/0.6
    ncs = {k: min(1.0, base/max(k*turn,0.30)) for k in (1,2,3)}
    return (7*ncs[1]+46*ncs[2]+7*ncs[3])/60, ncs

def flat(net, turn, sr, dd):
    base = max(net,0)*sr*max(0,1-1.2*dd)/0.6
    return min(1.0, base/max(2*turn,0.30))

def na(ra): return min(max(ra/0.08,0.0),0.70)
def nb(ra): return min(max(ra/0.06,0.0),1.0)

base_net = BASE["net"]; base_mix,_ = k_mix(BASE["net"], BASE["turn"], BASE["sr"], BASE["dd"])
base_flat = flat(BASE["net"], BASE["turn"], BASE["sr"], BASE["dd"])
print(f"base: net {base_net:.4f} turn {BASE['turn']:.4f} sr {BASE['sr']:.4f} dd {BASE['dd']:.4f} ra {BASE['ra']:.6f} "
      f"NA {na(BASE['ra']):.4f} NB {nb(BASE['ra']):.4f} NCmix {base_mix:.4f} NCflat {base_flat:.4f} "
      f"comb(now) {0.20*na(BASE['ra'])+0.45*base_mix:.4f} -> {(0.20*na(BASE['ra'])+0.45*base_mix)*POINTS:.0f} pts")

rows=[]
for name, c in CAND.items():
    net = c["gross"] - c["turn"]*2*0.003*25.2
    mix,_ = k_mix(net, c["turn"], c["sr"], c["dd"])
    fl = flat(net, c["turn"], c["sr"], c["dd"])
    ra = BASE["ra"] * (c["rankic"]*c["icir"])/(BASE["rankic"]*BASE["icir"])
    dna = na(ra)-na(BASE["ra"]); dnb = nb(ra)-nb(BASE["ra"])
    dnc = mix-base_mix; dncf = fl-base_flat
    dcomb_now = 0.20*dna + 0.45*dnc
    dcomb_nb  = 0.20*dna + 0.35*dnb + 0.45*dnc
    dcomb_flat = 0.20*dna + 0.45*dncf
    rows.append(dict(name=name, gross=c["gross"], net=net, turn=c["turn"], sr=c["sr"], dd=c["dd"],
                     dnet=net-base_net, dturn=c["turn"]-BASE["turn"], dsr=c["sr"]-BASE["sr"], ddd=c["dd"]-BASE["dd"],
                     rankic=c["rankic"], icir=c["icir"], ra=ra, dna=dna, dnb=dnb, dnc=dnc,
                     dcomb_now=dcomb_now, pts_now=dcomb_now*POINTS, dcomb_nb=dcomb_nb, pts_nb=dcomb_nb*POINTS,
                     dcomb_flat=dcomb_flat, pts_flat=dcomb_flat*POINTS))
    print(f"\n{name}")
    print(f"  net {net:.4f} ({net-base_net:+.4f})  turn {c['turn']:.4f} ({c['turn']-BASE['turn']:+.4f})  sr {c['sr']:.4f} ({c['sr']-BASE['sr']:+.4f})  dd {c['dd']:.4f}")
    print(f"  pool raw_a {ra:.6f} (dNA {dna:+.4f})  dNB {dnb:+.4f}  NCmix {mix:.4f} (dNC {dnc:+.4f})")
    print(f"  dComb now (NB=0) {dcomb_now:+.4f} -> {dcomb_now*POINTS:+.0f} pts/mo | with NB {dcomb_nb:+.4f} -> {dcomb_nb*POINTS:+.0f} | flatC {dcomb_flat*POINTS:+.0f}")
(OUT / "platform_bridge_swapf.json").write_text(json.dumps({"base": BASE, "candidates": rows}, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print("\nsaved platform_bridge_swapf.json")
