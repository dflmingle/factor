import io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = r"D:\factor\GOAL.md"
lines = open(p, encoding="utf-8").read().splitlines()
for i, l in enumerate(lines, 1):
    if l.startswith("#"):
        print(f"{i}: {l}")
print()
print("total lines", len(lines))