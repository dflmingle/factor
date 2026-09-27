import io
p = __import__("os").path.join(__import__("os").environ["TEMP"], "side_conv", "multi_window.py")
src = open(p, encoding="utf-8").read()
old = "    for k, d in enumerate(schedule):\n        if d not in fut:"
new = "    for k, d in enumerate(schedule):\n        if d > pd.Timestamp(\"2026-09-07\"):\n            continue\n        if d not in fut:"
assert old in src, "pattern not found"
open(p, "w", encoding="utf-8").write(src.replace(old, new))
print("patched")
