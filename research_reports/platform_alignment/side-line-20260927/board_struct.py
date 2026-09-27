import json, io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
T = os.environ["TEMP"]
b = json.load(open(os.path.join(T, "live_board_20260924.json"), encoding="utf-8"))
print("live_board type", type(b))
if isinstance(b, list):
    print("n", len(b), "| item keys:", list(b[0].keys()))
    b0 = b[0]
elif isinstance(b, dict):
    print("keys", list(b.keys())[:20])
    b0 = None
if b0 is not None:
    for k, v in b0.items():
        print("  %-24s %s" % (k, str(v)[:120]))
d = json.load(open(os.path.join(T, "top20_factor_details.json"), encoding="utf-8"))
print("\ntop20 type", type(d))
if isinstance(d, dict):
    ks = list(d.keys())
    print("n keys", len(ks), "| sample:", ks[:4])
    v = d[ks[3]] if len(ks) > 3 else d[ks[0]]
    print("value keys:", list(v.keys()) if isinstance(v, dict) else type(v))
    if isinstance(v, dict) and "factors" in v:
        print("factor[0] keys:", list(v["factors"][0].keys()))
