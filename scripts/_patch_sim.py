from pathlib import Path
p = Path(r"D:/factor/scripts/turnover_relaxed_pool_sim_20260926.py")
t = p.read_text(encoding="utf-8")
pairs = [
 ("for step in range(1, CYCLE + 1):", "for step in range(2, CYCLE + 2):"),
 ('if step == 1 and np.isfinite(row["turnover"]):', 'if step == 2 and np.isfinite(row["turnover"]):'),
 ("turnover = np.nan if not previous else 1.0 - len(current & previous) / len(current)",
  "turnover = 0.5 if not previous else 1.0 - len(current & previous) / len(current)"),
 ('signal_frame, {"cand": flat}, [{"handler": "cand", "direction": 1}])\n        score_frame = pd.concat([seats, pd.Series(cand_score, name="cand")], axis=1)',
  'signal_frame, {"cand": flat}, [{"key": "cand", "handler": "cand", "direction": 1}])\n        score_frame = pd.concat([seats, cand_score], axis=1).loc[:, keys]'),
]
for old, new in pairs:
    if old not in t:
        raise SystemExit("MISSING: " + old[:70])
    t = t.replace(old, new)
p.write_text(t, encoding="utf-8")
print("patched")