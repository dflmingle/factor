import json, os, sys, math
sys.stdout.reconfigure(encoding="utf-8")
TMP = os.environ["TEMP"]
det = json.load(open(os.path.join(TMP, "top20_factor_details.json"), encoding="utf-8"))
board = json.load(open(os.path.join(TMP, "live_board_20260924.json"), encoding="utf-8"))
bkey = {}
for b in board:
    bkey[b["pool_name"] + "|" + b["display_name"]] = b
fallback = {}
for b in board:
    fallback.setdefault(b["pool_name"], b)

hdr = "%-3s %-28s %6s %5s %4s %8s %10s %10s %8s %6s %6s %8s %8s %10s %10s" % (
    "rk","pool","score","age","nf","cyc","raw_a","mean_s","d_raw","na","na_ck","nb_ck","nc_ck","comb_ck","score_ck")
print(hdr)
rows = []
for k, v in det.items():
    b = bkey.get(k) or fallback.get(k.split("|")[0])
    if b is None:
        print("NO BOARD for", k); continue
    m = b.get("metrics", {})
    f = v["factors"]
    cnt = [x for x in f if x.get("counted")]
    ssum = sum(x["s_i_a"] for x in cnt)
    mean_s = ssum / len(cnt) if cnt else float("nan")
    raw_a = m.get("raw_a", float("nan"))
    cap = 0.7 if m.get("pool_age_months", 0) == 0 else 1.0
    na_ck = min(raw_a / m.get("anchor_a", 0.08), cap)
    nb_ck = min(m.get("raw_b", 0.0) / m.get("anchor_b", 0.06), 1.0) if m.get("denominator_b", 0) > 0 else 0.0
    raw_c = m.get("raw_c", float("nan"))
    nc_ck = min(max(raw_c, 0.0) / m.get("anchor_c", 0.6), 1.0)
    comb_ck = 0.2 * na_ck + 0.35 * nb_ck + 0.45 * nc_ck
    sc_ck = min(comb_ck * 40000 * (1.1 if m.get("is_newbie") else 1.0), 40000)
    line = "%-3s %-28s %6.0f %5s %4d %8s %10.6f %10.6f %+8.6f %6.4f %6.4f %6s %6s %8.4f %10.1f" % (
        b["rank"], (b["pool_name"] + "|" + b["display_name"])[:28], v["score"], m.get("pool_age_months"),
        len(f), v.get("cycle"), raw_a, mean_s, raw_a - mean_s, m.get("na"), na_ck,
        "%.4f" % m.get("nb"), "%.4f" % m.get("nc"), m.get("comb", float("nan")), v["score"])
    print(line)
    rows.append((k, b, v, cnt, ssum, mean_s))

print()
print("== 逐项二次校验 (显示值 vs 公式重算) ==")
for k, b, v, cnt, ssum, mean_s in rows:
    m = b["metrics"]
    ys = []
    ys.append(("na", m["na"], min(m["raw_a"] / m["anchor_a"], 0.7 if m["pool_age_months"] == 0 else 1.0)))
    ys.append(("nb", m["nb"], min(m["raw_b"] / m["anchor_b"], 1.0) if m["denominator_b"] > 0 else 0.0))
    ys.append(("nc", m["nc"], min(max(m["raw_c"], 0.0) / m["anchor_c"], 1.0)))
    comb = 0.2 * m["na"] + 0.35 * m["nb"] + 0.45 * m["nc"]
    ys.append(("comb", m["comb"], comb))
    sc = min(comb * 40000 * (1.1 if m["is_newbie"] else 1.0), 40000)
    ys.append(("score", m["monthly_points"], sc))
    bad = [(n, a, c) for n, a, c in ys if abs(a - c) > max(1e-6, abs(a) * 1e-6)]
    tag = "OK" if not bad else "; ".join("%s %.6f!=%.6f" % t for t in bad)
    print("%-30s %s" % (k[:30], tag))

# per-pool factor list dump
with open(os.path.join(TMP, "side_conv", "pool_factors_dump.txt"), "w", encoding="utf-8") as fh:
    for k, v in det.items():
        fh.write("## %s cycle=%s n=%d\n" % (k, v.get("cycle"), len(v["factors"])))
        for x in v["factors"]:
            fh.write("   %-38s ic=%+.4f icir=%+.3f win=%.3f s_i=%.5f cnt=%s n=%s %s..%s\n" % (
                x["factor_name"], x["ic_mean"], x["icir"], x["ic_win_rate"], x["s_i_a"],
                x["counted"], x["sample_count"], x["window_start"], x["window_end"]))
print("\ndump -> pool_factors_dump.txt")
