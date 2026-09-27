"""Register the 2026-09-25 platform-vs-local mismatch for K015/cand0003."""
import io, json, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

P = r"D:\factor\research_reports\platform_alignment\factor_alignment_failure_registry.json"
data = json.load(open(P, encoding="utf-8-sig"))

gross_platform = -0.13 / 100.0
turnover_platform = 0.9036
cost_platform = turnover_platform * 0.006 * (252.0 / 10.0)
net_platform = gross_platform - cost_platform
local_net = 0.1048909726381301
local_turnover = 0.4532970786094665
local_gross = local_net + local_turnover * 0.006 * (252.0 / 10.0)
local_rank_ic = 0.0372855886816978

record = {
    "id": "gp-platform-tests-20260925:candidates_panda:GP0924-K015-cand0003-P",
    "name": "GP0924-K015-cand0003-P",
    "report": "gp-platform-tests-20260925/candidates_panda.txt.state.json",
    "handler": "gp_candidate_platform_syntax",
    "formula": "((((DAVOL5/CAL_30D_RET_VOL_CORR)/CAL_20D_AMT_MA)/AMOUNT)/BS_TOTAL_ASSETS)",
    "platform_run_id": "6ab63731cd820fa2a40a6b87",
    "platform_net_excess_pct": net_platform * 100.0,
    "local_net_excess": local_net,
    "local_net_delta_pp": (local_net - net_platform) * 100.0,
    "platform_gross_excess": gross_platform,
    "local_gross_excess": local_gross,
    "local_gross_delta_pp": (local_gross - gross_platform) * 100.0,
    "platform_turnover": turnover_platform,
    "local_turnover": local_turnover,
    "turnover_alignment": "mismatch",
    "rank_ic_delta": 0.0 - local_rank_ic,
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
            "平台端十组年化超额全部落在 -1.62%~+0.71%，每组换手几乎相同（90.3%~90.5%），"
            "RankIC 0.0000、IC_mean -0.0003、单调性 0.07：因子在平台端退化为近似常数/随机分组；"
            "本地同一公式换手 45.3%、RankIC 0.0373、净超额 10.49%，两者不是同一对象。",
            "本地该公式依赖 local_proxy 字段（CAL 族全部是代理），平台端字段覆盖率/量级未做单字段反事实验证。",
        ],
        "formula_fields": [
            "davol5",
            "cal_30d_ret_vol_corr",
            "cal_20d_amt_ma",
            "amount",
            "bs_total_assets",
        ],
        "formula_operators": ["div"],
        "field_attribution": [
            {
                "field": "cal_30d_ret_vol_corr",
                "role": "local_proxy_field",
                "confidence": "low",
                "avoid_by_default": False,
                "reason": "本地为代理实现且 09-23 覆盖率清单标记为未在本地/平台验证；平台端行为未知。",
            },
            {
                "field": "cal_20d_amt_ma",
                "role": "local_proxy_field",
                "confidence": "low",
                "avoid_by_default": False,
                "reason": "本地为代理实现；平台端量级为元，与 AMOUNT、BS_TOTAL_ASSETS 连乘后因子值量级极小。",
            },
            {
                "field": "davol5",
                "role": "local_proxy_field",
                "confidence": "low",
                "avoid_by_default": False,
                "reason": "平台目录写作 DAVOL5/10/20 一行，运行未报未定义，但是否按 5 日口径返回未验证。",
            },
            {
                "field": "amount",
                "role": "market_data_leaf",
                "confidence": "low",
                "avoid_by_default": False,
                "reason": "历史证据显示 AMOUNT 单字段隔离偏差仅约 0.67pp，不单独归因。",
            },
            {
                "field": "bs_total_assets",
                "role": "financial_leaf",
                "confidence": "low",
                "avoid_by_default": False,
                "reason": "仅按公式出现位置登记为嫌疑字段。",
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

ids = [r.get("id") for r in data["unacceptable_records"]]
if record["id"] in ids:
    data["unacceptable_records"] = [r for r in data["unacceptable_records"]
                                    if r.get("id") != record["id"]]
data["unacceptable_records"].append(record)

notes = data.setdefault("field_evidence_notes", {})
notes["davol5"] = ("2026-09-25 K015-cand0003 平台端退化（RankIC 0.0000、十组换手同质 ~90.4%）；"
                   "单字段未做反事实验证，仅登记嫌疑。")
notes["cal_30d_ret_vol_corr"] = ("2026-09-25 K015-cand0003 平台端退化；该字段本地为代理、"
                                 "09-23 覆盖率清单未标记任何平台验证。")
notes["cal_20d_amt_ma"] = ("2026-09-25 K015-cand0003 平台端退化；与 AMOUNT/BS_TOTAL_ASSETS 连乘后"
                           "因子值量级约 1e-28，疑似平台端数值表示问题，未验证。")

json.dump(data, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("registry records:", len(data["unacceptable_records"]))
print("added:", record["id"], "net_delta_pp =", round(record["local_net_delta_pp"], 2))