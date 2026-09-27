from pathlib import Path
p = Path("D:/factor/scripts/_monthly_compare_all.py")
t = p.read_text(encoding="utf-8")
t = t.replace('dates = pd.to_datetime([r["data"] for r in fa["query_return_chart"]["x"][0]["data"]])',
              'dates = pd.to_datetime([r["data"] if isinstance(r, dict) else r for r in fa["query_return_chart"]["x"][0]["data"]])')
p.write_text(t, encoding="utf-8")
print("patched")