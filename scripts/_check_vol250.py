import io, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path("D:/factor")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "quantlab" / "third_party" / "AlphaPROBE" / "src"))
from pandaai_fields_local import formula_field_name_set
s = formula_field_name_set(include_period_variants=True)
print("total fields:", len(s))
for n in ["vol", "vol250", "vol120", "vol60", "vol30", "qtyr_5_20", "bs_total_assets",
          "ev_lyr", "cal_20d_amt_ma", "amount", "volume", "market_cap",
          "book_to_market_ratio_lf", "turnover", "close", "open", "high", "low"]:
    print(f"{n:24s} {n in s}   {n.lower() in s}")
cands = sorted(x for x in s if x.lower().startswith("vol"))
print("vol* fields:", cands[:40])