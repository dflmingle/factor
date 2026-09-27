import io, sys, csv, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = r"D:\factor\research_reports\platform_alignment\field-coverage-20260923\field_checklist.csv"
rows = list(csv.DictReader(open(p, encoding="utf-8-sig", newline="")))
print("cols:", rows[0].keys() if rows else None, "n", len(rows))
want = {"davol5", "cal_30d_ret_vol_corr", "cal_20d_amt_ma", "cal_30d_price_vol_corr",
        "ratio_bm_lyr", "is_operate_profit", "a_share_market_val", "bs_total_assets", "amount"}
for r in rows:
    key = (r.get("field") or "").lower()
    if key in want:
        print({k: r[k] for k in r})