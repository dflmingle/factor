import io, sys, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor")
OUT = ROOT / "research_reports/platform_alignment/a-basis-correction-20260926"
rows = json.loads((OUT / "platform_si_scan.json").read_text(encoding="utf-8"))
arena = json.loads((ROOT / "research_reports/platform_alignment/score-rules-20260924/verification.json").read_text(encoding="utf-8"))["seats"]
print("=== validate scan against arena seat values (window 20210927..20260826, 120 periods) ===")
for seat in arena:
    ic, ir, win, si = seat["ic_platform"], seat["ir_platform"], seat["win_platform"], seat["s_i_platform"]
    matches = [r for r in rows
               if abs(abs(r["rank_ic"]) - ic) < 0.006
               and abs(abs(r["rank_ic_ir"]) - ir) < 0.06]
    matches.sort(key=lambda r: abs(abs(r["rank_ic"]) - ic) + abs(abs(r["rank_ic_ir"]) - ir))
    print(f"-- {seat['column']:<34} arena ic={ic:.4f} ir={ir:.4f} win={win:.4f} s_i={si:.5f}")
    for r in matches[:3]:
        print("     %-70s ic=%.4f ir=%.4f win=%.4f s_i=%.5f (win_raw=%.4f) rel=%.2f%%" % (
            Path(r["path"]).name, r["rank_ic"], r["rank_ic_ir"], r["win"], r["s_i"], r["win_raw"],
            100.0 * (r["s_i"] - si) / si))
    if not matches:
        print("     (no backtest file matches these stats)")
