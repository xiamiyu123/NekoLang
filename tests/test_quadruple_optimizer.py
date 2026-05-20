import unittest

from neko.quadruple_optimizer import optimize_quadruples
from neko.semantic import Quadruple


class TestQuadrupleOptimizer(unittest.TestCase):
    def test_eliminates_repeated_expression_in_basic_block(self):
        quads = [
            Quadruple("program", "t"),
            Quadruple("+", "I1", "I2", "T1"),
            Quadruple(":=", "T1", "_", "I3"),
            Quadruple("+", "I1", "I2", "T2"),
            Quadruple(":=", "T2", "_", "I4"),
            Quadruple("end", "t"),
        ]

        result = optimize_quadruples(quads)

        self.assertEqual(result.cse_count, 1)
        self.assertEqual([q.op for q in result.quadruples], ["program", "+", ":=", ":=", "end"])
        self.assertEqual(result.quadruples[3], Quadruple(":=", "I3", "_", "I4"))

    def test_does_not_reuse_expression_after_operand_reassignment(self):
        quads = [
            Quadruple("program", "t"),
            Quadruple("+", "I1", "I2", "T1"),
            Quadruple(":=", "T1", "_", "I3"),
            Quadruple(":=", "C1", "_", "I1"),
            Quadruple("+", "I1", "I2", "T2"),
            Quadruple(":=", "T2", "_", "I4"),
            Quadruple("end", "t"),
        ]

        result = optimize_quadruples(quads, {"1": "C1"})

        self.assertEqual(result.cse_count, 0)
        self.assertEqual([q.op for q in result.quadruples].count("+"), 2)
        self.assertEqual(result.quadruples[4], Quadruple("+", "C1", "I2", "T2"))

    def test_reuses_commuted_not_equal_expression(self):
        quads = [
            Quadruple("program", "t"),
            Quadruple("!=", "I1", "I2", "T1"),
            Quadruple(":=", "T1", "_", "I3"),
            Quadruple("!=", "I2", "I1", "T2"),
            Quadruple(":=", "T2", "_", "I4"),
            Quadruple("end", "t"),
        ]

        result = optimize_quadruples(quads)

        self.assertEqual(result.cse_count, 1)
        self.assertEqual([q.op for q in result.quadruples], ["program", "!=", ":=", ":=", "end"])
        self.assertEqual(result.quadruples[3], Quadruple(":=", "I3", "_", "I4"))

    def test_orders_commutative_operands_by_constant_named_temp(self):
        quads = [
            Quadruple("program", "t"),
            Quadruple("+", "I1", "C1", "T1"),
            Quadruple("+", "T1", "I1", "T2"),
            Quadruple(":=", "T2", "_", "I2"),
            Quadruple("end", "t"),
        ]

        result = optimize_quadruples(quads, {"7": "C1"})

        self.assertEqual(result.quadruples[1], Quadruple("+", "C1", "I1", "T1"))
        self.assertEqual(result.quadruples[2], Quadruple("+", "I1", "T1", "T2"))


if __name__ == "__main__":
    unittest.main()
