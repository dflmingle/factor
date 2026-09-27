import io, sys, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

root = Path(r"D:\factor")
R = root / "research_reports" / "platform_alignment"
G = R / "gp-platform-tests-20260925"

# local references (from round1 summary / candidate_matches)
loc = {"K015": dict(net=0.1049, turn=0.453, rank_ic=0.0373),
       "K020": dict(net=0.1339, turn=0.399, rank_ic=0.0360)}
for k, v in loc.items():
    v["gross"] = v["net"] + v["turn"] * 0.006 * 25.2
    print(k, "local gross", round(v["gross"]*100, 2), "net", round(v["net"]*100, 2))

# platform results
k015 = dict(gross=17.27, turn=45.72, rank_ic=0.0357, ic_mean=0.0081, ic_ir=0.3373, ir=0.5558,
            p=0.0003, mono=0.76, win=65.0, net=17.27-45.72*0.006*25.2,
            decile_excess=[2.14,-8.59,-9.42,-9.01,-5.46,-3.75,0.11,4.74,11.49,17.27],
            decile_turn=[57.32,54.66,54.36,59.24,63.85,66.43,67.22,65.95,60.95,45.72],
            ls=15.13, ls2=20.09)
k020 = dict(gross=3.79, turn=72.99, rank_ic=-0.0352, ic_mean=-0.0084, ic_ir=-0.3346, ir=-0.5845,
            p=0.0004, mono=0.70, win=58.33, net=3.79-72.99*0.006*25.2,
            decile_excess=[19.44,9.95,4.08,-1.17,-4.16,-6.74,-9.20,-8.29,-8.18,3.79],
            decile_turn=[40.50,58.29,63.09,64.05,64.16,67.39,73.94,72.93,73.12,72.99],
            ls=-15.64, ls2=-18.13)
print("K015 plat net", round(k015["net"],2), "delta", round(loc["K015"]["net"]*100-k015["net"],2))
print("K020 plat net", round(k020["net"],2), "delta", round(loc["K020"]["net"]*100-k020["net"],2),
      "| flip net(direction 0) pred:", round(k020["decile_excess"][0] - k020["decile_turn"][0]*0.006*25.2, 2))

reg_path = R / "factor_alignment_failure_registry.json"
reg = json.loads(reg_path.read_text(encoding="utf-8"))
ev = reg["magnitude_remediation_evidence"]
ev["follow_up_20260925"] = {
    "note": "量级归一规则在 K015/K020 上的复测（round5，8 算力）",
    "K015_cand0003_S24": {
        "formula": "(POWER(10,24)*((((DAVOL5/CAL_30D_RET_VOL_CORR)/CAL_20D_AMT_MA)/AMOUNT)/BS_TOTAL_ASSETS))",
        "scale_basis": "本地抽样估算原量级 ~2.6e-25（成交额中位数 1e8 元、总资产中位数 3.8e9 元、corr~0.1）",
        "run_id": "6ab667df9e9d797cfb2cf769", "platform_net_excess_pct": round(k015["net"], 4),
        "platform_gross_excess_pct": k015["gross"], "platform_turnover": k015["turn"]/100,
        "rank_ic": k015["rank_ic"], "monotonicity": k015["mono"],
        "local_net_excess": loc["K015"]["net"], "net_delta_pp": round(loc["K015"]["net"]*100 - k015["net"], 4),
        "outcome": "RESOLVED_ACCEPTABLE",
    },
    "K020_cand0110_S27": {
        "formula": "(POWER(10,27)*((((RATIO_BM_LYR/(CAL_30D_PRICE_VOL_CORR/MA(CAL_30D_PRICE_VOL_CORR,40)))/CAL_20D_AMT_MA)/BS_TOTAL_ASSETS)/BS_TOTAL_ASSETS))",
        "scale_basis": "本地抽样估算原量级 ~3.5e-28",
        "run_id": "6ab66841a8ba1ed343bf7e04", "platform_net_excess_pct": round(k020["net"], 4),
        "platform_gross_excess_pct": k020["gross"], "platform_turnover": k020["turn"]/100,
        "rank_ic": k020["rank_ic"], "monotonicity": k020["mono"],
        "local_net_excess": loc["K020"]["net"], "net_delta_pp": round(loc["K020"]["net"]*100 - k020["net"], 4),
        "outcome": "SIGN_FLIP_VS_LOCAL",
        "sign_flip_evidence": {
            "abs_rank_ic_platform": 0.0352, "rank_ic_local": loc["K020"]["rank_ic"],
            "detail": "量级问题已解决（不再退化：换手 40.5%~73.9%、单调性 0.70、RankIC 显著 p=0.0004），"
                      "但平台端因子方向与本地**相反**：分组1（最低值端）年化超额 +19.44%、分组10 +3.79%、多空 -15.64%；"
                      "|RankIC| 0.0352 与本地 0.0360 几乎相同。方向翻转后（direction=0）预测净额 ≈ +13.3%（本地 13.39%）。",
        },
    },
}
reg["field_evidence_notes"]["ratio_bm_lyr"] = (
    "2026-09-25 round5：K020 缩放版在平台端方向与本地相反（|RankIC| 匹配），嫌疑为 ratio_bm_lyr 或 "
    "cal_30d_price_vol_corr 的符号约定与本地代理不同；待 direction=0 重测确认。")
reg["field_evidence_notes"]["cal_30d_price_vol_corr"] = (
    "2026-09-25 round5：K020 方向翻转的另一个嫌疑字段（价量相关符号约定）；本地为代理实现。")
for rec in reg["unacceptable_records"]:
    if rec["id"].endswith("K015-cand0003-P"):
        rec["attribution"]["superseded_by"] = "magnitude_remediation_evidence:follow_up_20260925:K015_cand0003_S24"

rec_new = {
    "id": "gp-platform-tests-20260925:round5/candidates_panda:GP0924-K020-cand0110-S27",
    "name": "GP0924-K020-cand0110-S27",
    "report": "gp-platform-tests-20260925/round5/candidates_panda.txt.state.json",
    "handler": "gp_candidate_platform_syntax",
    "formula": ev["follow_up_20260925"]["K020_cand0110_S27"]["formula"],
    "platform_run_id": "6ab66841a8ba1ed343bf7e04",
    "platform_net_excess_pct": round(k020["net"], 4),
    "local_net_excess": loc["K020"]["net"],
    "local_net_delta_pp": round(loc["K020"]["net"]*100 - k020["net"], 4),
    "platform_gross_excess": k020["gross"]/100,
    "local_gross_excess": loc["K020"]["gross"],
    "local_gross_delta_pp": round(loc["K020"]["gross"]*100 - k020["gross"], 4),
    "platform_turnover": k020["turn"]/100,
    "local_turnover": loc["K020"]["turn"],
    "turnover_alignment": "mismatch",
    "rank_ic_delta": round(loc["K020"]["rank_ic"] - k020["rank_ic"], 6),
    "period_coverage": 1.0,
    "alignment_quality": "field_or_path_mismatch",
    "alignment_quality_flags": ["large_net_delta", "sign_flip_vs_local_proxy", "unexplained_net_delta"],
    "attribution": {
        "acceptable_by_net_excess": False, "unacceptable_by_net_excess": True,
        "net_delta_pp": round(loc["K020"]["net"]*100 - k020["net"], 4),
        "gross_delta_pp": round(loc["K020"]["gross"]*100 - k020["gross"], 4),
        "turnover_dominant": False,
        "cause_codes": ["sign_flip_vs_local_proxy"],
        "cause_details": [
            "量级归一后（×1e27）退化消失：十组换手 40.5%~73.9%、单调性 0.70、RankIC -0.0352（p=0.0004）——与 K015/K021 的完全退化不同。",
            "平台端方向与本地相反：分组1 +19.44% / 分组10 +3.79% / 多空 -15.64%；本地 rank_ic +0.0360，平台 -0.0352，绝对值几乎一致。",
            "嫌疑字段：ratio_bm_lyr（B/M vs M/B 约定）或 cal_30d_price_vol_corr（价量相关符号）；两者均为本地代理实现。",
            "待办：以 direction=0 重跑确认（预计净额 ≈ +13.3%，接近本地 13.39%）。",
        ],
        "formula_fields": ["ratio_bm_lyr", "cal_30d_price_vol_corr", "cal_20d_amt_ma", "bs_total_assets"],
        "formula_operators": ["div", "ma", "power"],
        "field_attribution": [
            {"field": "ratio_bm_lyr", "role": "local_proxy_field", "confidence": "medium",
             "avoid_by_default": False, "reason": "方向翻转的头号嫌疑（B/M 约定）。"},
            {"field": "cal_30d_price_vol_corr", "role": "local_proxy_field", "confidence": "medium",
             "avoid_by_default": False, "reason": "方向翻转的次号嫌疑（价量相关符号）。"},
        ],
    },
}
reg["unacceptable_records"].append(rec_new)
reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("registry records:", len(reg["unacceptable_records"]))
