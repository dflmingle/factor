import io, sys, os, glob, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
roots = [r"D:\factor\vendor", r"D:\factor", r"D:\anaconda3\envs\easyrl4rec\Lib\site-packages"]
for root in roots:
    for p in glob.glob(os.path.join(root, "**", "*.py"), recursive=True):
        if "site-packages" in p and "alphagen" not in p.lower():
            continue
        try:
            src = open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        if "class TsDiv" in src:
            print("FOUND", p)