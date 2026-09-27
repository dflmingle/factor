import io, re, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = Path("D:/factor/scripts/platform_pool_bridge_20260926.py")
text = p.read_text(encoding="utf-8")
old = """    for name, spec in CANDIDATES.items():
        pool_metrics = top_group(OUT / f"{spec['key']}.v2.run.json")"""
new = """    for name, spec in CANDIDATES.items():
        result_path = OUT / f"{spec['key']}.v2.run.json"
        if not result_path.exists():
            print(f"[skip] {name}: no platform result at {result_path}")
            continue
        pool_metrics = top_group(result_path)"""
assert old in text
p.write_text(text.replace(old, new), encoding="utf-8")
print("patched bridge to skip missing results")