import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = r"D:\factor\scripts\gp_platform_submit_20260925.py"
text = open(p, encoding="utf-8").read()
old = ('CAND = BASE / "candidates_panda.txt"\n'
       'STATE = BASE / "candidates_panda.txt.state.json"\n'
       'DOWNLOAD = BASE / "downloads"\n'
       'LOG = BASE / "submit.log"')
new = ('CAND = Path(os.environ.get("PANDA_CAND", str(BASE / "candidates_panda.txt")))\n'
       'STATE = CAND.with_suffix(CAND.suffix + ".state.json")\n'
       'DOWNLOAD = CAND.parent / "downloads"\n'
       'LOG = CAND.parent / (CAND.stem + ".submit.log")')
assert old in text, "anchor not found"
open(p, "w", encoding="utf-8").write(text.replace(old, new, 1))
print("runner patched for PANDA_CAND")