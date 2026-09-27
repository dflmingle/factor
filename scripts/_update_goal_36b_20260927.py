import sys
from pathlib import Path
sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor")
goal = ROOT / "GOAL.md"
raw = goal.read_bytes(); text = raw.decode("utf-8")
assert "\r" not in text
old = "    - 行动：10-01~03 窗口**无新增报批对象**；可选判别实验（待批）BM4+FSCORE+E（6 席；预桥 −93/+129；FSCORE 从未上过平台）。"
new = "    - 行动：10-01~03 窗口**无稳健新增报批对象**；可选实验（待批，可二选一或都测）：① 判别型 = BM4+FSCORE+E（预桥 −93/+129；FSCORE 从未上过平台）；\n      ② 候选型 = BM4+AGG+E（预桥 +308/+3，名义双正中 dk 最强者；= SWAPF + AGG 第 6 席）。"
assert text.count(old) == 1, text.count(old)
text = text.replace(old, new)
nb = text.encode("utf-8")
assert b"\r" not in nb and not nb.startswith(b"\xef\xbb\xbf")
goal.write_bytes(nb)
print("updated:", len(raw), "->", len(nb))