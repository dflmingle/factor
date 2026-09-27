import pathlib

p = pathlib.Path(r"D:\factor\scripts\ab_batch_20260925.py")
t = p.read_text(encoding="utf-8")
old = '''            scen.append(dict(candidate=name, tag=tag, d_comb=m["pool_comb"] - base["pool_comb"],
                             d_points=POINTS * (m["pool_comb"] - base["pool_comb"]),
                             d_net=m["pool_net"] - base["pool_net"],
                             d_turn=m["pool_turnover"] - base["pool_turnover"],
                             turn_excess=m["T_monthly_k2"] - m["T_cap"], **m))
'''
new = '''            scen.append(dict(candidate=name, tag=tag, d_comb=m["pool_comb"] - base["pool_comb"],
                             d_points=POINTS * (m["pool_comb"] - base["pool_comb"]),
                             d_na=m["pool_na"] - base["pool_na"],
                             d_nc=m["pool_nc"] - base["pool_nc"],
                             d_comb_nc_only=0.45 * (m["pool_nc"] - base["pool_nc"]),
                             d_points_nc_only=POINTS * 0.45 * (m["pool_nc"] - base["pool_nc"]),
                             d_net=m["pool_net"] - base["pool_net"],
                             d_turn=m["pool_turnover"] - base["pool_turnover"],
                             turn_excess=m["T_monthly_k2"] - m["T_cap"], **m))
'''
assert old in t
t = t.replace(old, new, 1)
p.write_text(t, encoding="utf-8")
import ast
ast.parse(t)
print("patched ok")