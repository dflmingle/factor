"""Retrospective public-metric score-fitting analysis; no new backtest or platform call."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SEARCH = HERE / "search"
SCALE = np.array([.02, .20, .10])

def main():
    rows = [json.loads(x) for x in (SEARCH / "symbolic_evaluations.jsonl").read_text().splitlines()]
    ev = pd.DataFrame([r for r in rows if r.get("status") == "evaluated"])
    targets = pd.read_csv(HERE / "factor_targets.csv")
    targets = targets[targets.period.eq("2026-10")].copy()
    x = ev[["rank_ic", "rank_ir", "rank_win"]].to_numpy(float)
    out = []
    for t in targets.itertuples():
        target = np.array([t.ic_mean, t.icir, t.ic_win_rate], float)
        dist = np.mean(((x - target) / SCALE) ** 2, axis=1)
        q = ev.assign(score_distance=dist).sort_values(["score_distance", "nodes", "formula"]).head(5)
        for rank, r in enumerate(q.itertuples(), 1):
            out.append({
                "target_display_name": t.display_name,
                "target_factor": t.factor_name,
                "target_ic": t.ic_mean,
                "target_ir": t.icir,
                "target_win": t.ic_win_rate,
                "match_rank": rank,
                "formula": r.formula,
                "local_ic": r.rank_ic,
                "local_ir": r.rank_ir,
                "local_win": r.rank_win,
                "score_distance": r.score_distance,
                "train_periods": r.periods,
                "local_net_excess": r.net_excess,
            })
    result = pd.DataFrame(out)
    result.to_csv(SEARCH / "score_fit_matches.csv", index=False)

    # First-order leaderboard proxy: replace one public counted seat while
    # holding that pool's B/C components and seat count fixed. This is useful
    # for score-shape comparison, but it is not a full pool backtest.
    pool = pd.read_csv(HERE / "pool_metrics.csv")
    pool = pool[pool.score_period.eq("2026-10")].copy()
    pool_by_name = pool.set_index("display_name")
    target_rows = targets[targets.display_name.isin(pool_by_name.index)].copy()
    candidate_stats = pd.read_csv(SEARCH / "single_results.csv")
    candidate_stats = candidate_stats[(candidate_stats.cycle == 3) & candidate_stats.window.eq("formal_5y")].set_index("candidate")
    board_rows = []
    for t in target_rows.itertuples():
        p = pool_by_name.loc[t.display_name]
        if not bool(t.counted) or not np.isfinite(t.s_i_a):
            continue
        n = float(p.denominator_a)
        if not np.isfinite(n) or n <= 0:
            continue
        for candidate, c in candidate_stats.iterrows():
            si = float(c.s_i)
            raw_a_proxy = float(p.raw_a) + (si - float(t.s_i_a)) / n
            na_proxy = min(raw_a_proxy / 0.08, float(p.new_pool_cap))
            comb_proxy = 0.20 * na_proxy + 0.35 * float(p.nb) + 0.45 * float(p.nc)
            points_proxy = comb_proxy * 40000.0 * float(p.newbie_factor)
            cumulative_proxy = float(p.cumulative_points) + (points_proxy - float(p.monthly_points))
            rank_proxy = int(1 + (pool.cumulative_points > cumulative_proxy).sum())
            board_rows.append({
                "candidate": candidate,
                "opponent": t.display_name,
                "target_factor": t.factor_name,
                "public_comb": p.comb,
                "proxy_comb": comb_proxy,
                "delta_comb": comb_proxy - p.comb,
                "public_monthly_points": p.monthly_points,
                "proxy_monthly_points": points_proxy,
                "delta_monthly_points": points_proxy - p.monthly_points,
                "public_rank": p["rank"],
                "proxy_rank": rank_proxy,
                "delta_rank": rank_proxy - int(p["rank"]),
                "public_na": p.na,
                "proxy_na": na_proxy,
                "public_nb": p.nb,
                "public_nc": p.nc,
                "candidate_s_i": si,
                "public_s_i_a": t.s_i_a,
            })
    board = pd.DataFrame(board_rows)
    board.to_csv(SEARCH / "leaderboard_score_proxy.csv", index=False)
    board_summary = board.groupby("candidate", sort=True).agg(
        rows=("candidate", "size"),
        mean_delta_comb=("delta_comb", "mean"),
        median_delta_comb=("delta_comb", "median"),
        mean_delta_points=("delta_monthly_points", "mean"),
        median_delta_points=("delta_monthly_points", "median"),
        mean_delta_rank=("delta_rank", "mean"),
        best_delta_rank=("delta_rank", "min"),
        positive_proxy_rows=("delta_comb", lambda x: int((x > 0).sum())),
    ).reset_index()
    board_summary.to_csv(SEARCH / "leaderboard_score_proxy_summary.csv", index=False)

    # Keep a compact set of the clearest examples showing that the same score shape
    # has several structurally different explanations.
    examples = []
    for name, factor in [
        ("不知所云队", "probe-illiquidity"),
        ("不知所云队", "probe-rsi_rev"),
        ("Alpha猎手", "oos-f_c_val_rev_oos"),
    ]:
        q = result[(result.target_display_name == name) & (result.target_factor == factor)].head(3)
        examples.extend(q.to_dict("records"))
    lines = [
        "# 公开指标的分数拟合检验（2026-10-12）", "",
        "本文件只使用已经完成的 600 个符号结构评估结果和公开汇总指标，没有新增回测、平台调用或池修改。距离定义与搜索阶段一致：",
        "`mean(((RankIC-local - target)/0.02)^2, ((IR-local - target)/0.20)^2, ((胜率-local - target)/0.10)^2)`。",
        "", "## 结论", "",
        "把公开 IC、IR、胜率带入计算，确实能找到分数非常接近的候选，因此‘指标形状可复现’是成立的。它仍不能证明恢复了对手的原公式：公开值只有三个汇总约束，而候选表达式空间远大于三个约束；不同结构可以落在同一分数邻域。",
        "",
        "## 典型近似", "",
        "|公开席位|目标因子|候选|本地 RankIC|本地 IR|本地胜率|距离|",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for r in examples:
        lines.append(f"|{r['target_display_name']}|{r['target_factor']}|`{r['formula']}`|{r['local_ic']:.4f}|{r['local_ir']:.4f}|{r['local_win']:.1%}|{r['score_distance']:.4f}|")
    lines += [
        "", "同一个公开目标的前三名通常不是同一类结构。例如不知所云队的 `probe-illiquidity`，`Add(lowamount20,reversal60)` 与 `Add(smallsize,lowvol20)` 都能把三个分数拟合到很近，但前者是成交额×反转，后者是市值×低波动；这正是仅凭汇总分数无法识别原公式的直接证据。",
        "", "## 使用边界", "",
        "这些拟合是在搜索训练段的 184 个周期上得到的，公开榜单指标覆盖约 401/402 个历史周期。候选是否能在未参与拟合的后段保持相同分数，需要逐条做冻结后的完整窗口验证；已有结果显示，浅层树后段转负，因此不能把训练段分数对齐直接当作可交易复刻。",
        "", "完整逐目标前五名见 `search/score_fit_matches.csv`。",
        "", "## 榜单分数代理",
        "",
        "对公开池逐席位做了一阶替换：只把目标席位的 `s_i_a` 换成候选的本地 `S_i`，池的 B/C、席位数、新手系数和封顶参数沿用公开快照。由此得到代理 `NA`、`comb` 和月积分；这能检验候选是否会产生相似的榜单分数形状，但不能替代完整池级 C 回测，因为候选替换会同时改变组合收益、夏普、回撤和换手。",
        "",
        "逐席位结果见 `search/leaderboard_score_proxy.csv`。",
        "",
        "|候选|替换样本数|平均 Δcomb|中位数 Δcomb|平均 Δ月积分|中位数 Δ月积分|平均 Δ排名|最好 Δ排名|Δcomb 为正的样本|",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in board_summary.itertuples():
        lines.append(f"|{r.candidate}|{r.rows}|{r.mean_delta_comb:.4f}|{r.median_delta_comb:.4f}|{r.mean_delta_points:.1f}|{r.median_delta_points:.1f}|{r.mean_delta_rank:.1f}|{r.best_delta_rank:+d}|{r.positive_proxy_rows}|")
    (HERE / "score_fit_analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"evaluated_structures": len(ev), "target_rows": len(targets), "matches": len(result)}, ensure_ascii=False))

if __name__ == "__main__": main()
