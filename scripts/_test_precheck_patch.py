import sys, ast
sys.path.insert(0, r"D:\factor\scripts")
import platform_precheck as pp
f = "(POWER(10,19)*(((((RATIO_BM_LYR/LOG(VMA250))/CAL_20D_AMT_MA)/QTYR_5_20)/(ASI(OPEN,CLOSE,HIGH,LOW,26,10)/MA(ASI(OPEN,CLOSE,HIGH,LOW,26,10),20)))/BS_TOTAL_ASSETS))"
t = ast.parse(f, mode="eval")
print("corr_in_denominator:", pp.corr_in_denominator(t))
f2 = "(POWER(10,26)*(((((CAL_5D_MIN_LOW_IDX/MA(CAL_5D_MIN_LOW_IDX,10))/BBIBOLL_DOWN)/CAL_20D_AMT_MA)/BS_TOTAL_ASSETS)/BS_TOTAL_ASSETS))"
print("K031:", pp.corr_in_denominator(ast.parse(f2, mode="eval")))
print("has _signed_in:", hasattr(pp, "_signed_in"), "SIGNED set size:", len(getattr(pp, "SIGNED_DIVISOR_FIELDS", [])))