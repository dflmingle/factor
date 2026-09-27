from pathlib import Path
p = Path(r"D:\factor\scripts\platform_precheck.py")
t = p.read_text(encoding="utf-8")
old, new = "分母含相关系数（", "分母含相关系数/有符号近零字段（"
old2 = '→ 平台排序/方向不可预测，优先替换")'
new2 = '→ 平台排序/方向不可预测，优先替换、方向必须实测")'
changed = 0
if old in t:
    t = t.replace(old, new); changed += 1
if old2 in t:
    t = t.replace(old2, new2); changed += 1
p.write_text(t, encoding="utf-8")
print("replacements:", changed)