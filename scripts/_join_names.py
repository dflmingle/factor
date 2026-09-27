import io, sys, json, csv
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor")
rows = json.loads((ROOT / "research_reports/platform_alignment/a-basis-correction-20260926/platform_si_scan.json").read_text(encoding="utf-8"))
# join with the per-directory report csv files that carry factor names
reports = {}
for csv_path in ROOT.glob("*-candidates.results/*.report.csv"):
    try:
        with csv_path.open(encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                name = (row.get("name") or row.get("factor") or "").strip()
                if name:
                    reports[name] = row
    except Exception:
        pass
print("report rows:", len(reports))
wanted = ["t10-additions-20260911-T10-ADD-BM-20260911", "VERIFY10-E260910-04", "VERIFY10-F260910-12",
          "h03-t10-20260911-H03-T10-SINGLE", "size-only-20260911-SIZE-ONLY-20260911"]
for name in wanted:
    hit = reports.get(name)
    print("--", name, "->", "found" if hit else "MISSING", (hit or {}).get("run_id", ""), (hit or {}).get("turnover", ""))
