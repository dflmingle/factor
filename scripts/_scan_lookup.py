import io, sys, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor")
rows = json.loads((ROOT / "research_reports/platform_alignment/a-basis-correction-20260926/platform_si_scan.json").read_text(encoding="utf-8"))
targets = ["h03-t10-20260911", "size-only-20260911", "t10-additions-20260911", "t10-more-additions-20260911",
           "verify10", "VERIFY10", "t10-newdirections-20260911"]
for key in targets:
    hits = [r for r in rows if key.lower() in r["path"].lower()]
    print(f"== {key}: {len(hits)} runs")
    for r in sorted(hits, key=lambda x: -x["s_i"])[:6]:
        print("   %-88s n=%3d  RankIC=%.4f  IR=%.4f  win=%.4f  s_i=%.5f  | reported IC_IR=%s P=%s" % (
            Path(r["path"]).name, r["n_periods"], r["rank_ic"], r["rank_ic_ir"], r["win"], r["s_i"],
            r.get("reported_ic_ir"), r.get("reported_p_ic")))
