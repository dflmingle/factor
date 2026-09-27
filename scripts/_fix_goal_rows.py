from pathlib import Path
p = Path("D:/factor/GOAL.md")
text = p.read_text(encoding="utf-8")
a = "| 2026-09-26 | 放宽换手档 T2/T4 六席池实测：T2 成功 4.0；T4 三次平台故障（status=8 零节点 ×2 未计费、一次白付 6.0） | 10 | 1654.12 |\n| 2026-09-26 | （收到 10 算力礼包，余额 1654.12 起算；T2+T4 实付 10.0 后仍为 1654.12） | — | 1654.12 |"
b = "| 2026-09-26 | 收到 10 算力礼包（09-30 到期） | — | 1664.12 |\n| 2026-09-26 | 放宽换手档 T2/T4 六席池实测：T2 成功 4.0；T4 三次平台故障（status=8 零节点 ×2 未计费、一次白付 6.0） | 10 | 1654.12 |"
assert a in text
p.write_text(text.replace(a, b, 1), encoding="utf-8")
print("ledger rows reordered")