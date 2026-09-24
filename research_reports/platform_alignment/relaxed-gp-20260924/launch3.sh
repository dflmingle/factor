#!/usr/bin/env bash
# Wide-field GP mining, wave 3 (local, zero platform compute).
# Adds the size-exclusion control experiment: same objective, same budget, but
# the 17 market-cap / share-count / amv* fields are removed from the terminal
# set, so the answer to "is net excess pinned to the size axis?" is measurable.
set -u
cd /data/games/factor_
ROOT=research_reports/platform_alignment/relaxed-gp-20260924
FIELDS=$ROOT/fields_nosize.txt
ALLL=research_reports/platform_alignment/wider-field-search-20260923/fields.txt
PY=python

base=(
  --universe full_a
  --aligned-cycle 10
  --aligned-start 20210907
  --aligned-end 20260907
  --aligned-min-periods 100
  --search-field-mode all
  --allow-unverified-fields
  --allow-stale-failure-registry
  --field-cache-size 48
  --field-array-cache-size 400
  --device cuda:0
)

run() {
  local name="$1"; local fields="$2"; shift 2
  local dir="$ROOT/$name"
  mkdir -p "$dir"
  setsid nohup "$PY" scripts/alphaprobe_gp_tushare.py "${base[@]}" \
      --search-field-file "$fields" --output "$dir/gp" "$@" > "$dir/run.log" 2>&1 &
  disown
  echo "started $name pid=$!"
}

run net_wide_s9803 "$ALLL" --objective aligned_net_excess \
    --population-size 1000 --generations 40 --tournament-size 300 --seed 9803
run net_wide_s9804 "$ALLL" --objective aligned_net_excess \
    --population-size 1000 --generations 40 --tournament-size 150 --seed 9804
run net_nosize_s9831 "$FIELDS" --objective aligned_net_excess \
    --population-size 1000 --generations 40 --tournament-size 150 --seed 9831
run net_nosize_s9832 "$FIELDS" --objective aligned_net_excess \
    --population-size 1000 --generations 40 --tournament-size 600 --seed 9832
run front_wide_s9841 "$ALLL" --objective aligned_ic_frontier \
    --population-size 1000 --generations 40 --tournament-size 150 --seed 9841
run eff60_s9851 "$ALLL" --objective aligned_ic_efficiency \
    --aligned-turnover-cap 0.60 --aligned-net-floor 0.15 \
    --population-size 800 --generations 30 --tournament-size 200 --seed 9851
