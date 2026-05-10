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
        ir = generate_ir("(nya t (paw (purr 0)))")
        self.assertIn('"main"', ir)
        self.assertIn("ret i32 0", ir)
        self.assertIn("declare", ir)  # runtime declarations

    def test_variable_alloca(self):
        ir = generate_ir("(nya t (nyan ((x int))) (paw (meow x 1)))")
        self.assertIn("alloca i32", ir)
        self.assertIn("store i32 1", ir)

    def test_arithmetic_ops(self):
        ir = generate_ir("(nya t (nyan ((x int))) (paw (meow x (+ 1 2))))")
        self.assertIn("add i32", ir)

    def test_mul_div(self):
        ir = generate_ir("(nya t (nyan ((x int))) (paw (meow x (* 3 4))))")
        self.assertIn("mul i32", ir)

    def test_comparison(self):
        ir = generate_ir("(nya t (nyan ((x int))) (paw (if-nya (> x 0) (meow x 1) (meow x 0))))")
        self.assertIn("icmp", ir)
        self.assertIn("br i1", ir)

    def test_if_blocks(self):
        ir = generate_ir("(nya t (nyan ((x int))) (paw (if-nya (> x 0) (meow x 1) (meow x 0))))")
        self.assertIn("if.then", ir)
        self.assertIn("if.else", ir)
        self.assertIn("if.end", ir)

    def test_while_blocks(self):
        ir = generate_ir("(nya t (nyan ((i int))) (paw (purr-while (< i 10) (meow i (+ i 1)))))")
        self.assertIn("while.cond", ir)
        self.assertIn("while.body", ir)
        self.assertIn("while.end", ir)

    def test_float_type(self):
        ir = generate_ir("(nya t (nyan ((x float))) (paw (meow x 3.14)))")
        self.assertIn("double", ir)

    def test_print_call(self):
        ir = generate_ir("(nya t (nyan ((x int))) (paw (meow x 42) (purr x)))")
        self.assertIn('call void @"nekoprint_int"', ir)

    def test_printf_declared(self):
        ir = generate_ir("(nya t (paw (purr 0)))")
        self.assertIn('declare i32 @"printf"', ir)
        self.assertIn('declare void @"nekoprint_int"', ir)

    def test_array_gep(self):
        ir = generate_ir("(nya t (nyan ((arr (litter-box int 5)))) (paw (meow-arr arr 0 42)))")
        self.assertIn("getelementptr", ir)


class TestBasicExecution(unittest.TestCase):
    """Test compiled programs produce correct output."""

    def test_print_literal(self):
        output = compile_and_run("(nya t (paw (purr 42)))")
        self.assertEqual(output, "42")

    def test_variable_assign(self):
        output = compile_and_run("(nya t (nyan ((x int))) (paw (meow x 99) (purr x)))")
        self.assertEqual(output, "99")

    def test_addition(self):
        output = compile_and_run("(nya t (nyan ((x int))) (paw (meow x (+ 3 4)) (purr x)))")
        self.assertEqual(output, "7")

    def test_subtraction(self):
        output = compile_and_run("(nya t (nyan ((x int))) (paw (meow x (- 10 3)) (purr x)))")
        self.assertEqual(output, "7")

    def test_multiplication(self):
        output = compile_and_run("(nya t (nyan ((x int))) (paw (meow x (* 3 4)) (purr x)))")
        self.assertEqual(output, "12")

    def test_division(self):
        output = compile_and_run("(nya t (nyan ((x int))) (paw (meow x (/ 15 4)) (purr x)))")
        self.assertEqual(output, "3")

    def test_nested_arithmetic(self):
        output = compile_and_run("(nya t (nyan ((x int))) (paw (meow x (+ (* 5 2) 3)) (purr x)))")
        self.assertEqual(output, "13")

    def test_multiple_variables(self):
        source = """(nya t (nyan ((a int) (b int)))
          (paw (meow a 10) (meow b 20) (purr (+ a b))))"""
        output = compile_and_run(source)
        self.assertEqual(output, "30")


class TestControlFlow(unittest.TestCase):
    """Test if-nya and purr-while."""

    def test_if_true(self):
        source = """(nya t (nyan ((x int) (y int)))
          (paw (meow x 10)
               (if-nya (> x 5) (meow y 1) (meow y 0))
               (purr y)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "1")

    def test_if_false(self):
        source = """(nya t (nyan ((x int) (y int)))
          (paw (meow x 3)
               (if-nya (> x 5) (meow y 1) (meow y 0))
               (purr y)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "0")

    def test_while_loop(self):
        source = """(nya t (nyan ((i int) (sum int)))
          (paw (meow i 0) (meow sum 0)
               (purr-while (<= i 5)
                 (paw (meow sum (+ sum i)) (meow i (+ i 1))))
               (purr sum)))"""
        output = compile_and_run(source)
        # 0+1+2+3+4+5 = 15
        self.assertEqual(output, "15")

    def test_while_zero_iterations(self):
        source = """(nya t (nyan ((i int) (sum int)))
          (paw (meow i 10) (meow sum 0)
               (purr-while (< i 5)
                 (paw (meow sum (+ sum i)) (meow i (+ i 1))))
               (purr sum)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "0")

    def test_nested_while(self):
        source = """(nya t (nyan ((i int) (j int) (total int)))
          (paw (meow i 0) (meow total 0)
               (purr-while (< i 3)
                 (paw (meow j 0)
                      (purr-while (< j 2)
                        (paw (meow total (+ total 1)) (meow j (+ j 1))))
                      (meow i (+ i 1))))
               (purr total)))"""
        output = compile_and_run(source)
        # 3 * 2 = 6
        self.assertEqual(output, "6")


class TestComparisonOps(unittest.TestCase):
    """Test all comparison operators."""

    def test_lt(self):
        source = "(nya t (nyan ((x int))) (paw (if-nya (< 1 2) (meow x 1) (meow x 0)) (purr x)))"
        self.assertEqual(compile_and_run(source), "1")

    def test_gt(self):
        source = "(nya t (nyan ((x int))) (paw (if-nya (> 2 1) (meow x 1) (meow x 0)) (purr x)))"
        self.assertEqual(compile_and_run(source), "1")

    def test_eq(self):
        source = "(nya t (nyan ((x int))) (paw (if-nya (= 5 5) (meow x 1) (meow x 0)) (purr x)))"
        self.assertEqual(compile_and_run(source), "1")

    def test_neq(self):
        source = "(nya t (nyan ((x int))) (paw (if-nya (!= 5 3) (meow x 1) (meow x 0)) (purr x)))"
        self.assertEqual(compile_and_run(source), "1")

    def test_le(self):
        source = "(nya t (nyan ((x int))) (paw (if-nya (<= 5 5) (meow x 1) (meow x 0)) (purr x)))"
        self.assertEqual(compile_and_run(source), "1")

    def test_ge(self):
        source = "(nya t (nyan ((x int))) (paw (if-nya (>= 5 3) (meow x 1) (meow x 0)) (purr x)))"
        self.assertEqual(compile_and_run(source), "1")


class TestIntegrationPrograms(unittest.TestCase):
    """Test complete programs."""

    def test_demo_program(self):
        source = """(nya example
          (nyan ((a int) (b int)))
          (paw
            (meow a 2)
            (meow b (+ (* 5 a) 2))
            (purr b)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "12")

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
        source = """(nya factorial
          (nyan ((n int) (result int) (i int)))
          (paw
            (meow n 6)
            (meow result 1)
            (meow i 1)
            (purr-while (<= i n)
              (paw
                (meow result (* result i))
                (meow i (+ i 1))))
            (purr result)))"""
        output = compile_and_run(source)
        # 6! = 720
        self.assertEqual(output, "720")

    def test_max_of_two(self):
        source = """(nya max
          (nyan ((a int) (b int) (result int)))
          (paw
            (meow a 15)
            (meow b 23)
            (if-nya (> a b)
              (meow result a)
              (meow result b))
            (purr result)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "23")


if __name__ == "__main__":
    unittest.main()
