import io, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path("D:/factor")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "quantlab" / "third_party" / "AlphaPROBE" / "src"))
import pandaai_fields_local as f
names = ["current_assets", "current_liabilities", "inventory", "residual_volatility",
         "ratio_ev_ebitda_ttm", "gr_total_asset_lyr", "gr_revenue_ttm", "ratio_bm_ttm",
         "oper_main_profit_ttm", "vol250", "bs_total_assets", "cal_20d_amt_ma",
         "qtyr_5_20", "ev_lyr", "booking", "vma250", "vma3", "davol5", "asi"]
print(f"{'field':26s} {'formula348':>10s} {'catalog':>8s}  source")
for n in names:
    print(f"{n:26s} {str(n in f.PLATFORM_FIELD_SET):>10s} {str(n in f.PLATFORM_CATALOG_FIELD_SET):>8s}  {f.PLATFORM_FIELD_SOURCE_FILES.get(n)}")