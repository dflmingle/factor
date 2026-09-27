import io, sys, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor")
files = {
 "AGG": r"t10-more-additions-20260911-candidates.results\6aa3ca1451cdfe29b2e0bce4.json",
 "G13": r"t10-additions-20260911-candidates.results\6aa3c61451cdfe29b2e0bcdd.json",
 "DOWNSIDE": r"t10-more-additions-20260911-candidates.results\6aa3c9208b01f62dc5146090.json",
 "WC": r"t10-newdirections-20260911-candidates.results\6aa3690a6df2a192a47e7c60.json",
}
scan = {r["path"]: r for r in json.loads((ROOT / "research_reports/platform_alignment/a-basis-correction-20260926/platform_si_scan.json").read_text(encoding="utf-8"))}
bridge = {"AGG": 0.1057 * 0.4379 * 0.6167, "G13": 0.1043 * 0.4295 * 0.6167,
          "DOWNSIDE": 0.1067 * 0.4389 * 0.6167, "WC": 0.1052 * 0.4421 * 0.65}
for name, rel in files.items():
    d = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    fa = d["results"]["factor_analysis"]
    ind = {r["indicator"]: list(r.values())[-1] for r in fa["query_factor_analysis_data"]}
    row = scan.get(rel)
    print(f"== {name}")
    print("   reported:", json.dumps(ind, ensure_ascii=False))
    if row:
        print("   scan   : RankIC=%.4f  IR=%.4f  win=%.4f -> s_i=%.5f   [bridge used %.5f]" % (
            row["rank_ic"], row["rank_ic_ir"], row["win"], row["s_i"], bridge[name]))
