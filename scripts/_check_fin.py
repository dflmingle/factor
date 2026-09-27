import io, sys, pyarrow.parquet as pq
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
root = Path(r"D:/factor/quantlab/.quantlab/cache/research/cn_equity/financial_full_a")
files = sorted(root.rglob("*"))
print("entries:", len(files))
for f in files[:8]:
    print(" ", f.relative_to(root), f.stat().st_size if f.is_file() else "<dir>")
for f in files:
    if f.is_file() and f.suffix == ".parquet" and "balance" in f.name.lower():
        print("columns of", f.name, ":", pq.ParquetFile(f).schema_arrow.names[:30])
        break