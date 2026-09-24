#!/usr/bin/env bash
# Relaxed-turnover wide-field GP mining batch (local, zero platform compute).
# Rule version: full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate4
# Field mode: all locally computable terminals (diagnostic-unverified), stale failure registry
# accepted explicitly because banned-field list is empty under both qualitygate3/4.
set -u
cd /data/games/factor_
ROOT=research_reports/platform_alignment/relaxed-gp-20260924
PY=python

common=(
  --universe full_a
  --aligned-cycle 10
  --aligned-start 20210907
  --aligned-end 20260907
  --aligned-min-periods 100
  --search-field-mode all
  --allow-unverified-fields
  --allow-stale-failure-registry
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

run net_all_s9701 --objective aligned_net_excess \
    --population-size 1000 --generations 40 --tournament-size 150 --seed 9701
run net_all_s9702 --objective aligned_net_excess \
    --population-size 1000 --generations 40 --tournament-size 600 --seed 9702
run eff40_s9711 --objective aligned_ic_efficiency \
    --aligned-turnover-cap 0.40 --aligned-net-floor 0.15 \
    --population-size 600 --generations 30 --tournament-size 200 --seed 9711
run sizeneut_all_s9731 --objective aligned_size_neutral_net \
    --population-size 1000 --generations 40 --tournament-size 150 --seed 9731
