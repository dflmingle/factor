# H03 10-Day Single-Factor Comparison

- Formula: `RANK(SUM((HIGH-LOW)/(DELAY(CLOSE,1)+0.000001),60)/(SUM(AMOUNT,60)+1))`
- Window: 2021-09-07 to 2026-09-07
- Rebalance: 10 trading days
- Groups: 10
- One-way cost: 0.30%
- Result is an in-sample screening result; no independent OOS test has been run.

| Candidate | Rank_IC | ICIR | Long excess %/yr | Turnover % | Annual cost % | Net excess %/yr |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| H03-T10-SINGLE | 0.0665 | 0.3606 | 17.86 | 9.37 | 1.4167 | 16.4433 |
| T10-SIZE-PLUS-IMPACT | 0.1113 | 0.4524 | 22.79 | 30.64 | 4.6328 | 18.1572 |
| COMBO-DIRECT-OSR2-CHIP-TURN-SIZE-EQ | 0.1104 | 0.4527 | 21.93 | 36.68 | 5.5460 | 16.3840 |

## Conclusion

H03 alone is approximately level with the existing T10-SIZE baseline: net excess is higher by only 0.0593 percentage points. Adding H03 to the four-sleeve baseline raises net excess by 1.7732 percentage points versus the baseline and by 1.7140 percentage points versus H03 alone. This supports combination compatibility, not proof of independent alpha. Cross-sectional correlation and exposure attribution remain unmeasured.
