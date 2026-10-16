"""Review the completed approved batch; only reads saved backtest outputs."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "pool-incumbent-corrections-20261012"


def main():
    results = pd.read_csv(OUT / "pool_results.csv")
    new = results[results.candidate.ne("BASE")].copy()
    formal = new[new.window.eq("formal_5y")].set_index("candidate")
    new["delta_NA_five_year_proxy"] = new.candidate.map(formal.delta_NA_proxy)
    # Official A does not turn into a 15-period statistic in the recent window.
    # Show the recent path with a fixed five-year A proxy as an additional sensitivity.
    new["mean_delta_AC_fixed_five_year_A_proxy"] = .20*new.delta_NA_five_year_proxy + .45*new.mean_delta_NC
    new["minimum_delta_NB_fixed_five_year_A_breakeven"] = -new.mean_delta_AC_fixed_five_year_A_proxy/.35
    new.to_csv(OUT / "score_review.csv", index=False)
    sensitivities = []
    for row in new.itertuples():
        for dnb in (-.10, -.05, -.02, 0., .02, .05):
            sensitivities.append(dict(candidate=row.candidate, window=row.window,
                assumed_delta_NB=dnb, deltaComb_fixed_A_scenario=row.mean_delta_AC_fixed_five_year_A_proxy+.35*dnb,
                note="scenario only; neither observed B nor official increment"))
    pd.DataFrame(sensitivities).to_csv(OUT / "B_sensitivity_fixed_A.csv", index=False)
    acceptance = []
    for candidate, f in formal.iterrows():
        r = new[(new.candidate.eq(candidate)) & (new.window.eq("recent_2026"))].iloc[0]
        checks = dict(five_year_net_positive=bool(f.delta_net>0),
            five_year_drawdown_not_worse=bool(f.delta_dd<=0),
            five_year_turnover_increase_at_most_2pp=bool(f.delta_turnover<=.02),
            five_year_size_guard=bool(f.size_guard),
            five_year_AC_positive=bool(f.mean_delta_AC_proxy>0),
            recent_AC_fixed_five_year_A_positive=bool(r.mean_delta_AC_fixed_five_year_A_proxy>0),
            recent_size_guard=bool(r.size_guard))
        acceptance.append(dict(candidate=candidate, **checks,
            all_predeclared_local_gates_pass=all(checks.values()),
            five_year_net_95_interval_excludes_zero=bool(f.bootstrap_95_low>0)))
    gates = pd.DataFrame(acceptance)
    gates.to_csv(OUT / "acceptance.csv", index=False)

    # These are path descriptions from existing ledgers, not extra strategies.
    dd_rows = []
    for row in results.itertuples():
        daily = pd.read_csv(OUT / f"{row.candidate}_{row.window}_daily.csv", parse_dates=["date"])
        nav = np.r_[1., np.cumprod(1.+daily.portfolio.to_numpy())]
        running = np.maximum.accumulate(nav)
        trough = int(np.argmin(nav/running))
        peak = int(np.argmax(nav[:trough+1]))
        dd_rows.append(dict(candidate=row.candidate, window=row.window,
            max_dd=float(1.-nav[trough]/running[trough]),
            peak_date="initial_NAV_1" if peak==0 else str(daily.date.iloc[peak-1].date()),
            trough_date="initial_NAV_1" if trough==0 else str(daily.date.iloc[trough-1].date())))
    pd.DataFrame(dd_rows).to_csv(OUT / "drawdown_events.csv", index=False)
    monthly = pd.read_csv(OUT / "pool_monthly_deltas.csv")
    worst = []
    for (candidate, window), m in monthly.groupby(["candidate", "window"]):
        for kind, field in (("worst_baseline_Rex", "rex_base"), ("worst_delta_NC", "delta_NC")):
            worst.append(m.sort_values(field).head(5).assign(selection=kind))
    pd.concat(worst).to_csv(OUT / "worst_months.csv", index=False)
    annual = pd.read_csv(OUT / "annual_results.csv")
    base = annual[annual.candidate.eq("BASE")][["window", "year", "net_excess"]].rename(columns={"net_excess":"base_net"})
    annual = annual.merge(base, on=["window", "year"], validate="many_to_one")
    annual["delta_net"] = annual.net_excess-annual.base_net
    annual.to_csv(OUT / "annual_comparison.csv", index=False)

    lines = [
        "# 现役五席固定：批准的三个 F 修正候选",
        "",
        "2026-10-12。P01 保留为最有依据的研究候选：五年与近期净超额及 A+C 代理均改善；但五年回撤和换手超过预设门槛，尚不构成换席依据。P02/P03 的轻量修正没有改善综合诊断。本轮三个候选完成后停止，没有自动扩大或重复选型，平台消耗 0。",
        "",
        "## 池级表现（本地归档共同截面）",
        "",
        "|方案|五年净超额|换手/次|日度扣费 NAV 最大回撤|市值中性净额|2026净超额|",
        "|---|---:|---:|---:|---:|---:|",
    ]
    labels = {"BASE":"现役基线", "P01_NORMALIZED_HARD_F":"P01 标准化硬 veto",
              "P02_BOUNDED_CONTINUOUS_F":"P02 小幅连续惩罚", "P03_HYSTERESIS_F":"P03 进出缓冲惩罚"}
    for row in results[results.window.eq("formal_5y")].itertuples():
        recent = results[(results.candidate.eq(row.candidate)) & (results.window.eq("recent_2026"))].iloc[0]
        lines.append(f"|{labels[row.candidate]}|{row.net_excess:.2%}|{row.turnover:.2%}|{row.daily_net_nav_max_dd:.2%}|{row.size_neutral_net:.2%}|{recent.net_excess:.2%}|")
    lines += ["", "P01 五年净超额提高 0.30pp，近期提高 0.58pp；五年最大回撤增加 0.87pp，换手增加 2.72pp，超过本轮最多 +2pp 的门槛。五年 size 绝对相关由 .8371 降至 .8047，桶内秩中性净额由 5.18% 升至 5.71%；近期也通过 size 守卫。它改变了约 9% 的持仓，平均持仓重合度为 90.98%。",
        "", "P02/P03 的五年增量分别只有 +0.11pp/+0.09pp，近期分别为 −0.27pp/−0.29pp。换手增量较小（五年 +0.12pp/+0.19pp），近期收益仍下降，说明当前弱修正的问题不能仅归咎于成本。它们与原 F 的信号相关为 .9986/.9962，池持仓重合度为 99.67%/99.40%，大部分原排序未改变。缓冲版本的池换手还略高于连续版本，因此本轮未证实缓冲能改善这个池的交易效率。",
        "", "## 完整分列的 A/C 代理与未知 B",
        "", "A 使用五个独立席位的 RankIC 序列派生 S_i 均值，不使用池复合 IC。近期的 15 期席位 S_i 另存用于诊断；下表固定五年 A，只更换近期 C 路径。所有数值均是本地代理，不是官方积分增量。",
        "", "|候选|五年 ΔNA|五年月均 ΔNC|五年 Δ(A+C)|近期 Δ(A+C)，固定五年 A|五年 ΔNB 盈亏平衡|",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for candidate, row in formal.iterrows():
        recent = new[(new.candidate.eq(candidate)) & (new.window.eq("recent_2026"))].iloc[0]
        lines.append(f"|{labels[candidate]}|{row.delta_NA_proxy:+.6f}|{row.mean_delta_NC:+.6f}|{row.mean_delta_AC_proxy:+.6f}|{recent.mean_delta_AC_fixed_five_year_A_proxy:+.6f}|{row.minimum_delta_NB_for_breakeven:+.6f}|")
    lines += ["", "盈亏平衡为 `ΔNB = −Δ(A+C)/0.35`。例如 P01 在这套五年代理下允许 ΔNB 最低约 −0.0451；这不是预测 B 会损失多少，更不能用历史 A 的增幅推定 B 增幅。P02/P03 五年 A+C 本身为负，需正 B 增量才能打平；目前没有该证据。换掉 F 或修改公式都会影响该席的 B 历史，现役池本轮没有被修改。",
        "", "P01 五年 ΔE（月内两腿分别复利年化后的差的均值）为 +1.47pp，月均漂移换手 ΔT 为 +5.36pp，ΔNC 为 −0.00254。58 个完整月中，基线 C 满分 32 月，P01 满分 31 月，其中原满分月损失 2 月、另补回 1 月；P02/P03 都保持 32 个满分月，但原非满分月的 C 恶化，不能靠满分月数量宣称收益无损。",
        "", "P01 近期只有 6 个完整月，C 满分由 1 月升至 2 月；近期 ΔNC 为 +0.0979。这个短段的 C 提升不能外推未来，也不能将 58 个月和 6 个月混排。",
        "", "## 稳定性和风险归因",
        "", "|候选|五年净额增量|描述性区块重采样95%区间|五年已列年度净额改善数|",
        "|---|---:|---:|---:|",
    ]
    for candidate, row in formal.iterrows():
        years = annual[(annual.candidate.eq(candidate)) & (annual.window.eq("formal_5y"))]
        lines.append(f"|{labels[candidate]}|{row.delta_net*100:+.2f}pp|[{row.bootstrap_95_low*100:+.2f}, {row.bootstrap_95_high*100:+.2f}]pp|{int((years.delta_net>0).sum())}/{len(years)}|")
    lines += ["", "年度 2021/2026 为不完整年份，不能当作完整六年独立验证。三种候选五年收益差的区间均跨零；区块重采样只描述已查看历史中的差异，没有消除之前选型偏差。P01 的正点估计值得保留，但尚未证明稳定优于现役池。",
        "", "## 本轮验收",
        "", "P01 通过五年净额、size 守卫、五年 A+C 和近期 A+C 检查；未通过五年回撤不恶化及换手增量最多 +2pp 两项。P02/P03 通过换手和五年回撤检查，但五年和近期 A+C 都为负。三个候选均未满足全部预设本地准入条件，因此不自动申请平台，不修改现役池，也不把未达标等同于路线已被证伪。",
        "", "这轮把方向缩小到了明确的问题：标准化硬过滤具有可研究的收益/质量增量，但会增加回撤与换仓；当前固定幅度的弱修正未保留足够增量。若后续研究，应在新协议中直接把现役池边际风险/收益作为训练和选型目标，而不是继续扫描这三个输出层的阈值和权重。",
        "", "## 口径、验证与产物",
        "", "名义五年窗口 20210907–20260907，120 个保存信号期实际到 2026-08-10、标签到 2026-08-25；近期从 20260101 起 15 期。沪深全 A 行情来源、qfq、total_mv、2018 暖机、label-1、10 日、10 组、factor_valid 基准和 0.30% 单边成本。共同截面要求五个归档席位有效，最低覆盖率 70.59%，所以这是归档诊断，不能声称完成正式全 A 平台池等价重建。",
        "", "净超额主表使用成员换手成本的算术年化；日度 NAV 与月度 C 使用实际漂移权重的买卖成本，二者单独保存。主表回撤为本地扣费日度 NAV 的回撤，不能和平台原多头组回撤直接相比。",
        "", "基线净额/换手/回撤/size/中性净额与上一轮保存基线逐项复现；三候选有效股票截面一致；原候选哈希未变；真实输出层未来扰动在第48/96期前逐值不变；收益差与区块重采样点估计闭合。没有重训树、扫描参数或调用平台。执行验证见 verification.json。",
        "", "主要产物：pool_results.csv、score_review.csv、acceptance.csv、pool_monthly_deltas.csv、annual_comparison.csv、paired_uncertainty.csv、seat_correlations.csv、drawdown_events.csv、worst_months.csv、B_sensitivity_fixed_A.csv，以及逐候选双窗口日度/逐期/月度/组收益账本。执行前源文件哈希和批准协议保存在 execution_protocol.json。",
    ]
    (OUT / "summary.md").write_text("\n".join(lines) + "\n")
    (OUT / "complete.json").write_text(json.dumps(dict(status="complete", candidate_count=3, platform_runs=0,
        report="summary.md", all_predeclared_local_gates_passed_candidates=gates[gates.all_predeclared_local_gates_pass].candidate.tolist()), indent=2) + "\n")
    print(gates.to_string(index=False))
    print(new[["candidate","window","mean_delta_AC_fixed_five_year_A_proxy","minimum_delta_NB_fixed_five_year_A_breakeven"]].to_string(index=False))
    print(pd.DataFrame(dd_rows).to_string(index=False))


if __name__ == "__main__":
    main()
