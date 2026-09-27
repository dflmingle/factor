import io, sys, re, glob, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
base = r"D:\factor\vendor\skill-pandaai-factor-online\references"
for fn in glob.glob(os.path.join(base, "fields*.md")):
    text = open(fn, encoding="utf-8").read()
    for i, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        if "davol" in low or "vol_corr" in low or "amt_ma" in low:
            print(os.path.basename(fn), i, line.strip()[:170])