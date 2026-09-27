import io, sys, re, glob, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
targets = [r"D:\factor\GOAL.md", r"D:\factor\AGENTS.md",
           r"D:\factor\research_reports\platform_alignment\ALIGNMENT_RULES.md"]
kws = ["量级", "数值", "退化", "rescale", "缩放", "1e-", "精度", "下溢", "underflow", "常数"]
for p in targets:
    if not os.path.exists(p):
        continue
    text = open(p, encoding="utf-8").read()
    print("#" * 20, os.path.basename(p))
    for kw in kws:
        for m in re.finditer(kw, text):
            ln = text[:m.start()].count("\n") + 1
            line = text.splitlines()[ln - 1].strip()
            print(f"   [{kw}] {ln}: {line[:150]}")
            break