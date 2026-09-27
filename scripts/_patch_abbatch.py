import json
import pathlib

p = pathlib.Path(r"D:\factor\scripts\ab_batch_20260925.py")
t = p.read_text(encoding="utf-8")

t = t.replace(
    "import argparse, pickle, sys\n",
    "import argparse, json, pickle, sys\n",
    1,
)

helper = '''

def load_seats() -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """席位面板来源：优先交接单里的正式大缓存，缺失时回退到本机重建版。"""
    if SIGNALS.exists() and SEATS.exists():
        sf, _raw, _returns, _dates = pickle.load(SIGNALS.open("rb"))
        return sf, pickle.load(SEATS.open("rb"))["scores"][POOL], "canonical_pkl"
    payload = pickle.load(REBUILT.open("rb"))
    marker = "rebuilt:" + str(payload.get("provenance", {}).get("source_rule_version"))
    return payload["signal_frame"], payload["scores"][POOL], marker
'''

anchor = "\n\ndef zscore(frame: pd.DataFrame) -> pd.DataFrame:"
assert anchor in t
t = t.replace(anchor, helper + "\n\ndef zscore(frame: pd.DataFrame) -> pd.DataFrame:", 1)

t = t.replace(
    'SEATS = ROOT / "research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl"\n',
    'SEATS = ROOT / "research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl"\n'
    'REBUILT = ROOT / "research_reports/platform_alignment/ab-batch-20260925/seat_panels_rebuilt.pkl"\n',
    1,
)

old = '    sf, _raw, _returns, _dates = pickle.load(SIGNALS.open("rb"))\n    seat_scores = pickle.load(SEATS.open("rb"))["scores"][POOL]\n'
assert old in t
t = t.replace(old, '    sf, seat_scores, seat_source = load_seats()\n'
                   '    print(f"seat source: {seat_source}", flush=True)\n', 1)

old_write = '    pd.DataFrame([base]).to_csv(OUT / "base_pool.csv", index=False)\n'
assert old_write in t
t = t.replace(
    old_write,
    old_write
    + '    (OUT / "run_provenance.json").write_text(\n'
      '        json.dumps(dict(seat_source=seat_source, seat_panels=list(POOL), cycle=CYCLE,\n'
      '                        cost=COST, buckets=BUCKETS, points=POINTS, weakest=WEAKEST,\n'
      '                        rules="ab-batch-20260925"), ensure_ascii=False, indent=1),\n'
      '        encoding="utf-8",\n'
      '    )\n',
    1,
)

p.write_text(t, encoding="utf-8")
import ast

ast.parse(t)
print("patched ok")