import json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
TMP = os.environ["TEMP"]
det = json.load(open(os.path.join(TMP, "top20_factor_details.json"), encoding="utf-8"))
want = ["低换手反转|国羽长虹","量价|sx因子","joinlearn.com|dfkai","换手反转|新人报道",
        "稳健多因子Alpha|Lavine X","啦啦啦啦啦|forests","神人因子|神人队","Ayden Alpha|往复随安"]
for k in want:
    v = det[k]
    print("#### %s  cycle=%s n=%d" % (k, v.get("cycle"), len(v["factors"])))
    for x in v["factors"]:
        print("   %-40s ic=%+.4f icir=%+.3f win=%.3f s_i=%.5f cnt=%s n=%-4s %s..%s" % (
            x["factor_name"], x["ic_mean"], x["icir"], x["ic_win_rate"], x["s_i_a"],
            x["counted"], x["sample_count"], x["window_start"], x["window_end"]))
    print()
