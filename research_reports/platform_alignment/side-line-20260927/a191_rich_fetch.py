import os, sys, time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(os.environ["TEMP"]) / "side_conv" / "a191_rich" / "raw_daily"
OUT.mkdir(parents=True, exist_ok=True)

tok = os.environ.get("TUSHARE_TOKEN", "").strip()
if not tok:
    tok = Path(r"C:\Users\58302\tk.csv").read_text(encoding="utf-8", errors="replace").split()[-1]

import tushare as ts
CAL = Path(r"D:\factor\quantlab\.quantlab\cache\research\cn_equity\trade_calendar")
dates = set()
for year in range(2021, 2027):
    f = CAL / ("%d.parquet" % year)
    if not f.exists():
        continue
    df = pd.read_parquet(f)
    df = df[(df["exchange"] == "SSE") & (df["is_open"] == 1)]
    dates.update(df["trade_date"].astype(str).tolist())
dates = sorted(d for d in dates if d >= "20210104")
pending = [d for d in dates if not (OUT / ("raw_%s.parquet" % d)).exists()]
print("calendar=%d pending=%d %s..%s" % (len(dates), len(pending), dates[0], dates[-1]), flush=True)

FIELDS = "ts_code,trade_date,open,high,low,close,pre_close,vol,amount"
lock = threading.Lock()
done = [0]
fails = []
t0 = time.time()

def fetch(day):
    pro = ts.pro_api(tok)
    last = None
    for attempt in range(5):
        try:
            frame = pro.daily(trade_date=day, fields=FIELDS)
            if frame is not None and not frame.empty:
                return frame
            last = "empty"
        except Exception as exc:
            last = repr(exc)[:120]
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("%s: %s" % (day, last))

def work(day):
    try:
        frame = fetch(day)
        frame.to_parquet(OUT / ("raw_%s.parquet" % day), index=False)
        with lock:
            done[0] += 1
            if done[0] % 100 == 0:
                el = time.time() - t0
                print("fetched %d/%d  %.1f/min  elapsed %.1fmin" % (done[0], len(pending), done[0]/el*60, el/60), flush=True)
    except Exception as exc:
        with lock:
            fails.append(str(exc)[:150])
            print("FAIL %s" % str(exc)[:150], flush=True)
    time.sleep(0.05)

if pending:
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(work, pending))
el = time.time() - t0
print("DONE fetched=%d fails=%d elapsed=%.1fmin" % (done[0], len(fails), el/60), flush=True)
for f in fails[:20]:
    print("FAILED:", f, flush=True)
