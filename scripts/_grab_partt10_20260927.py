import io, json, subprocess, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"D:\factor\vendor\skill-pandaai-factor-online\scripts")

OUT = Path(r"D:\factor\platform_pool_tests_20260926")
run_id = "6ab7eee99e9d797cfb2cf8f0"
proc = subprocess.run(["pandaai-cli", "--json", "factor_result", run_id], capture_output=True)
raw = proc.stdout or b""
print("rc:", proc.returncode, "stdout bytes:", len(raw))
text = None
for enc in ("utf-8", "gb18030"):
    try:
        text = raw.decode(enc)
        print("decoded:", enc)
        break
    except UnicodeDecodeError as e:
        print("decode fail:", enc, str(e)[:80])
if text is None:
    text = raw.decode("utf-8", errors="replace")
payload = json.loads(text.lstrip("\ufeff"))
print("success:", payload.get("success"))
print("top keys:", [k for k in payload.keys()][:15])
d = OUT / "pool5-partt10-20260927-candidates.results"
d.mkdir(exist_ok=True)
p = d / (run_id + ".json")
p.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
print("saved:", p.name, p.stat().st_size, "bytes")
try:
    from batch import extract
    m = extract(payload, "1", 10)
    print("metrics:", json.dumps(m, ensure_ascii=False))
except Exception as e:
    print("extract fail:", type(e).__name__, str(e)[:200])