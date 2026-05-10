"""Tests for NekoLang LLVM backend - compile and run programs."""

import unittest
import os
import subprocess
import tempfile
import shutil

from neko.lexer import Lexer
from neko.parser import Parser
from neko.semantic import SemanticAnalyzer
from neko.codegen_llvm import LLVMCodegen


def compile_and_run(source: str) -> str:
    """Compile NekoLang source to executable, run it, return stdout."""
    # Parse and analyze
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    parser.set_source(source)
    ast = parser.parse()

    analyzer = SemanticAnalyzer()
    analyzer.set_source(source)
    analyzer.analyze(ast)

    # Generate LLVM IR
    codegen = LLVMCodegen()
    ir_text = codegen.generate(ast)

    # Find runtime.c
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime_c = os.path.join(script_dir, "runtime", "runtime.c")

    # Write IR to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ll", delete=False) as f:
        f.write(ir_text)
        ll_path = f.name

    # Create temp output path
    out_path = ll_path.replace(".ll", "")

    try:
        # Compile with clang
        result = subprocess.run(
            ["clang", runtime_c, ll_path, "-o", out_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"clang failed:\n{result.stderr}")

        # Run
        result = subprocess.run([out_path], capture_output=True, text=True)
        return result.stdout.strip()
    finally:
        os.unlink(ll_path)
        if os.path.exists(out_path):
            os.unlink(out_path)


def generate_ir(source: str) -> str:
    """Generate LLVM IR text from source."""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    parser.set_source(source)
    ast = parser.parse()
    codegen = LLVMCodegen()
    return codegen.generate(ast)


class TestIRGeneration(unittest.TestCase):
    """Test that LLVM IR contains expected instructions."""

    def test_program_structure(self):
        ir = generate_ir("(program t (begin (print 0)))")
        self.assertIn('"main"', ir)
        self.assertIn("ret i32 0", ir)
        self.assertIn("declare", ir)  # runtime declarations

    def test_variable_alloca(self):
        ir = generate_ir("(program t (var ((x int))) (begin (:= x 1)))")
        self.assertIn("alloca i32", ir)
        self.assertIn("store i32 1", ir)

    def test_arithmetic_ops(self):
        ir = generate_ir("(program t (var ((x int))) (begin (:= x (+ 1 2))))")
        self.assertIn("add i32", ir)

    def test_mul_div(self):
        ir = generate_ir("(program t (var ((x int))) (begin (:= x (* 3 4))))")
        self.assertIn("mul i32", ir)

    def test_comparison(self):
        ir = generate_ir("(program t (var ((x int))) (begin (if (> x 0) (:= x 1) (:= x 0))))")
        self.assertIn("icmp", ir)
        self.assertIn("br i1", ir)

    def test_if_blocks(self):
        ir = generate_ir("(program t (var ((x int))) (begin (if (> x 0) (:= x 1) (:= x 0))))")
        self.assertIn("if.then", ir)
        self.assertIn("if.else", ir)
        self.assertIn("if.end", ir)

    def test_while_blocks(self):
        ir = generate_ir("(program t (var ((i int))) (begin (while (< i 10) (:= i (+ i 1)))))")
        self.assertIn("while.cond", ir)
        self.assertIn("while.body", ir)
        self.assertIn("while.end", ir)

    def test_float_type(self):
        ir = generate_ir("(program t (var ((x float))) (begin (:= x 3.14)))")
        self.assertIn("double", ir)

    def test_print_call(self):
        ir = generate_ir("(program t (var ((x int))) (begin (:= x 42) (print x)))")
        self.assertIn('call void @"nekoprint_int"', ir)

    def test_printf_declared(self):
        ir = generate_ir("(program t (begin (print 0)))")
        self.assertIn('declare void @"nekoprint_int"', ir)
        self.assertIn('declare void @"nekoprint_bool"', ir)

    def test_array_gep(self):
        ir = generate_ir("(program t (var ((arr (array int 5)))) (begin (array-set arr 0 42)))")
        self.assertIn("getelementptr", ir)

    def test_bool_type(self):
        ir = generate_ir("(program t (var ((flag bool))) (begin (:= flag true) (print flag)))")
        self.assertIn("i1", ir)

    def test_function_definition_ir(self):
        ir = generate_ir(
            "(program t (begin (function add ((a int) (b int)) int (return (+ a b)))))"
        )
        self.assertIn('define i32 @"add"', ir)
        self.assertIn("ret i32", ir)


class TestBasicExecution(unittest.TestCase):
    """Test compiled programs produce correct output."""

    def test_print_literal(self):
        output = compile_and_run("(program t (begin (print 42)))")
        self.assertEqual(output, "42")

    def test_meow_print_alias(self):
        output = compile_and_run("(program t (var ((x int))) (begin (:= x 42) (meow x)))")
        self.assertEqual(output, "42")

    def test_variable_assign(self):
        output = compile_and_run("(program t (var ((x int))) (begin (:= x 99) (print x)))")
        self.assertEqual(output, "99")

    def test_addition(self):
        output = compile_and_run("(program t (var ((x int))) (begin (:= x (+ 3 4)) (print x)))")
        self.assertEqual(output, "7")

    def test_subtraction(self):
        output = compile_and_run("(program t (var ((x int))) (begin (:= x (- 10 3)) (print x)))")
        self.assertEqual(output, "7")

    def test_multiplication(self):
        output = compile_and_run("(program t (var ((x int))) (begin (:= x (* 3 4)) (print x)))")
        self.assertEqual(output, "12")

    def test_division(self):
        output = compile_and_run("(program t (var ((x int))) (begin (:= x (/ 15 4)) (print x)))")
        self.assertEqual(output, "3")

    def test_nested_arithmetic(self):
        output = compile_and_run("(program t (var ((x int))) (begin (:= x (+ (* 5 2) 3)) (print x)))")
        self.assertEqual(output, "13")

    def test_multiple_variables(self):
        source = """(program t (var ((a int) (b int)))
          (begin (:= a 10) (:= b 20) (print (+ a b))))"""
        output = compile_and_run(source)
        self.assertEqual(output, "30")

    def test_bool_print(self):
        output = compile_and_run("(program t (var ((flag bool))) (begin (:= flag true) (print flag)))")
        self.assertEqual(output, "true")

    def test_function_call(self):
        source = """(program t (var ((x int)))
          (begin
            (function add ((a int) (b int)) int (return (+ a b)))
            (:= x (add 4 5))
            (print x)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "9")


class TestControlFlow(unittest.TestCase):
    """Test if and while."""

    def test_if_true(self):
        source = """(program t (var ((x int) (y int)))
          (begin (:= x 10)
               (if (> x 5) (:= y 1) (:= y 0))
               (print y)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "1")

    def test_if_false(self):
        source = """(program t (var ((x int) (y int)))
          (begin (:= x 3)
               (if (> x 5) (:= y 1) (:= y 0))
               (print y)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "0")

    def test_while_loop(self):
        source = """(program t (var ((i int) (sum int)))
          (begin (:= i 0) (:= sum 0)
               (while (<= i 5)
                 (begin (:= sum (+ sum i)) (:= i (+ i 1))))
               (print sum)))"""
        output = compile_and_run(source)
        # 0+1+2+3+4+5 = 15
        self.assertEqual(output, "15")

    def test_while_zero_iterations(self):
        source = """(program t (var ((i int) (sum int)))
          (begin (:= i 10) (:= sum 0)
               (while (< i 5)
                 (begin (:= sum (+ sum i)) (:= i (+ i 1))))
               (print sum)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "0")

    def test_nested_while(self):
        source = """(program t (var ((i int) (j int) (total int)))
          (begin (:= i 0) (:= total 0)
               (while (< i 3)
                 (begin (:= j 0)
                      (while (< j 2)
                        (begin (:= total (+ total 1)) (:= j (+ j 1))))
                      (:= i (+ i 1))))
               (print total)))"""
        output = compile_and_run(source)
        # 3 * 2 = 6
        self.assertEqual(output, "6")


class TestComparisonOps(unittest.TestCase):
    """Test all comparison operators."""

    def test_lt(self):
        source = "(program t (var ((x int))) (begin (if (< 1 2) (:= x 1) (:= x 0)) (print x)))"
        self.assertEqual(compile_and_run(source), "1")

    def test_gt(self):
        source = "(program t (var ((x int))) (begin (if (> 2 1) (:= x 1) (:= x 0)) (print x)))"
        self.assertEqual(compile_and_run(source), "1")

    def test_eq(self):
        source = "(program t (var ((x int))) (begin (if (= 5 5) (:= x 1) (:= x 0)) (print x)))"
        self.assertEqual(compile_and_run(source), "1")

    def test_neq(self):
        source = "(program t (var ((x int))) (begin (if (!= 5 3) (:= x 1) (:= x 0)) (print x)))"
        self.assertEqual(compile_and_run(source), "1")

    def test_le(self):
        source = "(program t (var ((x int))) (begin (if (<= 5 5) (:= x 1) (:= x 0)) (print x)))"
        self.assertEqual(compile_and_run(source), "1")

    def test_ge(self):
        source = "(program t (var ((x int))) (begin (if (>= 5 3) (:= x 1) (:= x 0)) (print x)))"
        self.assertEqual(compile_and_run(source), "1")


class TestIntegrationPrograms(unittest.TestCase):
    """Test complete programs."""

    def test_demo_program(self):
        source = """(program example
          (var ((a int) (b int)))
          (begin
            (:= a 2)
            (:= b (+ (* 5 a) 2))
            (print b)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "12")

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
        output = compile_and_run(source)
        lines = output.split("\n")
        # First two: 0, 1, then 10 more fibonacci numbers
        self.assertEqual(lines[0], "0")
        self.assertEqual(lines[1], "1")
        self.assertEqual(lines[2], "1")
        self.assertEqual(lines[3], "2")
        self.assertEqual(lines[4], "3")
        self.assertEqual(lines[5], "5")
        self.assertEqual(lines[6], "8")
        self.assertEqual(lines[7], "13")
        self.assertEqual(lines[8], "21")
        self.assertEqual(lines[9], "34")
        self.assertEqual(lines[10], "55")
        self.assertEqual(lines[11], "89")

    def test_factorial_loop(self):
        source = """(program factorial
          (var ((n int) (result int) (i int)))
          (begin
            (:= n 6)
            (:= result 1)
            (:= i 1)
            (while (<= i n)
              (begin
                (:= result (* result i))
                (:= i (+ i 1))))
            (print result)))"""
        output = compile_and_run(source)
        # 6! = 720
        self.assertEqual(output, "720")

    def test_max_of_two(self):
        source = """(program max
          (var ((a int) (b int) (result int)))
          (begin
            (:= a 15)
            (:= b 23)
            (if (> a b)
              (:= result a)
              (:= result b))
            (print result)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "23")


if __name__ == "__main__":
    unittest.main()
