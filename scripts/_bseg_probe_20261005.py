# -*- coding: utf-8 -*-
"""B 段（NB / raw_b / denominator_b）零算力反解探针（2026-10-05）。

数据：board-details-20261004-period202609/factors_all.csv（305 池 × 3502 席逐席）
      + board-snapshot-20260930/board_live.json（池级 na/nb/nc/raw_a/raw_b/denominator_b）
      + board-20260928/board_live.json（09-24 cutoff，286 池，两周自然实验对照）
"""
import csv, json, sys
from collections import Counter, defaultdict
import statistics as st

BASE = "research_reports/platform_alignment/"
FAC = BASE + "board-details-20261004-period202609/factors_all.csv"
SNAP = BASE + "board-snapshot-20260930/board_live.json"
SNAP_OLD = BASE + "board-20260928/board_live.json"


def load_snap(path):
    d = json.load(open(path, encoding="utf-8"))
    return {r["participant_id"]: r for r in d["rows"]}


def load_factors():
    out = defaultdict(list)
    with open(FAC, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            out[r["participant_id"]].append(r)
    return out


def f(x, d=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def main():
    snap, old = load_snap(SNAP), load_snap(SNAP_OLD)
    fac = load_factors()
    print("pools with details: %d ; seats total: %d" % (len(fac), sum(len(v) for v in fac.values())))

    # --- 1. raw_a 聚合口径验证：raw_a == mean(s_i_a over counted) ?
    rows = []
    for pid, rs in fac.items():
        m = snap.get(pid)
        if not m:
            continue
        mm = m["metrics"]
        counted = [f(r["s_i_a"]) for r in rs if r["counted"] == "True" and f(r["s_i_a"]) is not None]
        if not counted:
            continue
        rows.append(dict(pid=pid, nseat=len(rs), ncount=len(counted),
                         mean_sia=sum(counted) / len(counted), max_sia=max(counted),
                         raw_a=f(mm["raw_a"]), den_a=mm["denominator_a"], den_b=mm["denominator_b"],
                         raw_b=f(mm["raw_b"]), nb=f(mm["nb"]), na=f(mm["na"]), nc=f(mm["nc"]),
                         age=m.get("pool_age_months"), seats=m.get("active_factor_count"),
                         cycle=m.get("rebalance_cycle_days"), turn=f(mm["turn"]),
                         rex=f(mm["annual_rex"]), sr=f(mm["annual_sr"]), dd=f(mm["max_dd"]),
                         score=m.get("score"), rank=m.get("rank")))
    err = [abs(r["mean_sia"] - r["raw_a"]) for r in rows]
    err.sort()
    print("\n[1] raw_a vs mean(s_i_a over counted): n=%d  median|err|=%.3e p95=%.3e max=%.3e"
          % (len(err), err[len(err) // 2], err[int(len(err) * .95)], err[-1]))
    print("    den_a == counted seats? %s" % (all(r["den_a"] == r["ncount"] for r in rows)))

    # --- 2. denominator_b 是什么
    ge = [r for r in rows if r["den_b"] and r["den_b"] > 0]
    print("\n[2] denominator_b: >0 的池 %d/%d (%.1f%%)" % (len(ge), len(rows), 100 * len(ge) / len(rows)))
    c = Counter((r["den_b"], r["nseat"]) for r in rows if r["den_b"])
    print("    den_b<=nseat 全部成立? %s" % all(r["den_b"] <= r["nseat"] for r in ge))
    db = Counter(r["den_b"] for r in rows)
    print("    den_b 分布:", dict(sorted(db.items(), key=lambda kv: (kv[0] is None, kv[0]))))

    # --- 3. nb>0 与 席位数 / 池龄 的关系（行动问题：加席是不是 B 段刚需？）
    def bucket(rs, key, edges, label):
        print("\n[3] %s -> nb>0 占比" % label)
        for lo, hi in zip(edges[:-1], edges[1:]):
            sel = [r for r in rs if lo <= (r[key] or 0) < hi]
            if sel:
                pos = sum(1 for r in sel if r["nb"] > 0)
                print("    %-14s n=%3d  nb>0=%3d (%.0f%%)  nb中位=%.2f  raw_b中位=%.3f" % (
                    "[%d,%d)" % (lo, hi), len(sel), pos, 100 * pos / len(sel),
                    st.median([r["nb"] for r in sel]), st.median([r["raw_b"] or 0 for r in sel])))
    bucket(rows, "nseat", [0, 5, 6, 8, 10, 13, 100], "活跃席位数")
    bucket(rows, "age", [0, 1, 2, 3, 6, 100], "池龄(月)")

    # --- 4. 与榜首/NB=1 池的画像对比
    ones = [r for r in rows if r["nb"] >= 0.999]
    zeros = [r for r in rows if r["nb"] <= 0.0001]
    print("\n[nb=1] n=%d ; [nb=0] n=%d" % (len(ones), len(zeros)))

    def prof(rs, name):
        if not rs:
            return
        med = lambda k: st.median([r[k] for r in rs if r[k] is not None])
        print("    %-6s 席位数中位=%.0f 池龄中位=%.0f den_b中位=%.0f raw_a中位=%.4f na中位=%.3f nc中位=%.2f turn中位=%.2f"
              % (name, med("nseat"), med("age") or 0, med("den_b") or 0, med("raw_a"), med("na"), med("nc"), med("turn")))
    prof(ones, "nb=1")
    prof(zeros, "nb=0")
    prof([r for r in rows if r["nb"] > 0], "nb>0")

    # --- 5. raw_b 的池内可解释性：与逐席指标的何种聚合最相关
    print("\n[5] raw_b 与逐席聚合的相关（仅 nb<1 的未封顶池，n=%d）" % len([r for r in rows if r["nb"] < 1]))
    print("    （待补：per-seat 窗口/样本数用于判定 B 是否=样本外口径）")

    # --- 6. 09-24 -> 09-30 自然实验
    both = [pid for pid in snap if pid in old]
    print("\n[6] 两周自然实验：两期都在榜的池 %d" % len(both))
    jump = [pid for pid in both if (snap[pid]["metrics"]["denominator_b"] or 0) > (old[pid]["metrics"]["denominator_b"] or 0)]
    drop = [pid for pid in both if (snap[pid]["metrics"]["denominator_b"] or 0) < (old[pid]["metrics"]["denominator_b"] or 0)]
    print("    den_b 上升 %d 池 / 下降 %d 池" % (len(jump), len(drop)))
    if jump:
        js = [dict(age=snap[p].get("pool_age_months"), nseat=snap[p]["active_factor_count"],
                   db0=old[p]["metrics"]["denominator_b"], db1=snap[p]["metrics"]["denominator_b"],
                   nb0=old[p]["metrics"]["nb"], nb1=snap[p]["metrics"]["nb"]) for p in jump]
        print("    上升池：池龄中位=%.0f 席位中位=%.0f ; den_b %s -> %s" % (
            st.median([x["age"] or 0 for x in js]), st.median([x["nseat"] for x in js]),
            Counter(x["db0"] for x in js), Counter(x["db1"] for x in js)))
        print("    其中 nb 也转正 %d 池" % sum(1 for x in js if x["nb1"] > x["nb0"]))


if __name__ == "__main__":
    main()