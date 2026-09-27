import io, sys, re, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
text = open(r"D:\factor\vendor\skill-pandaai-factor-online\references\operators.md", encoding="utf-8").read()
ops = {m.group(1).lower() for m in re.finditer(r"\|\s*`?([A-Z][A-Z0-9_]{1,24})\s*\(", text)}
ops |= {m.group(1).lower() for m in re.finditer(r"`([A-Za-z][A-Za-z0-9_]{1,24})\(", text)}
path = sys.argv[1] if len(sys.argv) > 1 else r"D:\factor\research_reports\platform_alignment\gp-platform-tests-20260925\round4\candidates_panda.txt"
for line in open(path, encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    name, formula = [p.strip() for p in line.split("~")[:2]]
    toks = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", formula)
    called = {m.group(1).lower() for m in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(", formula)}
    bare = sorted({t.lower() for t in toks if t.lower() not in called})
    print(f"{name}: called={sorted(called)}")
    print(f"  bare={bare}")
    print(f"  collisions={[t for t in bare if t in ops]}")
