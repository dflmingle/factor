#!/usr/bin/env bash
# Wide-field GP mining, wave 2 (local, zero platform compute).
#
# Wave 1 used the full 1,152-terminal active set and was killed: every
# evaluation rebuilt named-field panels because the field LRU held only 24
# entries (measured: >3 s for a single cold field panel).  Wave 2 keeps the
# 374-field curated set and separates the CPU array cache (400 fields) from
# the device panel cache (48), so each field is built once per run.
set -u
cd /data/games/factor_
ROOT=research_reports/platform_alignment/relaxed-gp-20260924
FIELDS=research_reports/platform_alignment/wider-field-search-20260923/fields.txt
PY=python

common=(
  --universe full_a
  --aligned-cycle 10
  --aligned-start 20210907
  --aligned-end 20260907
  --aligned-min-periods 100
  --search-field-mode all
  --search-field-file "$FIELDS"
  --allow-unverified-fields
  --allow-stale-failure-registry
  --field-cache-size 48
  --field-array-cache-size 400
  --device cuda:0
)

run() {
  local name="$1"; shift
  local dir="$ROOT/$name"
  mkdir -p "$dir"
  setsid nohup "$PY" scripts/alphaprobe_gp_tushare.py "${common[@]}" \
      --output "$dir/gp" "$@" > "$dir/run.log" 2>&1 &
  disown
  echo "started $name pid=$!"
}

run net_wide_s9801 --objective aligned_net_excess \
    --population-size 1000 --generations 40 --tournament-size 150 --seed 9801
run net_wide_s9802 --objective aligned_net_excess \
    --population-size 1000 --generations 40 --tournament-size 600 --seed 9802
run eff40_s9811 --objective aligned_ic_efficiency \
    --aligned-turnover-cap 0.40 --aligned-net-floor 0.15 \
    --population-size 800 --generations 30 --tournament-size 200 --seed 9811
run sizeneut_wide_s9821 --objective aligned_size_neutral_net \
    --population-size 800 --generations 30 --tournament-size 150 --seed 9821
