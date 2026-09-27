import io, sys, csv
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
m = {r["candidate"]: r for r in csv.DictReader(open(r"D:\factor\research_reports\platform_alignment\cluster-overlap-20260924\candidate_matches.csv", encoding="utf-8-sig", newline=""))}
s = {r["formula"]: r for r in csv.DictReader(open(r"D:\factor\research_reports\platform_alignment\relaxed-gp-20260924\screen2\screened_candidates.csv", encoding="utf-8-sig", newline=""))}
r = m["cand0013"]
print("cand0013 local:")
for k in ["formula","net","turnover","net_y2026","net_last12","corr_size","corr_max_seat_name","max_abs_corr_member","max_abs_corr_member_name","band","is_rediscovery"]:
    if k in r: print(f"  {k:26s} {r[k]}")
sc = s.get(r["formula"])
if sc:
    print("  screened:", {k: sc[k] for k in list(sc.keys())[:14]})
