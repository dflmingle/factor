import io, sys, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"D:\factor\scripts")
import alphaprobe_gp_tushare as gp

cands = {
    "K008-cand0000": "Inv(Sub(a_share_market_val,TsStd(TsMax(is_operate_profit,10),30)))",
    "K015-cand0003": "Div(Div(Div(Div(davol5,cal_30d_ret_vol_corr),cal_20d_amt_ma),amount),bs_total_assets)",
    "K020-cand0110": "Div(Div(Div(Div(ratio_bm_lyr,TsDiv(cal_30d_price_vol_corr,40)),cal_20d_amt_ma),bs_total_assets),bs_total_assets)",
}
fields = gp.formula_field_name_set(include_period_variants=True)
print("field set size", len(fields))
for probe in ["davol5", "DAVOL5", "a_share_market_val", "cal_20d_amt_ma", "ratio_bm_lyr"]:
    print("  field", probe, probe.lower() in fields)
print()
for name, formula in cands.items():
    try:
        out = gp.expression_to_panda_formula(formula)
    except Exception as exc:
        out = f"ERROR {type(exc).__name__}: {exc}"
    print(f"{name}:\n  local : {formula}\n  panda : {out}\n")