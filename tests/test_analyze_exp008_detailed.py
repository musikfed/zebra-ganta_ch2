import unittest
from tools.analyze_exp008_detailed import spearman


class DetailedExp008Tests(unittest.TestCase):
    def test_rank_order(self):
        self.assertEqual(spearman([1,2,3,4],[2,4,6,8]),1.0)
        self.assertEqual(spearman([1,2,3,4],[8,6,4,2]),-1.0)
    def test_not_enough_data(self):
        self.assertIsNone(spearman([1],[1]))
        self.assertIsNone(spearman([1,1,1],[2,3,4]))
    def test_ties(self):
        self.assertAlmostEqual(spearman([1,1,2,2],[5,5,6,6]),1.0)
