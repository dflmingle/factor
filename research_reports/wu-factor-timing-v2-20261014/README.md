# Wu (2024) reproduction attempt

See [summary.md](summary.md) for results and [method mapping](../literature/wu-china-factor-timing-20261014/method_mapping.md) for original/proxy boundaries.

Re-run from repository root:

```bash
python scripts/wu_factor_timing_inputs_20261014.py
python scripts/wu_factor_timing_models_20261014.py
python scripts/wu_factor_timing_models_20261014.py --clusters --wings LS
python scripts/wu_factor_timing_verify_20261014.py
python scripts/wu_factor_timing_evaluate_20261014.py
python scripts/wu_factor_timing_report_20261014.py
```

All24 factor definitions: `factor_definitions.csv`. Model outputs include unsuccessful forecasts. Cached inputs are versioned; use a new output directory after changing assumptions. No PandaAI calls or live pool changes.
