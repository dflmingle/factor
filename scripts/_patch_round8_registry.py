import io, sys, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
R = Path(r"D:\factor\research_reports\platform_alignment")
reg_path = R / "factor_alignment_failure_registry.json"
reg = json.loads(reg_path.read_text(encoding="utf-8"))

loc = {
 "K031": dict(net=0.126912133026123, turn=0.5310312509536743, rank_ic=0.0561, dec1=None),
 "K029": dict(net=0.1067544934272766, turn=0.6030830144882202, rank_ic=0.0512, dec1=None),
 "K013": dict(net=0.1367536790370941, turn=0.3125, rank_ic=0.0460, dec1=None),
 "K030": dict(net=0.0892079935312271, turn=0.4547895789146423, rank_ic=-0.0023, dec1=None),
}
for v in loc.values():
    v["gross"] = v["net"] + v["turn"] * 0.006 * 25.2

plat = {
 "K031": dict(run="6ab68ecab8f0d75493c83233", long=-8.75, turn=79.70, rank_ic=-0.0573, mono=0.94, p=0.0005,
              dec1=19.33, dec10=-8.75, ls=-28.08, formula="(POWER(10,26)*(((((CAL_5D_MIN_LOW_IDX/MA(CAL_5D_MIN_LOW_IDX,10))/BBIBOLL_DOWN)/CAL_20D_AMT_MA)/BS_TOTAL_ASSETS)/BS_TOTAL_ASSETS))",
              fields=["cal_5d_min_low_idx","bbiboll_down","cal_20d_amt_ma","bs_total_assets"],
              causes=["signed_denominator_interaction_not_reproducible","turnover_inflated_on_platform"],
              details=["分母含 BBIBOLL_DOWN（可为负的通道下轨），平台端方向与本地相反：单调性 0.94、RankIC -0.0573（p=0.0005）、分组1 +19.33% / 分组10 -8.75%。",
                       "换手从本地 53.1% 膨胀到平台 79.7%（+26.6pp），扣费后净额 -20.80%（本地 +12.69%）。",
                       "direction=0 反事后：分组1 gross +19.33%、换手 79.7% → 预测净额 ≈ +7.3%，且换手远超 40% 一票否决线 → 不具进池价值。",
                       "与 K020（corr/MA(corr)）、K029（ASI/MA(ASI)）同一病理：有符号近零序列做分母。"],
              flags=["large_net_delta","sign_flip_vs_local_proxy","turnover_mismatch"]),
 "K029": dict(run="6ab687c42d2f6998fc1bf777", long=4.09, turn=88.62, rank_ic=-0.0506, mono=0.69, p=0.1110,
              dec1=16.64, dec10=4.09, ls=-12.54, formula="(POWER(10,19)*(((((RATIO_BM_LYR/LOG(VMA250))/CAL_20D_AMT_MA)/QTYR_5_20)/(ASI(OPEN,CLOSE,HIGH,LOW,26,10)/MA(ASI(OPEN,CLOSE,HIGH,LOW,26,10),20)))/BS_TOTAL_ASSETS))",
              fields=["ratio_bm_lyr","vma250","cal_20d_amt_ma","qtyr_5_20","asi","bs_total_assets"],
              causes=["signed_denominator_interaction_not_reproducible","turnover_inflated_on_platform"],
              details=["分母含 ASI/MA(ASI,20)（有符号震荡指标穿过其均线时接近 0），平台端方向与本地相反：RankIC -0.0506、分组1 +16.64% / 分组10 +4.09%。",
                       "换手从本地 60.3% 膨胀到平台 88.6%（+28.3pp），扣费后净额 -9.31%（本地 +10.68%）。",
                       "direction=0 反事后：预测净额 ≈ +3.2%，不达 10% 门槛 → 不具进池价值。",
                       "预检脚本此前只拦 corr 分母，本例暴露 ASI 类有符号分母 → 已推广（signed_divisor 标记）。"],
              flags=["large_net_delta","sign_flip_vs_local_proxy","turnover_mismatch"]),
 "K013": dict(run="6ab690eccd820fa2a40a6c0f", long=-0.75, turn=90.88, rank_ic=-0.0019, mono=0.52, p=0.2627,
              dec1=-0.16, dec10=-0.75, ls=-0.58, formula="(POWER(10,34)*((((((MAADTM-TS_MIN(MAADTM,50))/CAL_20D_AMT_MA)/BS_TOTAL_ASSETS)/CAL_20D_AMT_MA)/QTYR_5_20)/BS_TOTAL_ASSETS))",
              fields=["maadtm","cal_20d_amt_ma","bs_total_assets","qtyr_5_20"],
              causes=["degenerate_platform_factor_panel"],
              details=["平台端完全退化：十组换手 90.88%、RankIC -0.0019、单调性 0.52、多空 -0.58%，分1/分10 均≈0。",
                       "缩放 k=34（×1e34，原量级估算 ~6.25e-36）仍无法恢复区分度——缩放修正的已验证区间是 1e18~1e27，k>=30 不可靠。",
                       "本地净 13.68%、RankIC 0.0460、换手 31.3%（本地侧三项俱佳），平台不可复现。"],
              flags=["degenerate_panel","large_net_delta"]),
 "K030": dict(run="6ab6916acd820fa2a40a6c12", long=5.31, turn=79.22, rank_ic=0.0007, mono=0.03, p=0.7771,
              dec1=3.36, dec10=5.31, ls=1.95, formula="(POWER(10,17)*(((TS_SKEW(CFD_FLOW_PER_SHARE_TTM,30)/CAL_20D_AMT_MA)/QTYR_5_20)/BS_TOTAL_ASSETS))",
              fields=["cfd_flow_per_share_ttm","cal_20d_amt_ma","qtyr_5_20","bs_total_assets"],
              causes=["degenerate_platform_factor_panel","turnover_inflated_on_platform"],
              details=["平台端 rankIC 0.0007、单调性 0.03、分1 +3.36% / 分10 +5.31% → 无区分度；换手 79.2%（本地 45.5%）。",
                       "本地 RankIC 本就 ≈ -0.0023（收益来自非单调尾部效应），两端一致地弱 → 属'因子本身无横截面排序力'，不是平台特有故障。",
                       "该条为 kept 池中独立性冠军（rho 0.009、|corr_size| 0.006），说明'极低相关'与'可用'是两回事。"],
              flags=["no_cross_sectional_signal","turnover_mismatch"]),
}

rid = {
 "K031": "gp-platform-tests-20260925:next-batch/candidates_panda_b:GP0924-K031-cand0040-S26b",
 "K029": "gp-platform-tests-20260925:next-batch/candidates_panda:GP0924-K029-cand0192-S19",
 "K013": "gp-platform-tests-20260925:next-batch/candidates_panda_b:GP0924-K013-cand0099-S34b",
 "K030": "gp-platform-tests-20260925:next-batch/candidates_panda_c:GP0924-K030-cand0038-S17c",
}
name = {"K031":"GP0924-K031-cand0040-S26b","K029":"GP0924-K029-cand0192-S19",
        "K013":"GP0924-K013-cand0099-S34b","K030":"GP0924-K030-cand0038-S17c"}
report = {"K031":"gp-platform-tests-20260925/next-batch/candidates_panda_b.txt.state.json",
          "K029":"gp-platform-tests-20260925/next-batch/candidates_panda.txt.state.json",
          "K013":"gp-platform-tests-20260925/next-batch/candidates_panda_b.txt.state.json",
          "K030":"gp-platform-tests-20260925/next-batch/candidates_panda_c.txt.state.json"}

for K in ("K031","K029","K013","K030"):
    p = plat[K]; l = loc[K]
    net_pl = round(p["long"] - p["turn"]*0.006*25.2, 4)
    rec = {
        "id": rid[K], "name": name[K], "report": report[K], "handler": "gp_candidate_platform_syntax",
        "formula": p["formula"], "platform_run_id": p["run"],
        "platform_net_excess_pct": net_pl,
        "local_net_excess": l["net"],
        "local_net_delta_pp": round(l["net"]*100 - net_pl, 4),
        "platform_gross_excess": p["long"]/100,
        "local_gross_excess": round(l["gross"], 7),
        "local_gross_delta_pp": round(l["gross"]*100 - p["long"], 4),
        "platform_turnover": p["turn"]/100,
        "local_turnover": l["turn"],
        "turnover_alignment": "mismatch" if abs(p["turn"]/100 - l["turn"]) > 0.05 else "comparable",
        "rank_ic_delta": round(l["rank_ic"] - p["rank_ic"], 6),
        "period_coverage": 1.0,
        "alignment_quality": "field_or_path_mismatch" if p["causes"][0] != "degenerate_platform_factor_panel" else "degenerate_platform_factor_panel",
        "alignment_quality_flags": p["flags"],
        "attribution": {
            "acceptable_by_net_excess": False, "unacceptable_by_net_excess": True,
            "net_delta_pp": round(l["net"]*100 - net_pl, 4),
            "gross_delta_pp": round(l["gross"]*100 - p["long"], 4),
            "turnover_dominant": abs(p["turn"]/100 - l["turn"]) > 0.05,
            "cause_codes": p["causes"],
            "cause_details": p["details"],
            "formula_fields": p["fields"],
            "formula_operators": ["div","ma","power","corr"] if K=="K029" else ["div","ma","power"],
            "field_attribution": [],
        },
        "platform_group_excess": {"分组1": p["dec1"], "分组10": p["dec10"], "多空组合": p["ls"]},
        "platform_monotonicity": p["mono"], "platform_p_value": p["p"],
    }
    reg["unacceptable_records"].append(rec)
    print(K, "net_pl", net_pl, "delta", rec["local_net_delta_pp"])

notes = reg["field_evidence_notes"]
notes["bbiboll_down"] = ("2026-09-25 K031：BBIBOLL_DOWN 做分母 → 平台端方向翻转（单调 0.94、RankIC -0.0573）"
                         "且换手 53%→79.7%，本地不可复现。属'有符号近零分母'族（可为负的通道下轨）。")
old_asi = notes.get("asi", "")
notes["asi"] = (old_asi + " | 2026-09-25 K029：ASI/MA(ASI,20) 做分母 → 平台端方向翻转（RankIC -0.0506）"
                "且换手 60%→88.6%，本地不可复现；预检已把 ASI 纳入 signed_divisor 标记。")
notes["bbiboll_down_precheck"] = "scripts/platform_precheck.py 已把该族字段纳入 SIGNED_DIVISOR_FIELDS（2026-09-25）。"

reg["signed_denominator_evidence"] = {
    "note": "2026-09-25 第八轮（5 条候选全跑，22 算力）：'分母含相关系数'规则已推广为'分母含相关系数/有符号近零序列'"
            "——平台端共同表现为【方向翻转 + 换手膨胀】，本地不可复现。",
    "cases": {
        "K020_cand0110": {"divisor": "corr/MA(corr,40)", "symptom": "方向反（|IC| 匹配）+ 换手 40%→73%",
                          "status": "direction=0 后平台净 +13.28%（可用但结构脆弱）"},
        "K029_cand0192": {"divisor": "ASI/MA(ASI,20)", "symptom": "方向反 + 换手 60%→88.6%",
                          "status": "direction=0 预测净 ≈ +3.2% → 弃"},
        "K031_cand0040": {"divisor": "BBIBOLL_DOWN", "symptom": "方向反（单调 0.94）+ 换手 53%→79.7%",
                          "status": "direction=0 预测净 ≈ +7.3%、换手超线 → 弃"},
    },
    "precheck_upgrade": "scripts/platform_precheck.py：新增 SIGNED_DIVISOR_FIELDS 与 signed_divisor 标记；"
                        "回归样本 round2/round4/round5 与 next-batch 全部按预期命中或不误报。",
    "pool_rescreen": "kept 149 条中 25 条分母含 corr/有符号字段；在旧门槛（net>=8%、2026>=3%、换手<=62%、"
                     "rho<=0.55、|size|<=0.55、簇内最佳）上再排除脆弱分母后只剩 2 条：K024（已平台通过 +6.51%）、"
                     "K030（本地/平台两端 rankIC≈0，无横截面排序力）。",
    "reproduced_candidate": {
        "name": "GP0924-K024-cand0026-S27b", "run_id": "6ab69093b8f0d75493c8323a",
        "platform_net_excess_pct": 6.51, "platform_turnover": 0.5503, "platform_rank_ic": 0.0194,
        "local_net_excess": 0.0863360856771469, "net_delta_pp": 2.12,
        "note": "方向一致（分1 +11.91% / 分10 +14.83%）、换手 53.5%→55.0%；但 IC 不显著（p=0.81）、单调性 0.31 → "
                "平台可复现但偏弱，未达 10% 净额门槛。",
    },
    "run_attempt_stats": {"total_attempts": 10, "dead_runs_status8": 5,
                          "note": "平台侧 50% 的 run 死于 status=8/零节点（不计费）；换全新 factor 重试均成功（K031/K024/K013/K030 各验证一次）。"},
}

reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("registry records now:", len(reg["unacceptable_records"]))