import io, sys, re, glob, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"D:\factor\scripts")
import alphaprobe_gp_tushare as gp

fields = gp.formula_field_name_set(include_period_variants=True)
refs = r"D:\factor\vendor\skill-pandaai-factor-online\references"
catalog = set()
for fn in glob.glob(os.path.join(refs, "fields*.md")):
    text = open(fn, encoding="utf-8").read()
    for line in text.splitlines():
        m = re.match(r"^\|\s*`([A-Za-z_][A-Za-z0-9_]*)`", line)
        if m:
            catalog.add(m.group(1).lower())

local = {
    "cand0013": "Div(Div(Div(TsCorr(asi,vma3,30),cal_20d_amt_ma),qtyr_5_20),bs_total_assets)",
    "cand0038": "Div(Div(Div(TsSkew(cfd_flow_per_share_ttm,30),cal_20d_amt_ma),qtyr_5_20),bs_total_assets)",
    "cand0026": "Div(Div(Div(Div(ratio_bm_lyr,TsDelta(TsRank(TsMax(ev_lf,40),20),30)),cal_20d_amt_ma),bs_total_assets),bs_total_assets)",
}
for name, formula in local.items():
    panda = gp.expression_to_panda_formula(formula)
    print(f"{name}\n  local : {formula}\n  panda : {panda}")
    names = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", panda))
    bare = [n for n in names if n.lower() not in {"power","corr","ma","ts_skew","div"}]
    print("  fields:", sorted(bare))
    for n in sorted(bare):
        flag = "OK" if n.lower() in catalog else ("proxy" if n.lower() in fields else "MISSING")
        print(f"     {n:28s} {flag}")
    print(f"  scaled: POWER(10,18)*({panda})")
    print()