import unittest
import os
import tempfile

import pytest

from neko import cli as neko_cli
from neko.lexer import Lexer
from neko.parser import Parser
from neko.semantic import SemanticAnalyzer
from tests._cli_support import run_cli_main


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
        source = """(program example
  (var ((a int) (b int)))
  (begin
    (:= a 2)
    (:= b (+ (* 5 a) 2))
    (print b)))"""
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
        source = "(program hello (var ((x int))) (begin (:= x 42) (print x)))"
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)
        self.assertGreaterEqual(len(analyzer.quadruples), 4)

    def test_personalized_alias_program(self):
        source = "(nya hello (nyan ((x int))) (paw (:= x 42) (meow x)))"
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn(":=", ops)
        self.assertIn("print", ops)

    def test_function_and_bool_program(self):
        source = """(program check
  (var ((flag bool) (value int)))
  (begin
    (function positive ((x int)) bool
      (return (> x 0)))
    (:= value 3)
    (:= flag (positive value))
    (print flag)))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn("call", ops)
        self.assertIn("return", ops)

    def test_arithmetic_program(self):
        source = """(program math
  (var ((a int) (b int)))
  (begin
    (:= a 3)
    (:= b 5)
    (print (+ a b))))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn("+", ops)

    def test_conditional_program(self):
        source = """(program cond
  (var ((x int) (y int)))
  (begin
    (:= x 10)
    (if (> x 5)
      (:= y 1)
      (:= y 0))
    (print y)))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn(">", ops)
        self.assertIn("if_false", ops)

    def test_while_program(self):
        source = """(program loop
  (var ((i int) (sum int)))
  (begin
    (:= i 0)
    (:= sum 0)
    (while (<= i 5)
      (begin
        (:= sum (+ sum i))
        (:= i (+ i 1))))
    (print sum)))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn("<=", ops)
        self.assertIn("if_false", ops)

    def test_nested_expressions(self):
        source = """(program nested
  (var ((a int) (b int) (c int)))
  (begin
    (:= a 1)
    (:= b 2)
    (:= c 3)
    (print (+ (* a b) (- c 1)))))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn("*", ops)
        self.assertIn("-", ops)
        self.assertIn("+", ops)

    def test_full_feature_program(self):
        source = """(program full
  (var ((a int) (b int) (result int) (flag int)))
  (begin
    (:= a 10)
    (:= b 3)
    (:= result (+ (* a b) (- a b)))
    (print result)
    (if (> result 20)
      (:= flag 1)
      (:= flag 0))
    (print flag)
    (:= a 0)
    (while (< a 5)
      (begin
        (print a)
        (:= a (+ a 1))))))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)
        self.assertGreater(len(analyzer.quadruples), 15)

    def test_fibonacci(self):
        source = """(program fibonacci
  (var ((a int) (b int) (c int) (n int) (i int)))
  (begin
    (:= a 0)
    (:= b 1)
    (:= n 10)
    (:= i 0)
    (print a)
    (print b)
    (while (< i n)
      (begin
        (:= c (+ a b))
        (:= a b)
        (:= b c)
        (print c)
        (:= i (+ i 1))))))"""
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


class TestCLI(unittest.TestCase):
    def _run_cli(self, *args):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return run_cli_main(neko_cli.main, args, repo_root, subprocess_module=neko_cli.subprocess)

    def test_check_command(self):
        result = self._run_cli("check", "examples/demo.neko")
        self.assertEqual(result.returncode, 0)
        self.assertIn("检查通过", result.stdout)

    @pytest.mark.slow
    def test_run_command_with_args(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = os.path.join(tmpdir, "args.neko")
            with open(source_path, "w", encoding="utf-8") as f:
                f.write(
                    "(program args (var ((count int) (value int))) "
                    "(begin (:= count (argc)) (:= value (argv-int 0)) (print count) (print value)))"
                )
            result = self._run_cli("run", source_path, "--", "9")
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "1\n9")

    @pytest.mark.slow
    def test_legacy_compile_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "legacy-demo")
            result = self._run_cli("examples/demo.neko", "--compile", output_path)
            self.assertEqual(result.returncode, 0)
            self.assertTrue(os.path.exists(output_path))


if __name__ == "__main__":
    unittest.main()
