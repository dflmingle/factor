#!/usr/bin/env python3
import json, yaml, requests, time
from pathlib import Path
BASE='https://www.pandaaiquant.com/pandaApi'
PID='0a4f3ddbc4bb8b74720587a3'
OUT=Path(__file__).with_name('public_holdings_20261013.json')
cfg=yaml.safe_load(open('/home/minkefu/.pandaai/config.yaml'))
base=cfg['gateway_url'].rstrip('/')
h={'Authorization':cfg['token'],'uid':str(cfg['uid']),'Accept':'application/json'}
dates=['20260908','20260909','20260910','20260911','20260914','20260915','20260916','20260917','20260918','20260921','20260922','20260923','20260924','20260928','20260929','20260930','20261008','20261009']
out={}
for date in dates:
    first=requests.get(base+f'/arenaRanking/pools/{PID}/holdings',params={'tradeDate':date,'page':1,'pageSize':100},headers=h,timeout=30).json()['data']
    rows=list(first.get('rows') or [])
    total=int(first.get('selected_count') or len(rows))
    pages=(total+99)//100
    for page in range(2,pages+1):
        d=requests.get(base+f'/arenaRanking/pools/{PID}/holdings',params={'tradeDate':date,'page':page,'pageSize':100},headers=h,timeout=30).json()['data']
        rows.extend(d.get('rows') or [])
        time.sleep(.05)
    first['rows']=rows
    out[date]=first
    print(date,first.get('data_status'),len(rows),first.get('signal_trade_date'),first.get('active_factor_count'),first.get('rebalance_cycle_days'))
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=1))
print('saved',OUT)
