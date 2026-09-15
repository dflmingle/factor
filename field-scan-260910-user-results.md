# E/F/G PandaAI Field Scan

This is the result block supplied from the PandaAI backtest interface. All rows use the five-year, 5-day, 10-group, 0.30% one-way-cost setup stated in the source message.

| Batch | Candidate | Direction | Rank_IC | ICIR | Net excess %/yr |
| --- | --- | ---: | ---: | ---: | ---: |
| E | E260910-04 | 1 | 0.0670 | 0.2637 | 17.7951 |
| E | E260910-14 | 1 | not supplied | not supplied | 17.0381 |
| E | E260910-15 | 1 | not supplied | not supplied | 14.8251 |
| E | E260910-10 | 1 | not supplied | not supplied | 14.1620 |
| E | E260910-11 | 1 | not supplied | not supplied | 6.7107 |
| E | E260910-13 | 1 | not supplied | not supplied | 1.7271 |
| E | E260910-03 | 1 | not supplied | not supplied | 1.5353 |
| E | E260910-05 | 0 | not supplied | not supplied | 0.7030 |
| F | F260910-12 | 1 | 0.0662 | 0.2597 | 15.4589 |
| F | F260910-14 | 1 | not supplied | not supplied | 14.9289 |
| F | F260910-01 | 1 | not supplied | not supplied | 14.6590 |
| F | F260910-15 | 1 | not supplied | not supplied | 13.6458 |
| F | F260910-11 | 0 | not supplied | not supplied | 3.7672 |
| F | F260910-10 | 1 | not supplied | not supplied | 3.0792 |
| F | F260910-09 | 1 | not supplied | not supplied | 1.7913 |
| F | F260910-13 | 1 | not supplied | not supplied | 1.0699 |
| F | F260910-06 | 1 | not supplied | not supplied | 0.2156 |
| G | G260910-13 | 1 | 0.0442 | 0.2612 | 14.1905 |
| G | G260910-01 | 1 | 0.0569 | 0.2521 | 13.1180 |
| G | G260910-12 | 1 | not supplied | not supplied | 12.9620 |
| G | G260910-11 | 1 | not supplied | not supplied | 12.8259 |
| G | G260910-14 | 1 | not supplied | not supplied | 12.7380 |
| G | G260910-10 | 1 | not supplied | not supplied | 11.7852 |
| G | G260910-15 | 1 | not supplied | not supplied | 11.5150 |
| G | G260910-06 | 1 | not supplied | not supplied | 7.1361 |

The exact formulas are in [field-scan-260910-user-batch.txt](field-scan-260910-user-batch.txt). The supplied source only included Rank_IC and ICIR for the rows shown with values; the other metric cells are intentionally left as `not supplied` rather than inferred.
