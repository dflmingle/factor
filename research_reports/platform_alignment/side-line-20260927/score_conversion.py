import sys
sys.stdout.reconfigure(encoding="utf-8")
RA = 0.025893           # our pool raw_a (platform measured)
SIZE = 0.009136         # weakest seat (to swap out)
A_RATE = 110000.0       # points per 1.0 raw_a (A term, newbie 1.1 included)
B_RATE = 256667.0       # same, if NB mirrors A structure (unverified)
cands = [
 ("010_LW (新人报道)", 0.09804),
 ("alpha191-042改造 (forests)", 0.07208),
 ("G17-zscore3 (LavineX)", 0.07074),
 ("G16/E13/E5/P2 家族 (LavineX)", 0.0660),
 ("F-J06_120_LW (新人报道)", 0.06451),
 ("F191-010 (LavineX)", 0.04759),
 ("volume-vol-10d (forests)", 0.04507),
 ("intradayma40_low (神人队)", 0.04442),
 ("F-J08_140_LW (新人报道)", 0.04035),
 ("intradayma60_low (神人队)", 0.03588),
 ("stdvol20/5y (神人队)", 0.03421),
 ("intradayma90_low (神人队)", 0.03113),
 ("MS3-042 (往复随安)", 0.02853),
 ("intradayma120_low (神人队)", 0.02765),
 ("20日负偏离x低换手 (国羽)", 0.02541),
 ("maxret20 (LavineX)", 0.02282),
 ("pvcorr20 (LavineX)", 0.01983),
 ("bias60 (sx)", 0.01433),
]
print("== 情形1: 换掉 SIZE-ONLY (N=5, raw_a 基准 %.6f) ==" % RA)
print("%-32s %8s %10s %12s %12s" % ("候选(平台5y s_i)", "s_i", "d_raw_a", "d分(A)", "d分(A+B)"))
for name, s in cands:
    d = (s - SIZE) / 5.0
    print("%-32s %8.5f %+10.6f %+12.0f %+12.0f" % (name, s, d, d*A_RATE, d*(A_RATE+B_RATE)))
print()
print("== 情形2: 加第6席 (N=6) ==")
print("%-32s %8s %10s %12s %12s" % ("候选", "s_i", "d_raw_a", "d分(A)", "d分(A+B)"))
for name, s in cands:
    d = (s - RA) / 6.0
    print("%-32s %8.5f %+10.6f %+12.0f %+12.0f" % (name, s, d, d*A_RATE, d*(A_RATE+B_RATE)))
print()
print("== 分数结构 ==")
print("我们:  A %.0f + B 0 + C 19800 = 22649" % (0.3237*A_RATE/0.2/4.0*0.2*4.0 if False else 0.3237*8800))
print("榜首:  A %.0f + B %.0f + C 19800 = 35624" % (0.0481947*8800, 15400))
print("A 上限(cap 0.70): %.0f 分/月, 距现在 +%.0f" % (0.70*8800, (0.70-0.3237)*8800))
# hypothetical: our 5 seats + 4 top opponent seats
front = [0.09804, 0.07208, 0.07074, 0.06451]
ra2 = (5*RA + sum(front)) / 9
print("模拟(我们5席 + 这4条顶席, 9席): raw_a %.5f -> na %.4f -> A %.0f 分/月 (+%.0f)" % (ra2, min(ra2/0.08,0.7), min(ra2/0.08,0.7)*8800, min(ra2/0.08,0.7)*8800 - 0.3237*8800))
