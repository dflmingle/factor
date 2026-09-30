#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, "/data/games/factor_/scripts")
import gp_candidates_vs_clusters_20260924 as M

M.CAND_PATH = Path("/tmp/factor_cluster_20260930/nf_candidates.csv")
M.PAIRS_PATH = Path("/tmp/factor_cluster_20260930/members77.csv")
M.CLUSTER_PATH = Path("/data/games/factor_/research_reports/platform_alignment/all-factor-cluster-expansion-20260919.clusters.csv")
sys.argv = ["run.py", "--out", "/tmp/factor_cluster_20260930/overlap",
            "--stage", "eval", "--eval-mode", "chunkmajor", "--day-chunk", "30",
            "--threads", "32"]
raise SystemExit(M.main())
