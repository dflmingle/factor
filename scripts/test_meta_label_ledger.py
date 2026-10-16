"""Economic invariants for the corrected ledger, independent of research data."""
import unittest
import numpy as np
import pandas as pd
from meta_label_ledger import trade, daily_ledger, period_ledger


class LedgerTests(unittest.TestCase):
    def test_cash_entry_and_full_replacement(self):
        t = trade([0, 0], [1, 0])
        self.assertAlmostEqual(t['fee'], .003/1.003, places=13)
        self.assertAlmostEqual(t['buy']+t['fee'], 1, places=13)
        r = trade([1, 0], [0, 1])
        self.assertAlmostEqual(r['fee'], .006/1.003, places=13)
        self.assertAlmostEqual(r['sell'], 1, places=13)

    def test_unchanged_holdings_can_require_rebalancing(self):
        # Same members, but one appreciated: restoring equal weights trades.
        t = trade([.75, .25], [.5, .5])
        self.assertAlmostEqual(t['fee'], .0015, places=13)
        self.assertGreater(t['turnover'], .24)
        self.assertAlmostEqual(trade([.5,.5],[.5,.5])['fee'], 0, places=13)

    def test_shrinking_holdings_sells_and_reinvests(self):
        t = trade([.5,.5], [1,0])
        self.assertAlmostEqual(t['sell'], .5, places=13)
        self.assertGreater(t['buy'], .49)
        self.assertGreater(t['fee'], .0029)

    def test_daily_matches_direct_cash_share_account(self):
        # Two one-day holding intervals, common boundary close, full replacement.
        cal = pd.date_range('2024-01-01', periods=4)
        close = np.array([[100,100],[100,100],[110,90],[120,99]], float)
        periods, daily, _ = daily_ledger([{0},{1}], [np.array([0,1])]*2,
                                         [0,1], cal[:2], cal, close, cycle=1)
        shares_a = 1/1.003/100
        cash_after_sale = shares_a*110*(1-.003)
        shares_b = cash_after_sale/1.003/90
        final_nav = shares_b*99
        self.assertAlmostEqual(np.prod(1+daily.portfolio), final_nav, places=12)
        self.assertGreater(periods.iloc[1].fee, .0059)
        self.assertAlmostEqual(np.prod(1+daily.portfolio), np.prod(1+periods.net_held), places=12)

    def test_continuous_ledger_charges_block_boundary(self):
        r = np.zeros((3,2))
        p = period_ledger([{0},{0},{1}], [np.array([0,1])]*3, r, [0,1,2])
        self.assertGreater(p.iloc[0].fee, 0)
        self.assertAlmostEqual(p.iloc[1].fee, 0, places=13)
        self.assertGreater(p.iloc[2].fee, .0059)


if __name__ == '__main__':
    unittest.main()
