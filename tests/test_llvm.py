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
    return compile_and_run_with_args(source)


def compile_and_run_process(
    source: str, args: list[str] | None = None, stdin_data: str | None = None
) -> subprocess.CompletedProcess:
    """Compile NekoLang source to executable, run it, return the process result."""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    parser.set_source(source)
    ast = parser.parse()

    analyzer = SemanticAnalyzer()
    analyzer.set_source(source)
    analyzer.analyze(ast)

    codegen = LLVMCodegen()
    ir_text = codegen.generate(ast)

    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runtime_c = os.path.join(script_dir, "runtime", "runtime.c")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ll", delete=False) as f:
        f.write(ir_text)
        ll_path = f.name

    out_path = ll_path.replace(".ll", "")

    try:
        result = subprocess.run(
            ["clang", runtime_c, ll_path, "-o", out_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"clang failed:\n{result.stderr}")

        return subprocess.run(
            [out_path, *(args or [])],
            input=stdin_data,
            capture_output=True,
            text=True,
        )
    finally:
        os.unlink(ll_path)
        if os.path.exists(out_path):
            os.unlink(out_path)


def compile_and_run_with_args(source: str, args: list[str] | None = None) -> str:
    """Compile NekoLang source to executable, run it, return stdout."""
    return compile_and_run_process(source, args=args).stdout.strip()


def compile_and_run_with_input(source: str, stdin_data: str) -> str:
    return compile_and_run_process(source, stdin_data=stdin_data).stdout.strip()


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

    def test_string_print_call(self):
        ir = generate_ir('(program t (begin (print "你好")))')
        self.assertIn('declare void @"nekoprint_string"', ir)
        self.assertIn('call void @"nekoprint_string"', ir)

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

    def test_runtime_declarations(self):
        ir = generate_ir(
            '(program t (var ((x int))) (begin (:= x (argc)) (:= x (read-int "a.txt"))))'
        )
        self.assertIn('declare i32 @"neko_argv_int"', ir)
        self.assertIn('declare i32 @"neko_read_int"', ir)
        self.assertIn('define i32 @"main"(i32 %"argc"', ir)

    def test_input_runtime_declarations(self):
        ir = generate_ir("(program t (var ((x int))) (begin (:= x (input-int))))")
        self.assertIn('declare i32 @"neko_input_int"', ir)
        self.assertIn('call i32 @"neko_input_int"', ir)

    def test_random_runtime_declarations(self):
        ir = generate_ir("(program t (var ((x int))) (begin (rand-seed 7) (:= x (rand-range 1 6))))")
        self.assertIn('declare void @"neko_rand_seed"', ir)
        self.assertIn('declare i32 @"neko_rand_range"', ir)
        self.assertIn('call void @"neko_rand_seed"', ir)
        self.assertIn('call i32 @"neko_rand_range"', ir)


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

    def test_argc_and_argv(self):
        source = """(program t (var ((count int) (value int)))
          (begin
            (:= count (argc))
            (:= value (argv-int 0))
            (print count)
            (print value)))"""
        output = compile_and_run_with_args(source, ["7"])
        self.assertEqual(output, "1\n7")

    def test_file_read_and_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "input.txt")
            output_path = os.path.join(tmpdir, "output.txt")
            with open(input_path, "w", encoding="utf-8") as f:
                f.write("21\n")

            source = f"""(program t (var ((value int)))
              (begin
                (:= value (read-int "{input_path}"))
                (:= value (+ value 1))
                (write-int "{output_path}" value)
                (print value)))"""
            output = compile_and_run(source)
            self.assertEqual(output, "22")
            with open(output_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read().strip(), "22")

    def test_guess_number_demo_with_multiple_args(self):
        source = """(program guess_number
          (var ((count int) (index int) (guess int) (secret int) (solved int)))
          (begin
            (:= count (argc))
            (:= index 0)
            (:= secret 42)
            (:= solved 0)
            (while (< index count)
              (begin
                (if (= solved 0)
                  (begin
                    (:= guess (argv-int index))
                    (if (< guess secret)
                      (print 1)
                      (if (> guess secret)
                        (print 2)
                        (begin
                          (print 0)
                          (:= solved 1)))))
                  (:= solved solved))
                (:= index (+ index 1))))
            (print solved)))"""
        output = compile_and_run_with_args(source, ["30", "50", "42", "99"])
        self.assertEqual(output, "1\n2\n0\n1")

    def test_input_int(self):
        output = compile_and_run_with_input(
            "(program t (var ((x int))) (begin (:= x (input-int)) (print x)))",
            "7\n",
        )
        self.assertEqual(output, "7")

    def test_input_float(self):
        output = compile_and_run_with_input(
            "(program t (var ((x float))) (begin (:= x (input-float)) (print x)))",
            "3.5\n",
        )
        self.assertEqual(output, "3.500000")

    def test_input_bool(self):
        output = compile_and_run_with_input(
            "(program t (var ((x bool))) (begin (:= x (input-bool)) (print x)))",
            "true\n",
        )
        self.assertEqual(output, "true")

    def test_input_char(self):
        output = compile_and_run_with_input(
            "(program t (var ((x char))) (begin (:= x (input-char)) (print x)))",
            "x\n",
        )
        self.assertEqual(output, "x")

    def test_print_string_literal(self):
        output = compile_and_run('(program t (begin (print "猜大了")))')
        self.assertEqual(output, "猜大了")

    def test_multiple_input_tokens(self):
        output = compile_and_run_with_input(
            "(program t (var ((a int) (b int))) (begin (:= a (input-int)) (:= b (input-int)) (print a) (print b)))",
            "10 20\n",
        )
        self.assertEqual(output, "10\n20")

    def test_input_eof_error(self):
        result = compile_and_run_process(
            "(program t (var ((x int))) (begin (:= x (input-int)) (print x)))",
            stdin_data="",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("runtime error: stdin reached EOF", result.stderr)

    def test_input_bool_parse_error(self):
        result = compile_and_run_process(
            "(program t (var ((x bool))) (begin (:= x (input-bool)) (print x)))",
            stdin_data="maybe\n",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("runtime error: input-bool parse failed: maybe", result.stderr)

    def test_input_int_parse_error(self):
        result = compile_and_run_process(
            "(program t (var ((x int))) (begin (:= x (input-int)) (print x)))",
            stdin_data="cat\n",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("runtime error: input-int parse failed: cat", result.stderr)

    def test_input_float_parse_error(self):
        result = compile_and_run_process(
            "(program t (var ((x float))) (begin (:= x (input-float)) (print x)))",
            stdin_data="bird\n",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("runtime error: input-float parse failed: bird", result.stderr)

    def test_rand_range_with_seed_is_repeatable(self):
        source = """(program t (var ((a int) (b int)))
          (begin
            (rand-seed 123)
            (:= a (rand-range 1 10))
            (rand-seed 123)
            (:= b (rand-range 1 10))
            (print a)
            (print b)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "9\n9")

    def test_rand_range_stays_in_bounds(self):
        source = """(program t (var ((x int)))
          (begin
            (rand-seed 5)
            (:= x (rand-range 3 7))
            (print x)))"""
        output = compile_and_run(source)
        value = int(output)
        self.assertGreaterEqual(value, 3)
        self.assertLessEqual(value, 7)

    def test_rand_range_invalid_bounds(self):
        result = compile_and_run_process(
            "(program t (var ((x int))) (begin (:= x (rand-range 5 3)) (print x)))"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("runtime error: rand-range invalid bounds", result.stderr)


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
