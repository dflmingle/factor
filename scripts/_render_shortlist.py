import io, sys, re, glob, os, csv
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor"); sys.path.insert(0, str(ROOT/"scripts"))
import platform_precheck as pp
import alphaprobe_gp_tushare as gp

refs = ROOT/"vendor/skill-pandaai-factor-online/references"
catalog = set()
for fn in glob.glob(str(refs/"fields*.md")):
    for line in open(fn, encoding="utf-8"):
        m = re.match(r"^\|\s*`([A-Za-z_][A-Za-z0-9_]*)`", line)
        if m: catalog.add(m.group(1).lower())
proxies = gp.formula_field_name_set(include_period_variants=True)
OPS = pp.load_platform_ops()

LOCAL = {
 "cand0040": "Div(Div(Div(Div(TsDiv(cal_5d_min_low_idx,10),bbiboll_down),cal_20d_amt_ma),bs_total_assets),bs_total_assets)",
 "cand0192": "Div(Div(Div(Div(Div(ratio_bm_lyr,Log(vma250)),cal_20d_amt_ma),qtyr_5_20),TsDiv(asi,20)),bs_total_assets)",
 "cand0038": "Div(Div(Div(TsSkew(cfd_flow_per_share_ttm,30),cal_20d_amt_ma),qtyr_5_20),bs_total_assets)",
 "cand0026": "Div(Div(Div(Div(ratio_bm_lyr,TsDelta(TsRank(TsMax(ev_lf,40),20),30)),cal_20d_amt_ma),bs_total_assets),bs_total_assets)",
 "cand0099": "Div(Div(Div(Div(Div(TsMinDiff(maadtm,50),cal_20d_amt_ma),bs_total_assets),cal_20d_amt_ma),qtyr_5_20),bs_total_assets)",
}
META = {
 "cand0040": ("K031","GP0924-K031-cand0040"),
 "cand0192": ("K029","GP0924-K029-cand0192"),
 "cand0038": ("K030","GP0924-K030-cand0038"),
 "cand0026": ("K024","GP0924-K024-cand0026"),
 "cand0099": ("K013","GP0924-K013-cand0099"),
}
out_dir = ROOT/"research_reports/platform_alignment/gp-platform-tests-20260925/next-batch"
out_dir.mkdir(exist_ok=True)
lines = []
for c,(K,tag) in META.items():
    local = LOCAL[c]
    k = pp.analyze(c, local, OPS)["k"]
    panda = gp.expression_to_panda_formula(local)
    if re.search(r"\bASI\b(?!\()", panda):
        panda = re.sub(r"\bASI\b(?!\()", "ASI(OPEN,CLOSE,HIGH,LOW,26,10)", panda)
        fix = " + ASI算子化"
    else:
        fix = ""
    scaled = f"(POWER(10,{k})*{panda})" if k else panda
    chk = pp.analyze(c, scaled, OPS)
    names = sorted({n for n in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", scaled) if not n.isdigit()})
    missing = [n for n in names if n.lower() not in catalog and n.lower() not in proxies and n.lower() not in OPS and n.upper() not in {"POWER","MA","LOG"}]
    line = f"{tag}-S{k} ~ {scaled} ~ 1"
    lines.append(line)
    print(f"[{c} / {K}] k={k}{fix}  费用={chk['cost']}  脆弱={chk['fragile'] or '-'}  撞名={chk['collisions'] or '-'}")
    print(f"   {scaled}")
    if missing: print(f"   ⚠ 字段不在参考目录: {missing}")
(out_dir/"candidates_panda.txt").write_text("\n".join(lines)+"\n", encoding="utf-8")
print("\nwritten:", out_dir/"candidates_panda.txt")