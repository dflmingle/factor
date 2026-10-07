"""Verify literal payload emission round-trips the npz arrays exactly (2026-10-01)."""
import importlib.util
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "mlx", ROOT / "scripts" / "ml_combo_walkforward_export_20261001.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

z = np.load(ROOT / "research_reports/platform_alignment/ml-combo-platform-20261001/models_wf.npz",
            allow_pickle=False)
payloads = {k: z[k] for k in z.files}
cuts = ["2024-08-31", "2025-08-31", "2026-09-07"]
block = mod.emit_payload_block(payloads, cuts)
print("block chars", len(block))

ns = {"__name__": "t"}
exec(compile(block, "<block>", "exec"), ns)
ok = True
for wi in range(3):
    m = ns[f"_M{wi}"]
    for k, dt in (("feat", np.int16), ("threshold", np.float64), ("left", np.int32),
                  ("right", np.int32), ("missing_left", np.uint8), ("leaf_value", np.float64),
                  ("offsets", np.int32)):
        same = bool(np.array_equal(np.asarray(m[k], dtype=dt), z[f"m{wi}_{k}"]))
        ok &= same
        if not same:
            print("MISMATCH", wi, k)
    base_ok = float(m["baseline"]) == float(z[f"m{wi}_baseline"][0])
    ok &= base_ok
    if not base_ok:
        print("BASE MISMATCH", wi)
print("roundtrip exact:", ok, "| _MODELS len", len(ns["_MODELS"]))

text = mod.FACTOR_TEMPLATE.format(payload_block=block, features=mod.FEATURES, cuts=cuts)
print("factor text chars", len(text))
ns2 = {"Factor": object, "__name__": "factor_mod"}
exec(compile(text, "<factor>", "exec"), ns2)
models = ns2["_models"]()
print("models keys", sorted(models[0].keys()))
test = np.asarray(models[2]["feat"], dtype=np.int16)
print("models[2] nodes", len(test), "first feat", int(test[0]))
