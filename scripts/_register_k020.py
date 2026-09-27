import io, json, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
P = r"D:\factor\research_reports\platform_alignment\factor_alignment_failure_registry.json"
data = json.load(open(P, encoding="utf-8-sig"))

gross_platform = -0.74 / 100.0
turnover_platform = 0.9034
net_platform = gross_platform - turnover_platform * 0.006 * (252.0 / 10.0)
local_net = 0.1338881838798523
local_turnover = 0.3988119065761566
local_gross = local_net + local_turnover * 0.006 * (252.0 / 10.0)
local_rank_ic = 0.0360432006418705

record = {
    "id": "gp-platform-tests-20260925:candidates_panda:GP0924-K020-cand0110-P",
    "name": "GP0924-K020-cand0110-P",
    "report": "gp-platform-tests-20260925/candidates_panda.txt.state.json",
    "handler": "gp_candidate_platform_syntax",
    "formula": "((((RATIO_BM_LYR/(CAL_30D_PRICE_VOL_CORR/MA(CAL_30D_PRICE_VOL_CORR,40)))/CAL_20D_AMT_MA)/BS_TOTAL_ASSETS)/BS_TOTAL_ASSETS)",
    "platform_run_id": "6ab65af945ce44aed9d15639",
    "platform_net_excess_pct": net_platform * 100.0,
    "local_net_excess": local_net,
    "local_net_delta_pp": (local_net - net_platform) * 100.0,
    "platform_gross_excess": gross_platform,
    "local_gross_excess": local_gross,
    "local_gross_delta_pp": (local_gross - gross_platform) * 100.0,
    "platform_turnover": turnover_platform,
    "local_turnover": local_turnover,
    "turnover_alignment": "mismatch",
    "rank_ic_delta": 0.0008 - local_rank_ic,
    "period_coverage": 1.0,
    "alignment_quality": "field_or_path_mismatch",
    "alignment_quality_flags": [
        "large_net_delta",
        "turnover_not_comparable",
        "degenerate_platform_panel",
        "unexplained_net_delta",
    ],
    "attribution": {
        "acceptable_by_net_excess": False,
        "unacceptable_by_net_excess": True,
        "net_delta_pp": (local_net - net_platform) * 100.0,
        "gross_delta_pp": (local_gross - gross_platform) * 100.0,
        "turnover_dominant": True,
        "cause_codes": ["degenerate_platform_factor_panel"],
        "cause_details": [
            "与 K015 完全相同的退化签名：十组年化超额全部落在 -0.74%~+0.71%、每组换手 90.26%~90.35%、"
            "多空组合 -1.38%、RankIC 0.0008、IC_mean -0.0009、单调性 0.23；本地同公式换手 39.9%、"
            "RankIC 0.0360、净超额 13.39%。",
            "两条退化候选共用 CAL_20D_AMT_MA 与 BS_TOTAL_ASSETS，且都在除法链末端除以 1e8~1e10 量级的"
            "成交额/总资产（数值量级 1e-19~1e-28）；未退化的 K008 用同样式的除法但量级为 1e-10。"
            "疑似平台端数值表示/精度问题，未做单字段反事实验证。",
            "首次运行（17:03:13）失败原因为平台侧计费服务超时（页面提示：计费服务超时，请稍后重试），"
            "与公式无关；19:28 重跑成功并得到上述退化结果。",
        ],
        "formula_fields": [
            "ratio_bm_lyr",
            "cal_30d_price_vol_corr",
            "cal_20d_amt_ma",
            "bs_total_assets",
        ],
        "formula_operators": ["div", "ma"],
        "field_attribution": [
            {
                "field": "cal_20d_amt_ma",
                "role": "local_proxy_field",
                "confidence": "medium",
                "avoid_by_default": False,
                "reason": "两条退化记录（K015、K020）共用该字段；量级 1e8~1e10，是因子值降到 1e-28 的主因。",
            },
            {
                "field": "cal_30d_price_vol_corr",
                "role": "local_proxy_field",
                "confidence": "low",
                "avoid_by_default": False,
                "reason": "本地为代理实现；平台端行为未知。",
            },
            {
                "field": "ratio_bm_lyr",
                "role": "local_proxy_field",
                "confidence": "low",
                "avoid_by_default": False,
                "reason": "仅按公式出现位置登记为嫌疑字段。",
            },
            {
                "field": "bs_total_assets",
                "role": "financial_leaf",
                "confidence": "low",
                "avoid_by_default": False,
                "reason": "量级 1e10，与成交额连乘后进一步压低因子值量级。",
            },
        ],
        "alignment_flags": [
            "large_net_delta",
            "turnover_not_comparable",
            "degenerate_platform_panel",
            "unexplained_net_delta",
        ],
    },
}

data["unacceptable_records"] = [r for r in data["unacceptable_records"]
                                if r.get("id") != record["id"]]
data["unacceptable_records"].append(record)
notes = data.setdefault("field_evidence_notes", {})
notes["cal_20d_amt_ma"] = ("2026-09-25 K015 与 K020 两条平台退化记录的共用字段（含 BS_TOTAL_ASSETS）；"
                           "两条都因除法链量级降到 1e-28 而疑似在平台端失去区分度。按拉黑规则，该字段已有 "
                           "2 条 >5pp 记录且无 <=5pp 反例，达到可拉黑门槛——但建议先用一次放大量级的复跑做"
                           "反事实验证，再决定是否全局拉黑。")
json.dump(data, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("records:", len(data["unacceptable_records"]))
print("K020 net_delta_pp =", round(record["local_net_delta_pp"], 2))