# AlphaGen pool optimiser - opt stage (2026-10-02, zero platform compute)

- library: 48 candidates = 5 seats + LAMD10-K5V2 + 42 legs
- train <= 2024-09-06 (73 dates), val = rest (47 dates)
- objective: alphagen AlphaPool loss (Adam, l1) + greedy forward selection

## Legs-only combos (ranked by valid-window RankIC)

| id | n | ric_train | ric_val | ric_full | signed_full | max|corr seats| | legs |
|---|---:|---:|---:|---:|---:|---:|---|
| AGP01 | 6 | 0.1329 | 0.1174 | 0.1269 | 0.1170 | 0.782 | intr20(+0.18); amt60(+0.32); vs_756(+0.13); retrev20(+0.19); downup(+0.09); cstd20_60(+0.09) |
| AGP02 | 3 | 0.1316 | 0.1149 | 0.1251 | 0.1238 | 0.781 | intr20(+0.40); amt60(+0.40); vs_756(+0.20) |
| AGP03 | 6 | 0.1301 | 0.1101 | 0.1223 | 0.1206 | 0.774 | cstd20(+0.21); amt60(+0.19); intr20(+0.16); drift20(+0.16); amihud20(-0.15); retrev20(+0.13) |
| AGP04 | 1 | 0.0962 | 0.0900 | 0.0938 | 0.0938 | 0.422 | intr20(+1.00) |
| AGP05 | 6 | 0.1352 | 0.0829 | 0.1147 | 0.1081 | 0.753 | cstd20(+0.23); retrev20(+0.21); amt60(+0.16); retrev10(-0.15); retrev5(+0.15); amihud20(-0.10) |

## Greedy paths

| tag | step | add | trial_ic | refit_ic | members |
|---|---:|---|---:|---:|---|
| all | 1 | mix:LAMD10-K5V2 | 0.0733 | 0.0733 | ["mix:LAMD10-K5V2"] |
| all | 2 | seat:t10_size_plus_impact_bm | 0.0773 | 0.0773 | ["mix:LAMD10-K5V2", "seat:t10_size_plus_impact_bm"] |
| all | 3 | leg:retrev20 | 0.0793 | 0.0793 | ["mix:LAMD10-K5V2", "seat:t10_size_plus_impact_bm", "leg:retrev20"] |
| all | 4 | leg:downup | 0.0803 | 0.0803 | ["mix:LAMD10-K5V2", "seat:t10_size_plus_impact_bm", "leg:retrev20", "leg:downup"] |
| all | 5 | leg:retmom60 | 0.0809 | 0.0809 | ["mix:LAMD10-K5V2", "seat:t10_size_plus_impact_bm", "leg:retrev20", "leg:downup", "leg:retmom60"] |
| all | 6 | leg:retstd20_60 | 0.0812 | 0.0812 | ["mix:LAMD10-K5V2", "seat:t10_size_plus_impact_bm", "leg:retrev20", "leg:downup", "leg:retmom60", "leg:retstd20_60"] |
| legs | 1 | leg:intr20 | 0.0551 | 0.0551 | ["leg:intr20"] |
| legs | 2 | leg:amt60 | 0.0711 | 0.0711 | ["leg:intr20", "leg:amt60"] |
| legs | 3 | leg:vs_756 | 0.0762 | 0.0762 | ["leg:intr20", "leg:amt60", "leg:vs_756"] |
| legs | 4 | leg:retrev20 | 0.0776 | 0.0776 | ["leg:intr20", "leg:amt60", "leg:vs_756", "leg:retrev20"] |
| legs | 5 | leg:downup | 0.0785 | 0.0785 | ["leg:intr20", "leg:amt60", "leg:vs_756", "leg:retrev20", "leg:downup"] |
| legs | 6 | leg:cstd20_60 | 0.0792 | 0.0792 | ["leg:intr20", "leg:amt60", "leg:vs_756", "leg:retrev20", "leg:downup", "leg:cstd20_60"] |
