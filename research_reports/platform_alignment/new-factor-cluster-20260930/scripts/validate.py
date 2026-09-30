import re, sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, "/data/games/factor_/scripts")
import gp_candidates_vs_clusters_20260924 as M
import alphaprobe_gp_tushare as gp

ns = gp.expression_namespace()
ns.update({"DELAY": ns["Ref"], "ZSCORE": M.CrossZScore, "IF": M.IfElse, "ZScore": M.CrossZScore})
M.patch_expression_comparisons()
M.wrap_field_leaves(ns)

members = pd.read_csv("/tmp/factor_cluster_20260930/members77.csv")
cands = pd.read_csv("/tmp/factor_cluster_20260930/nf_candidates.csv")
problems = []
for kind, frame, fcol in (("member", members, "factor_a_formula"), ("cand", cands, "formula")):
    for _, row in frame.iterrows():
        f = str(row[fcol])
        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", f)
        name_ok = True
        for tok in tokens:
            if tok in {"True", "False", "None"}:
                continue
            if tok not in ns:
                problems.append((kind, row.get("name", row.get("band")), f"missing name {tok}", f[:100]))
                name_ok = False
        if not name_ok:
            continue
        try:
            compile(f, "<f>", "eval")
        except SyntaxError as exc:
            problems.append((kind, row.get("name", row.get("band")), f"syntax {exc}", f[:100]))
            continue
        try:
            expr = gp.evaluate_formula(f, ns)
            _ = str(expr)  # ensure tree materialised
        except Exception as exc:
            problems.append((kind, row.get("name", row.get("band")), f"{type(exc).__name__}: {exc}", f[:100]))
print("problems:", len(problems))
for p in problems:
    print(" *", p[0], p[1], "::", p[2], "::", p[3])
print("members:", len(members), "candidates:", len(cands), "-> all parse OK" if not problems else "FIX NEEDED")
