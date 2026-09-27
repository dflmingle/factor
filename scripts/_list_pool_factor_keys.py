import io, re, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path("D:/factor")
pat = re.compile(r"factors\[\s*['\"]([a-z0-9_]+)['\"]\s*\]")
rows = []
for path in sorted(ROOT.glob("pool*.py")) + sorted(ROOT.glob("platform_pool_tests_*/pool*.py")):
    keys = sorted(set(pat.findall(path.read_text(encoding="utf-8"))))
    if keys:
        rows.append((path.name, keys))
for name, keys in rows:
    print(f"{name}: {', '.join(keys)}")