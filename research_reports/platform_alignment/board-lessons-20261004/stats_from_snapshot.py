# -*- coding: utf-8 -*-
"""board-lessons-20261004 报告数字复核（只读快照，零平台算力）。

数据源：
  - ../board-snapshot-20260930/board_live.json      （305 池总榜快照，data cutoff 2026-09-30）
  - ../board-snapshot-20260930/me_boards.json       （我方分榜）
  - ../board-details-20261004/all_pool_details.json （305 池 header；席位明细接口已关闭）

输出：stdout + 同目录 stats_output.txt
运行：PYTHONUTF8=1 python stats_from_snapshot.py
"""
from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
LIVE = BASE / "board-snapshot-20260930" / "board_live.json"
ME = BASE / "board-snapshot-20260930" / "me_boards.json"
DETAILS = BASE / "board-details-20261004" / "all_pool_details.json"

SCALE = 40_000.0
OUT = []


def p(line: str = "") -> None:
    OUT.append(line)
    print(line)


def static_rank(rows, score: float) -> int:
    return 1 + sum(1 for r in rows if r["score"] > score)


def main() -> None:
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    me = json.loads(ME.read_text(encoding="utf-8"))
    details = json.loads(DETAILS.read_text(encoding="utf-8"))
    meta, rows = live["meta"], live["rows"]
    hdr = {pid: e["header"] for pid, e in details.items() if isinstance(e, dict)}
    cycle = {pid: h.get("rebalance_cycle_days") for pid, h in hdr.items()}
    ours = next(r for r in rows if r["display_name"] == "ddd")
    om = ours["metrics"]
    nf = om["newbie_factor"] or 1.0

    p("== meta ==")
    p(json.dumps(meta, ensure_ascii=False))

    p()
    p("== 我方池（display_name=ddd, pool=mingle）==")
    p(f"rank={ours['rank']} score={ours['score']:.1f} rank_delta={ours['rank_delta']} style={ours.get('style_tag')}")
    p(f"na={om['na']:.4f} nb={om['nb']:.3f} nc={om['nc']:.2f} comb={om['comb']:.4f} "
      f"raw_a={om['raw_a']:.5f} raw_c={om['raw_c']:.2f} fac={om['active_factor_count']} "
      f"age={om['pool_age_months']} newbie={om['newbie_factor']}")

    p()
    p("== top 30（含我方 rank 26）==")
    for r in sorted(rows, key=lambda r: r["rank"])[:30]:
        m = r["metrics"]
        c = cycle.get(r["participant_id"], "?")
        p(f"{r['rank']:>3} {r['display_name'][:16]:<18} score={r['score']:>9.1f} na={m['na']:.4f} "
          f"nb={m['nb']:.3f} nc={m['nc']:.2f} fac={m['active_factor_count']:>2} cyc={c} age={m['pool_age_months']}")

    top = sorted(rows, key=lambda r: r["rank"])[0]
    tm = top["metrics"]
    p()
    p("== 差距分解（vs 榜首）==")
    gap_nb = 0.35 * (tm["nb"] - om["nb"]) * SCALE * nf
    gap_na = 0.20 * (tm["na"] - om["na"]) * SCALE * nf
    gap_nc = 0.45 * (tm["nc"] - om["nc"]) * SCALE * nf
    p(f"榜首 {top['display_name']} score={top['score']:.1f} na={tm['na']:.4f} nb={tm['nb']} nc={tm['nc']:.2f} "
      f"raw_a={tm['raw_a']:.5f} fac={tm['active_factor_count']} age={tm['pool_age_months']}")
    p(f"总差距={top['score']-ours['score']:.1f} 其中 NB 段={gap_nb:.1f}（{gap_nb/(top['score']-ours['score'])*100:.1f}%）"
      f" NA 段={gap_na:.1f} NC 段={gap_nc:.1f}")
    p(f"raw_a 比：我方/榜首 = {om['raw_a']/tm['raw_a']*100:.1f}%   fac 比 {om['active_factor_count']}/{tm['active_factor_count']}")

    p()
    p("== 我方 what-if 情景（静态对比当前榜单，假设对手分数不变；newbie={:.1f}）==".format(nf))
    scenarios = [
        ("现状", om["na"], om["nb"], om["nc"]),
        ("NB=0.3", om["na"], 0.3, om["nc"]),
        ("NB=0.5", om["na"], 0.5, om["nc"]),
        ("NB=0.836（追平 09-22 旧榜首线）", om["na"], 0.836, om["nc"]),
        ("NB=1.0", om["na"], 1.0, om["nc"]),
        ("NA=0.50", 0.50, om["nb"], om["nc"]),
        ("NA=0.70（新池封顶）", 0.70, om["nb"], om["nc"]),
        ("NB=1.0 + NA=0.70", 0.70, 1.0, om["nc"]),
    ]
    for name, na, nb, nc in scenarios:
        comb = 0.20 * na + 0.35 * nb + 0.45 * nc
        raw = comb * SCALE * nf
        rank = static_rank(rows, raw)
        p(f"{name:<26} comb={comb:.4f} 积分={raw:>8.1f}"
          f"{'（封顶40k）' if raw > SCALE else ''} 静态rank={rank}")

    p()
    p("== NB 分层（305 池）==")
    b0 = [r for r in rows if r["metrics"]["nb"] == 0]
    b1 = [r for r in rows if 0 < r["metrics"]["nb"] < 0.5]
    b2 = [r for r in rows if 0.5 <= r["metrics"]["nb"] < 1]
    b3 = [r for r in rows if r["metrics"]["nb"] >= 1]
    for label, group in [("NB=0", b0), ("0<NB<0.5", b1), ("0.5<=NB<1", b2), ("NB=1", b3)]:
        ranks = sorted(r["rank"] for r in group)
        p(f"{label:<10} n={len(group):>3} rank范围 [{ranks[0]},{ranks[-1]}]")
    p("NB=1 明细：")
    for r in sorted(b3, key=lambda r: r["rank"]):
        m = r["metrics"]
        p(f"  rank {r['rank']:>3} {r['display_name'][:16]:<18} score={r['score']:>9.1f} na={m['na']:.4f} "
          f"nc={m['nc']:.2f} fac={m['active_factor_count']:>2} cyc={cycle.get(r['participant_id'], '?')}")
    p("0.5<=NB<1 明细：")
    for r in sorted(b2, key=lambda r: r["rank"]):
        m = r["metrics"]
        p(f"  rank {r['rank']:>3} {r['display_name'][:16]:<18} score={r['score']:>9.1f} na={m['na']:.4f} "
          f"nb={m['nb']:.3f} fac={m['active_factor_count']:>2}")

    p()
    p("== 结构分布 ==")
    top30 = sorted(rows, key=lambda r: r["rank"])[:30]
    for label, group in [("全榜", rows), ("top30", top30)]:
        cyc = Counter(cycle.get(r["participant_id"], "?") for r in group)
        fac = Counter(r["metrics"]["active_factor_count"] for r in group)
        p(f"{label} cycle 分布: {dict(sorted(cyc.items(), key=lambda kv: str(kv[0])))}")
        p(f"{label} 因子数分布: {dict(sorted(fac.items()))}  众数={fac.most_common(1)[0]}")
    na_all = sorted(r["metrics"]["na"] for r in rows)
    p(f"NA 全榜：median={statistics.median(na_all):.4f} p90={na_all[int(0.9*len(na_all))-1]:.4f} max={na_all[-1]:.4f}")
    n_nc1 = sum(1 for r in rows if r["metrics"]["nc"] >= 1)
    p(f"NC=1 的池数：{n_nc1}；NB>0 池数：{len(rows)-len(b0)}；我方 raw_a 排名（降序）= "
      f"{1 + sum(1 for r in rows if r['metrics']['raw_a'] > om['raw_a'])}/{len(rows)}；"
      f"na 排名（降序）={1 + sum(1 for r in rows if r['metrics']['na'] > om['na'])}/{len(rows)}")

    p()
    p("== 苦日子（同族谱系对手）==")
    for r in rows:
        if "苦日子" in (r.get("pool_name") or "") or "苦日子" in (r["display_name"] or ""):
            m = r["metrics"]
            p(f"rank={r['rank']} name={r['display_name']} pool={r['pool_name']} score={r['score']:.1f} "
              f"na={m['na']:.4f} nb={m['nb']} nc={m['nc']:.2f} raw_a={m['raw_a']:.5f} "
              f"fac={m['active_factor_count']} age={m['pool_age_months']} cyc={cycle.get(r['participant_id'], '?')}")

    p()
    p("== me_boards 分榜 ==")
    for b in me["data"]["boards"]:
        p(f"{b['board_title']}（{b['cadence']}/{b['period']}）rank={b['rank']}/{b['total']} score={b['score']} "
          f"prize_rank={b.get('prize_rank')} snapshot={b.get('snapshot_type')}")

    p()
    p("== 席位明细接口状态 ==")
    n_nonempty = sum(1 for e in details.values()
                     if isinstance(e, dict) and (e.get("factor_pool_details") or e.get("pool_radar")))
    p(f"board-details-20261004：305 池中席位明细非空 = {n_nonempty}"
      f"（该次抓取漏传 ?period=2026-09 → 按当前周期 2026-10 返回空；补抓见 board-details-20261004-period202609/）")

    (HERE / "stats_output.txt").write_text("\n".join(OUT) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
