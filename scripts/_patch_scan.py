import io, sys, re
from pathlib import Path
p = Path(r"D:\factor\scripts\platform_si_scan_20260926.py")
src = p.read_text(encoding="utf-8")
old = """    mean = float(finite.mean())
    std = float(finite.std(ddof=1))
    ir = mean / std if std > 0 else float("nan")
    win = float((finite > 0.02).mean())
    si = abs(mean) * abs(ir) * win"""
new = """    mean = float(finite.mean())
    std = float(finite.std(ddof=1))
    ir = mean / std if std > 0 else float("nan")
    # SCORE_RULES: the win rate is a hard count of the *sign-aligned* RankIC > +0.02,
    # and it is not flipped by `direction` on its own - align by sign(mean) first.
    aligned = finite if mean >= 0 else -finite
    win = float((aligned > 0.02).mean())
    win_raw = float((finite > 0.02).mean())
    si = abs(mean) * abs(ir) * win"""
assert old in src
src = src.replace(old, new)
src = src.replace('win=win, s_i=si,', 'win=win, win_raw=win_raw, s_i=si,')
p.write_text(src, encoding="utf-8")
print("patched")
