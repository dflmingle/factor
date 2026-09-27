import pickle, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = pickle.load(open(r"D:/factor/research_reports/platform_alignment/ab-batch-20260925/seat_panels_rebuilt.pkl","rb"))
print("keys:", list(p.keys()))
print("scores type:", type(p["scores"]), len(p["scores"]))
for k,v in p["scores"].items():
    print(" ", k, v.shape, v.index[0], v.index[-1], "nan_share=%.4f"%float(v.isna().to_numpy().mean()))
print("signal_frame", p["signal_frame"].shape, p["signal_frame"].columns.tolist())
print("returns", p["returns"].shape, p["returns"].columns.tolist())
print("dates", len(p["dates"]), p["dates"][0], p["dates"][-1])
print("pool_summary", p["pool_summary"])