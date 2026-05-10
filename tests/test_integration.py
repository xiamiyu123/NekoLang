import unittest
import os
from neko.lexer import Lexer
from neko.parser import Parser
from neko.semantic import SemanticAnalyzer


def compile_source(source: str):
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    parser.set_source(source)
    ast = parser.parse()
    analyzer = SemanticAnalyzer()
    analyzer.set_source(source)
    quadruples = analyzer.analyze(ast)
    return analyzer


class TestCourseExample(unittest.TestCase):
    """Test the exact example from the course PPT."""

    def test_course_example_quadruples(self):
        source = """(nya example
  (nyan ((a int) (b int)))
  (paw
    (meow a 2)
    (meow b (+ (* 5 a) 2))
    (purr b)))"""
        analyzer = compile_source(source)
        quads = analyzer.quadruples

        self.assertEqual(quads[0].op, "program")
        self.assertEqual(quads[1].op, ":=")
        self.assertEqual(quads[1].ob1, "C1")  # constant 2
        self.assertEqual(quads[1].t, "I2")    # variable a

        mul_q = next(q for q in quads if q.op == "*")
        add_q = next(q for q in quads if q.op == "+")
        self.assertEqual(mul_q.ob1, "C2")  # constant 5
        self.assertEqual(mul_q.ob2, "I2")  # variable a
        self.assertEqual(add_q.ob2, "C1")  # constant 2

        self.assertEqual(quads[-1].op, "end")


class TestEndToEnd(unittest.TestCase):
    def test_hello_world(self):
        source = "(nya hello (nyan ((x int))) (paw (meow x 42) (purr x)))"
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)
        self.assertGreaterEqual(len(analyzer.quadruples), 4)

    def test_arithmetic_program(self):
        source = """(nya math
  (nyan ((a int) (b int)))
  (paw
    (meow a 3)
    (meow b 5)
    (purr (+ a b))))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn("+", ops)

    def test_conditional_program(self):
        source = """(nya cond
  (nyan ((x int) (y int)))
  (paw
    (meow x 10)
    (if-nya (> x 5)
      (meow y 1)
      (meow y 0))
    (purr y)))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn(">", ops)
        self.assertIn("if_false", ops)

    def test_while_program(self):
        source = """(nya loop
  (nyan ((i int) (sum int)))
  (paw
    (meow i 0)
    (meow sum 0)
    (purr-while (<= i 5)
      (paw
        (meow sum (+ sum i))
        (meow i (+ i 1))))
    (purr sum)))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn("<=", ops)
        self.assertIn("if_false", ops)

    def test_nested_expressions(self):
        source = """(nya nested
  (nyan ((a int) (b int) (c int)))
  (paw
    (meow a 1)
    (meow b 2)
    (meow c 3)
    (purr (+ (* a b) (- c 1)))))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn("*", ops)
        self.assertIn("-", ops)
        self.assertIn("+", ops)

    def test_full_feature_program(self):
        source = """(nya full
  (nyan ((a int) (b int) (result int) (flag int)))
  (paw
    (meow a 10)
    (meow b 3)
    (meow result (+ (* a b) (- a b)))
    (purr result)
    (if-nya (> result 20)
      (meow flag 1)
      (meow flag 0))
    (purr flag)
    (meow a 0)
    (purr-while (< a 5)
      (paw
        (purr a)
        (meow a (+ a 1))))))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)
        self.assertGreater(len(analyzer.quadruples), 15)

    def test_fibonacci(self):
        source = """(nya fibonacci
  (nyan ((a int) (b int) (c int) (n int) (i int)))
  (paw
    (meow a 0)
    (meow b 1)
    (meow n 10)
    (meow i 0)
    (purr a)
    (purr b)
    (purr-while (< i n)
      (paw
        (meow c (+ a b))
        (meow a b)
        (meow b c)
        (purr c)
        (meow i (+ i 1))))))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)
        self.assertGreaterEqual(len(analyzer.quadruples), 20)


class TestFileFixtures(unittest.TestCase):
    """Test that fixture .neko files compile without errors."""

    def _compile_file(self, path: str):
        with open(path, "r") as f:
            source = f.read()
        return compile_source(source)

    def test_hello(self):
        analyzer = self._compile_file("tests/fixtures/hello.neko")
        self.assertEqual(len(analyzer.errors), 0)

    def test_arithmetic(self):
        analyzer = self._compile_file("tests/fixtures/arithmetic.neko")
        self.assertEqual(len(analyzer.errors), 0)

    def test_conditional(self):
        analyzer = self._compile_file("tests/fixtures/conditional.neko")
        self.assertEqual(len(analyzer.errors), 0)

    def test_while_loop(self):
        analyzer = self._compile_file("tests/fixtures/while_loop.neko")
        self.assertEqual(len(analyzer.errors), 0)

    def test_full_example(self):
        analyzer = self._compile_file("tests/fixtures/full_example.neko")
        self.assertEqual(len(analyzer.errors), 0)


if __name__ == "__main__":
    unittest.main()
