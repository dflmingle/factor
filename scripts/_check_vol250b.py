import io, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path("D:/factor")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "quantlab" / "third_party" / "AlphaPROBE" / "src"))
import pandaai_fields_local as f
print("vol250 source:", f.PLATFORM_FIELD_SOURCE_FILES.get("vol250"))
print("vol250 label:", f.PLATFORM_FIELD_LABELS.get("vol250"))
print("vol250 category:", f.PLATFORM_FIELD_CATEGORIES.get("vol250"))
print("in PLATFORM_FIELD_SET (348 formula-mode):", "vol250" in f.PLATFORM_FIELD_SET)
print("in CATALOG set:", "vol250" in f.PLATFORM_CATALOG_FIELD_SET)
for n in ["qtyr_5_20","bs_total_assets","ev_lyr","cal_20d_amt_ma"]:
    print(f"{n}: src={f.PLATFORM_FIELD_SOURCE_FILES.get(n)} formula_mode={n in f.PLATFORM_FIELD_SET} cat={n in f.PLATFORM_CATALOG_FIELD_SET}")