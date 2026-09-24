#!/usr/bin/env bash
# Parallel candidate screening: 8 shards, one panel load each, merged afterwards.
set -u
cd /data/games/factor_
ROOT=research_reports/platform_alignment/relaxed-gp-20260924/screen2
for i in 0 1 2 3 4 5 6 7; do
  setsid nohup python scripts/relaxed_gp_screen_20260924.py --runs all \
      --pool-per-band 120 --per-band 25 --device cpu --shard-index "$i" --shard-count 8 \
      --out "$ROOT" > "$ROOT/shard$i.log" 2>&1 &
  disown
done
echo launched
