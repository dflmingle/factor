import subprocess, io, sys, json, os, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = r"D:\factor\research_reports\platform_alignment\gp-platform-tests-20260925"
env = dict(os.environ, PYTHONUTF8="1")
dl = os.path.join(BASE, "downloads")
os.makedirs(dl, exist_ok=True)
for rid in ["6ab63731cd820fa2a40a6b87", "6ab636d745ce44aed9d15615"]:
    p = subprocess.run(["pandaai-cli", "--json", "factor_result", rid, "--download", dl],
                       capture_output=True, env=env, timeout=900)
    t = p.stdout.decode("utf-8", errors="replace")
    print("run", rid, "rc", p.returncode, "stdout head:", t[:200].replace(chr(10), " "))
    print("   stderr:", p.stderr.decode("utf-8", errors="replace")[:200])
print("downloads now:")
for f in glob.glob(os.path.join(dl, "**", "*"), recursive=True):
    print("   ", f, os.path.getsize(f) if os.path.isfile(f) else "DIR")