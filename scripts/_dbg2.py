from pathlib import Path
t = Path(r"D:\factor\GOAL.md").read_bytes().decode("utf-8-sig").replace("\r\n", "\n")
old = """以 NA 0.239、NC 1.00 为基准折算：

| NB | 折算积分 | 当前榜上位置 |
| ---: | ---: | --- |
| 0 | 21,903 | ≈第 24 名 |
| 0.3 | 26,523 | ≈第 4 名 |
| 0.5 | 29,603 | 第 4 名档 |
| 1.0 | 37,303 | 第 1 名档 |"""
print("count:", t.count(old))
i = t.find("以 NA 0.239")
seg = t[i:i+len(old)+20]
print(repr(seg[-80:]))
print("len old", len(old), "len seg", len(seg))
for a, b in zip(old, seg):
    if a != b:
        print("first diff:", repr(a), repr(b)); break
else:
    print("prefix identical for", min(len(old), len(seg)))
