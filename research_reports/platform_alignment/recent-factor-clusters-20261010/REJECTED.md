# 未采用的首轮物化

本目录为归簇补录的首轮中间计算，不作为正式归簇结果。

核对引擎后发现：AlphaPROBE 原生 Rank 使用 ordinal ties；TsPctChange 的 N 是窗口观测数，N=1 恒为零，不能直接充当平台 RETURNS 的 N 日滞后。

正式补录在 `../recent-factor-clusters-20261010-average-rank-v2/`。该版本使用平均秩，平台 RETURNS 显式实现为 `X/DELAY(X,N)-1`；GP 原生表达式仍按保存的原生语义物化并标记。

旧面板保留用于审计，不与新面板合并。没有平台调用或平台回测。
