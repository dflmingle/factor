import io, sys, re, os, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
base = r"D:\factor\vendor\skill-pandaai-factor-online\references"

ops = set()
for fn in glob.glob(os.path.join(base, "*.md")):
    text = open(fn, encoding="utf-8").read()
    for m in re.finditer(r"\|\s*`?([A-Z][A-Z0-9_]{1,24})\s*\(", text):
        ops.add(m.group(1))
print("platform operators:", len(ops))
print(sorted(ops))
print()

fields = set()
for fn in glob.glob(os.path.join(base, "fields*.md")):
    text = open(fn, encoding="utf-8").read()
    for line in text.splitlines():
        m = re.match(r"^\|\s*`([^`]+)`", line)
        if m:
            fields.add(m.group(1).strip())
print("platform fields:", len(fields))
need = ["a_share_market_val","is_operate_profit","davol5","cal_30d_ret_vol_corr","cal_20d_amt_ma",
        "amount","bs_total_assets","ratio_bm_lyr","cal_30d_price_vol_corr"]
for n in need:
    print(f"  {n:26s}", "OK" if n in fields else "MISSING")
print()
print("closest matches:")
for n in need:
    if n in fields: continue
    base_n = n.lower()
    cands = [f for f in fields if base_n[:6] in f.lower() or f.lower().startswith(base_n[:4])]
    print("  ", n, "->", sorted(cands)[:12])