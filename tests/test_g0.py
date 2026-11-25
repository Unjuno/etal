import unittest
from fractions import Fraction as Q
from etal.g0 import TASKS, STATES, best, row, utility, grid

class TestG0(unittest.TestCase):
    def test_consequence_keeps_initial_marginal(self):
        self.assertEqual(TASKS['C'][0], TASKS['N'][0])
        self.assertNotEqual(TASKS['C'][1], TASKS['N'][1])
        self.assertEqual(TASKS['F'][1], TASKS['N'][1])
        self.assertNotEqual(TASKS['F'][0], TASKS['N'][0])
        self.assertTrue(all(sum(p)==1 for p,_ in TASKS.values()))
    def test_source_compression(self):
        r=row(1,'C',Q(1,20),Q(1),Q(0),100)
        self.assertEqual(r['source_optimum'],Q(19,20))
        self.assertEqual(r['fixed_post_min'],Q(9,20))
        self.assertEqual(r['fixed_post_max'],Q(9,20))
        self.assertEqual(r['gain_min'],Q(1,2))
    def test_free_inspection_removes_benefit(self):
        r=row(1,'C',Q(1,20),Q(0),Q(0),100)
        self.assertEqual(r['gain_max'],0)
        self.assertEqual(r['no_message_post'],1)
    def test_frequency_no_semantic_shift(self):
        r=row(1,'F',Q(1,20),Q(1),Q(0),100)
        self.assertEqual(r['gain_max'],0)
    def test_no_shift(self):
        self.assertEqual(row(1,'N',Q(1,20),Q(1),Q(0),10)['gain_max'],0)
    def test_migration_cost(self):
        self.assertEqual(row(1,'C',Q(1,20),Q(1),Q(10),10)['gain_max'],0)
        self.assertEqual(row(1,'C',Q(1,20),Q(1),Q(1),10)['gain_min'],Q(2,5))
    def test_sufficient_fixed(self):
        r=row(1,'C',Q(0),Q(1),Q(1),10)
        self.assertEqual(r['sufficient_fixed_post'],1)
        self.assertLess(r['adaptive_post_max'],r['sufficient_fixed_post'])
    def test_symbol_rename(self):
        c=(0,0,1,1)
        self.assertEqual(utility(c,1,'C',Q(1,20),Q(1)),utility(tuple(1-x for x in c),1,'C',Q(1,20),Q(1)))
    def test_sufficient_source_ties_are_retained(self):
        r=row(2,'C',Q(1,20),Q(1),Q(0),10)
        self.assertLess(r['fixed_post_min'],r['fixed_post_max'])
        self.assertEqual(r['gain_min'],0)
    def test_all_cells(self):
        rows=list(grid())
        self.assertEqual(len(rows),864)
        self.assertTrue(all(r['gain_min']>=0 and r['gain_max']>=r['gain_min'] for r in rows))
