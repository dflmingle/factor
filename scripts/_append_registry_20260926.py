"""Append the 2026-09-26 pool-level mismatch (T2 as 6th seat) to the alignment failure registry."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path("D:/factor")
REG = ROOT / "research_reports/platform_alignment/factor_alignment_failure_registry.json"

record = {
    "id": "platform_pool_tests_20260926:pool6-t2t4-v2:POOL6-T2V2-20260926",
    "name": "POOL6-T2V2-20260926",
    "kind": "pool_level_seat_addition",
    "report": "platform_pool_tests_20260926/pool6-t2t4-v2-20260926-candidates.txt.state.json",
    "handler": "pool6_seat_addition",
    "formula": "(1/((TS_MEDIAN(AMOUNT,10)-STDDEV(TS_MEDIAN(STDDEV(VOL250,30),40),30))))",
    "platform_run_id": "6ab75e8fcd820fa2a40a6cbe",
    "platform_factor_id": "6ab75e8d9e9d797cfb2cf878",
    "baseline_pool_run_id": "6ab254c08b01f62dc5147d3a",
    "platform_pool_gross_excess": 0.2058,
    "platform_pool_net_excess": 0.1793,
    "platform_pool_turnover_per_rebalance": 0.175,
    "platform_pool_sharpe": 1.1509,
    "platform_pool_max_drawdown": 0.2628,
    "baseline_pool_net_excess": 0.2030,
    "baseline_pool_turnover_per_rebalance": 0.1339,
    "net_delta_pp": -2.37,
    "local_pool_delta_points_local": 482.0,
    "local_pool_delta_points_uplifted": 655.0,
    "platform_pool_delta_points_ex_nb": -2330.0,
    "local_net_delta_pp": 37.1,
    "alignment_quality": "pool_level_marginal_seat_mismatch",
    "alignment_quality_flags": ["overstated_local_A_proxy", "turnover_floor_crossing"],
    "attribution": {
        "acceptable_by_net_excess": False,
        "unacceptable_by_net_excess": True,
        "net_delta_pp": -2.37,
        "turnover_dominant": True,
        "cause_codes": [
            "pool_level_A_proxy_overstated",
            "turnover_floor_crossing",
            "no_NB_model_in_local_sim",
        ],
        "cause_details": [
            "本地逐月官方口径模拟给 T2 加席 +482（local）/ +655（uplifted）分/月，其中 A 项 +489/+662 全部来自假设 '池 rawA 上移 (s6-rawA)/6'。平台实测池级 IC 反而变差：RankIC 0.0919->0.0893、P(IC>0.02) 70.83%->63.87%、IC_IR 0.3675->0.3764；用同一池级 rawA(=RankIC*IC_IR*win) 代理法（对 base 复现 0.02589 fixture）得 dNA=-0.031，即 A 侧 -269 分/月，与本地 +489~662 反号。",
            "C 侧：gross 22.32%->20.58%、净 20.30%->17.93%（-2.37pp）、每次调仓换手 13.39%->17.50%。月度口径复核（平台自身每期净值曲线复利到月）：月均超额 1.24%->1.16%、中位 1.37%->1.23%、负额月数同为 15/60、T2 占优月 28/60 —— 没有 '逐月 T* 抬得动' 的证据。",
            "换手跨过 0.30 地板：2 调仓月基线 T=0.268<0.30（无惩罚），加 T2 后 0.35>0.30 -> rawC 分母惩罚 0.857；3 调仓月 0.402->0.525。全期 DD 代理桥 dNC=-0.104（-2,060 分/月），月度 DD 口径会软化 DD 项，但 Rex 与换手两项仍为负 -> 符号稳健。",
            "T2 唯一改善项是 Sharpe（1.0648->1.1509）与全期 MaxDD（31.64%->26.28%）；官方 C 用当月日频 MaxDD（量级远小于全期），该改善在月频 C 中几乎不产生分数。",
            "结论：'放宽换手' 假设（T2 作第 6 席）在平台端被证伪；本地逐月重算机器仍系统性高估候选边际（与 09-24 AGG 对靶同向，AGG 本地 +666 vs 平台可归因 A+C≈-254）。",
        ],
        "formula_fields": ["amount", "vol250"],
        "formula_operators": ["inv", "sub", "ts_median", "stddev"],
        "field_attribution": [],
    },
    "platform_group_excess": {"分组1": -14.73, "分组10": 20.58, "多空组合": 35.32},
    "platform_monotonicity": 0.98,
    "platform_p_value": 0.0001,
    "notes": "T4 (POOL6-T4V5) 未能取得可用结果：平台 status=8 零节点 x2 + '获取运行详情失败'（该次仍计费 6.0），不进入结论。",
}

payload = json.loads(REG.read_text(encoding="utf-8"))
ids = {r.get("id") for r in payload["unacceptable_records"]}
if record["id"] in ids:
    print("record already present, skipping")
else:
    payload["unacceptable_records"].append(record)
    summary = payload.get("summary", {})
    summary["unacceptable_records"] = len(payload["unacceptable_records"])
    payload["summary"] = summary
    REG.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("appended record; total unacceptable_records =", len(payload["unacceptable_records"]))