"""Analyze public aggregate leaderboard snapshots; no factor definitions or runs."""
from pathlib import Path
import csv
import json
import statistics

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
NOW = json.loads((OUT / "board-live/board_live.json").read_text(encoding="utf-8"))
OLD = json.loads((ROOT / "research_reports/platform_alignment/board-snapshot-20261009c/board_live.json").read_text(encoding="utf-8"))
rows = NOW["rows"]
assert len(rows) == NOW["meta"]["row_count"]
assert len({r["pool_id"] for r in rows}) == len(rows)
assert len(rows) == len(OLD["rows"])
old_by_pool = {r["pool_id"]: r for r in OLD["rows"]}
me = next(r for r in rows if r["pool_name"] == "mingle")
leader = rows[0]


def write_csv(name, records):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


table = []
excluded = []
for r in rows:
    m = r["metrics"]
    old = old_by_pool[r["pool_id"]]
    om = old["metrics"]
    if any(m.get(k) is None for k in ["monthly_points", "na", "nb", "nc", "raw_a", "cumulative_points", "booked_points"]):
        excluded.append({"name":r["display_name"],"reason":"missing monthly score or A/B/C metrics"})
        continue
    monthly = min(40000, 40000 * m["newbie_factor"] * (0.2*m["na"] + 0.35*m["nb"] + 0.45*m["nc"]))
    assert abs(monthly-m["monthly_points"]) < 1e-7
    assert abs(r["score"]-m["cumulative_points"]) < 1e-7
    assert abs(m["cumulative_points"]-m["booked_points"]-m["monthly_points"]) < 1e-7
    table.append({"rank":r["rank"], "name":r["display_name"], "pool":r["pool_name"],
                  "cumulative":m["cumulative_points"], "booked":m["booked_points"],
                  "monthly_estimate":m["monthly_points"], "seats":r["active_factor_count"],
                  "raw_a":m["raw_a"], "na":m["na"], "nb":m["nb"], "nc":m["nc"],
                  "den_b":m["denominator_b"], "bonus":m["newbie_factor"],
                  "monthly_change":m["monthly_points"]-om["monthly_points"] if om.get("monthly_points") is not None else None,
                  "raw_a_change":m["raw_a"]-om["raw_a"] if om.get("raw_a") is not None else None,
                  "nb_change":m["nb"]-om["nb"] if om.get("nb") is not None else None,
                  "nc_change":m["nc"]-om["nc"] if om.get("nc") is not None else None,
                  "full_bc_monthly_scenario":min(40000,40000*m["newbie_factor"]*(0.2*m["na"]+0.8))})
write_csv("board_aggregate.csv", table)
strong = sorted([r for r in table if r["nc"] >= 1-1e-10], key=lambda r:r["raw_a"], reverse=True)
write_csv("high_a_full_c.csv", strong)

cohorts = []
for name, group in [
    ("all",table), ("top20_cumulative",table[:20]),
    ("full_c",strong), ("na_ge_0.5_full_c",[r for r in strong if r["na"] >= .5]),
    ("na_cap_full_c",[r for r in strong if r["na"] >= .7-1e-10]),
    ("nb_positive",[r for r in table if r["nb"] > 0]),
    ("full_b_and_c",[r for r in table if r["nb"] >= 1-1e-10 and r["nc"] >= 1-1e-10]),
]:
    cohorts.append({"cohort":name,"count":len(group),
                    "median_raw_a":statistics.median(r["raw_a"] for r in group) if group else None,
                    "median_seats":statistics.median(r["seats"] for r in group) if group else None})
write_csv("board_cohorts.csv", cohorts)

scenarios = []
for raw_a in [me["metrics"]["raw_a"], .035, .04, .045, .05, .056]:
    for bonus in [1.1,1.0]:
        na = min(raw_a/.08,.7)
        mine = min(40000,40000*bonus*(.2*na+.8))
        theirs = min(40000,40000*bonus*(.2*leader["metrics"]["na"]+.8))
        scenarios.append({"raw_a":raw_a,"bonus_same_for_both":bonus,"nb":1,"nc":1,
                          "my_monthly":mine,"leader_monthly":theirs,"monthly_gap":mine-theirs,
                          "months_to_recover_current_estimated_gap":
                          (leader["score"]-me["score"])/(mine-theirs) if mine>theirs else None})
write_csv("score_scenarios.csv", scenarios)

summary = {"snapshot":NOW["meta"], "rows":len(rows),
           "me":next(r for r in table if r["pool"]=="mingle"), "leader":table[0],
           "estimated_cumulative_gap":leader["score"]-me["score"],
           "booked_gap":leader["metrics"]["booked_points"]-me["metrics"]["booked_points"],
           "monthly_gap":leader["metrics"]["monthly_points"]-me["metrics"]["monthly_points"],
           "changed_monthly_count":sum(r["monthly_change"] is not None and abs(r["monthly_change"])>1e-7 for r in table),
           "changed_abc_count":sum(any(r[k] is not None and abs(r[k])>1e-10 for k in ["raw_a_change","nb_change","nc_change"]) for r in table),
           "me_a_rank":1+sum(r["raw_a"]>me["metrics"]["raw_a"] for r in table),
           "aheads_full_c":sum(r["raw_a"]>me["metrics"]["raw_a"] for r in strong),
           "cohorts":cohorts, "valid_rows":len(table), "excluded":excluded,
           "checks":"Pool uniqueness; monthly formula and cumulative=booked+estimate pass for rows with complete metrics; missing metrics explicitly excluded",
           "limits":"Preview, 2026-10-09 cutoff; C has only early-month observations; scenarios freeze rival NA and assume full B/C, not a forecast."}
(OUT / "board_analysis.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
print("HIGH A FULL C")
for r in strong[:12]:
    print(json.dumps({k:r[k] for k in ["rank","name","raw_a","na","nb","nc","seats"]},ensure_ascii=False))
