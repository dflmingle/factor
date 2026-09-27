import pathlib
p = pathlib.Path(r"D:\factor\scripts\not_new_clusters_20260925.py")
t = p.read_text(encoding="utf-8")
old = 'm=row.best_member, net=row.best_net,\n'
new = 'm=row.best_member,\n                net=f"{row.best_net:.3f}" if np.isfinite(row.best_net) else "n/a",\n'
n1 = t.count(old)
t = t.replace(old, new)
old_fmt = '"| {c} | {n} | {m} | {net:.3f} | {y} | {b} | {kc} | {kf} | {r:.3f} |".format('
n2 = t.count(old_fmt)
t = t.replace(old_fmt, '"| {c} | {n} | {m} | {net} | {y} | {b} | {kc} | {kf} | {r:.3f} |".format(')
p.write_text(t, encoding="utf-8")
print("patched", n1, n2)