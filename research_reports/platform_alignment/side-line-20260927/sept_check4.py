import json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
TMP = os.environ["TEMP"]
det = json.load(open(os.path.join(TMP, "top20_factor_details.json"), encoding="utf-8"))
board = json.load(open(os.path.join(TMP, "live_board_20260924.json"), encoding="utf-8"))
bp = {b["pool_name"] + "|" + b["display_name"]: b for b in board}

POOLS = {
 "低换手反转|国羽长虹": {"20日价格负偏离低换手反转": ("lt20", 0.0800,0.580,0.658),
                      "T3平滑均线负偏离反转": ("t3", 0.0655,0.402,0.613)},
 "量价|sx因子": {"c20-c02-rev-bias60": ("bias60",0.0633,0.365,0.605),
              "probe-rev-bias20": ("bias20",0.0463,0.283,0.575),
              "c20-c07-trend-ma20": ("bias20dup",0.0463,0.283,0.575),
              "c20-c03-rev-ret10": ("ret10",0.0409,0.257,0.568),
              "c20-c01-rev-bias10": ("bias10",0.0315,0.202,0.545),
              "probe-dist-high60": ("dist60",0.0200,0.110,0.488),
              "c20-c04-dist-high20": ("dist20",0.0077,0.045,0.435)},
 "joinlearn.com|dfkai": {"comp-full-Amihud非流动性-20d": ("amihud20",0.0513,0.333,0.613),
                        "comp-full-小市值": ("size",0.0435,0.227,0.588)},
 "换手反转|新人报道": {"F-J06_Alpha191_120_LW": ("a191_120LW",0.0971,0.505,0.681),
                  "F-J08_Alpha191_140_LW": ("a191_140LW",0.0683,0.424,0.622),
                  "F-I07_Alpha191_124_LW": ("a191_124LW",0.0080,0.066,0.429)},
 "稳健多因子Alpha|Lavine X": {"ex1-maxret20": ("maxret20",0.0749,0.490,0.642),
                          "ex1-pvcorr20": ("pvcorr20",0.0525,0.581,0.625),
                          "ex3-amt60": ("amt60",0.0664,0.434,0.629),
                          "ex2-illiq5": ("illiq5",0.0550,0.370,0.600),
                          "ex2-illiq20n": ("illiq20",0.0499,0.327,0.592),
                          "ex2-size": ("size",0.0409,0.215,0.583)},
 "啦啦啦啦啦|forests": {"volume-vol-10d": ("vv10",0.0794,0.780,0.723),
                    "ema26-ratio": ("ema26",0.0659,0.403,0.605),
                    "short-term-reversal-20d": ("ret20rev",0.0647,0.412,0.597),
                    "small-cap-baseline": ("smallcap",0.0557,0.289,0.639)},
 "神人因子|神人队": {"ex_intradayma40_low": ("idm40",0.0939,0.649,0.708),
                 "fid5y_stdvol20_5y_low": ("stdvol5y",0.0773,0.771,0.742),
                 "full_intradayma60_low": ("idm60",0.0871,0.566,0.733),
                 "ex_intradayma90_low": ("idm90",0.0849,0.565,0.700),
                 "ex_intradayma120_low": ("idm120",0.0804,0.543,0.658)},
 "Ayden Alpha|往复随安": {"MS3-a191_042-官方Alpha复刻": ("a191_042",0.0639,0.486,0.646)},
}

print("== A. 逐席位：平台 vs 本地 (s_i = ic*icir*win) ==")
for pk, m in POOLS.items():
    v = det[pk]; b = bp[pk]; mm = b["metrics"]
    fac = {x["factor_name"]: x for x in v["factors"]}
    print("-- %s  raw_a=%.5f na=%.4f score=%.1f is_newbie=%s age=%s" % (
        pk, mm["raw_a"], mm["na"], v["score"], mm["is_newbie"], mm["pool_age_months"]))
    dsum = 0.0
    for fname, (tag, ic, icir, win) in m.items():
        p = fac[fname]
        s_loc = ic * icir * win
        d = s_loc - p["s_i_a"]
        dsum += d
        print("   %-32s plat %.5f (ic%+.4f/icir%+.3f/win%.3f) | local %.5f | d%+.5f  [%s]" % (
            fname, p["s_i_a"], p["ic_mean"], p["icir"], p["ic_win_rate"], s_loc, d, tag))
    n = len(v["factors"])
    dra = dsum / n
    dna = dra / mm["anchor_a"]
    dsc = 0.2 * dna * 40000 * (mm["newbie_factor"] if mm["is_newbie"] else 1.0)
    ssum = sum(x["s_i_a"] for x in v["factors"])
    cov = sum(fac[f]["s_i_a"] for f in m) / ssum
    print("   -> 覆盖 %d/%d 席, 占池A分 %.1f%% | d_sum=%+.5f d_raw_a=%+.6f d_na=%+.5f d_score=%+.1f" % (
        len(m), n, 100*cov, dsum, dra, dna, dsc))
    print()

print("== B. 全池计分链复算(平台明细 -> 榜单) ==")
ok = 0
for b in board:
    mm = b["metrics"]; k = b["pool_name"] + "|" + b["display_name"]
    if k not in det: continue
    v = det[k]
    ra = sum(x["s_i_a"] for x in v["factors"] if x["counted"]) / max(1, sum(1 for x in v["factors"] if x["counted"]))
    na = min(ra / mm["anchor_a"], 0.7 if mm["pool_age_months"] == 0 else 1.0)
    nb = min(mm["raw_b"] / mm["anchor_b"], 1.0) if mm["denominator_b"] > 0 else 0.0
    nc = min(max(mm["raw_c"], 0.0) / mm["anchor_c"], 1.0)
    comb = 0.2*na + 0.35*nb + 0.45*nc
    sc = min(comb*40000*(mm["newbie_factor"] if mm["is_newbie"] else 1.0), 40000)
    good = abs(ra-mm["raw_a"])<1e-9 and abs(na-mm["na"])<1e-9 and abs(nb-mm["nb"])<1e-9 and abs(nc-mm["nc"])<1e-9 and abs(comb-mm["comb"])<1e-9 and abs(sc-b["score"])<1e-6
    ok += good
    if not good:
        print("  MISMATCH", k, ra, mm["raw_a"], na, mm["na"], nb, mm["nb"], nc, mm["nc"], sc, b["score"])
print("  20 池逐项复算与榜单一致: %d/20" % ok)
