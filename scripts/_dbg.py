from pathlib import Path
t = Path(r"D:\factor\GOAL.md").read_bytes().decode("utf-8-sig").replace("\r\n", "\n")
tests = {
 "header": "以 NA 0.239、NC 1.00 为基准折算：",
 "row0": "| 0 | 21,903 | ≈第 24 名 |",
 "row3": "| 1.0 | 37,303 | 第 1 名档 |",
 "block": "以 NA 0.239、NC 1.00 为基准折算：\n\n| NB | 折算积分 | 当前榜上位置 |\n| ---: | ---: | --- |",
}
for k, v in tests.items():
    print(k, t.count(v))
i = t.find("21,903")
print(repr(t[i-120:i+40]))
