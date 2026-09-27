import json, io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
T = os.environ["TEMP"]
board = json.load(open(os.path.join(T, "live_board_20260924.json"), encoding="utf-8"))
det = json.load(open(os.path.join(T, "top20_factor_details.json"), encoding="utf-8"))

print("=== live board (抓取 2026-09-27 00:47) ===")
for b in board:
    if b["display_name"] in ("forests", "神人队", "燕雀", "虎墨666", "国羽长虹"):
        m = b["metrics"]
        print("%-8s rank=%-4s score=%10.1f delta=%+5s | na=%.4f nb=%.3f nc=%.4f raw_a=%.5f Rex=%.2f%% SR=%.3f turn=%.3f DD=%.2f%% 月Rex=%.2f%%" % (
            b["display_name"], b["rank"], b["score"], b.get("rank_delta"), m["na"], m["nb"], m["nc"], m["raw_a"],
            m["annual_rex"]*100, m["annual_sr"], m["turn"], m["max_dd"]*100, m["monthly_rex"]*100))

print("\n=== 席位明细（top20_factor_details, 抓取 09-27 00:53） ===")
for key in ["啦啦啦啦啦|forests", "神人因子|神人队"]:
    v = det[key]
    print("-- %s  pool raw_a?= n=%s nb=%s nc=%s cycle=%s" % (key, v.get("n_factor"), v.get("nb"), v.get("nc"), v.get("cycle")))
    for f in v["factors"]:
        print("   %-26s dir=%-8s ic=%.4f icir=%.4f win=%.4f s_i=%s counted=%s insufficient=%s win=%s..%s" % (
            f["factor_name"][:26], f["direction"], f["ic_mean"], f["icir"], f["ic_win_rate"],
            f.get("s_i_a"), f.get("counted"), f.get("insufficient"), f.get("window_start"), f.get("window_end")))
