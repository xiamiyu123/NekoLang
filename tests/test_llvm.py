"""Tests for NekoLang LLVM backend - compile and run programs."""

import os
import shutil
import subprocess
import tempfile
import unittest

from neko.codegen_llvm import LLVMCodegen
from neko.lexer import Lexer
from neko.parser import Parser
import pytest
from tests._codegen_support import (
    compile_and_run as _compile_and_run,
    compile_and_run_process as _compile_and_run_process,
    compile_and_run_with_args as _compile_and_run_with_args,
    compile_and_run_with_input as _compile_and_run_with_input,
    generate_ir_text,
)


def compile_and_run(source: str) -> str:
    return _compile_and_run(source, backend="llvm")


def compile_and_run_process(
    source: str, args: list[str] | None = None, stdin_data: str | None = None
) -> subprocess.CompletedProcess:
    return _compile_and_run_process(source, backend="llvm", args=args, stdin_data=stdin_data)


def compile_and_run_with_args(source: str, args: list[str] | None = None) -> str:
    return _compile_and_run_with_args(source, args=args, backend="llvm")


def compile_and_run_with_input(source: str, stdin_data: str) -> str:
    return _compile_and_run_with_input(source, stdin_data=stdin_data, backend="llvm")


def generate_ir(source: str) -> str:
    return generate_ir_text(source)


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
        self.assertIn('define i32 @"neko_fn_add"', ir)
        self.assertIn("ret i32", ir)

    def test_hyphenated_function_name_ir(self):
        ir = generate_ir(
            "(program t (var ((x int))) "
            "(begin (function double-it ((a int)) int (return (* a 2))) "
            "(:= x (double-it 7))))"
        )
        self.assertIn('define i32 @"neko_fn_double_x002d_it"', ir)
        self.assertIn('call i32 @"neko_fn_double_x002d_it"', ir)

    def test_extern_declaration_ir(self):
        ir = generate_ir('(program t (var ((x int))) (begin (extern atoi (string) int) (:= x (atoi "42"))))')
        self.assertIn('declare i32 @"atoi"', ir)
        self.assertNotIn('define i32 @"atoi"', ir)

    def test_extern_pointer_declaration_ir(self):
        ir = generate_ir(
            '(program t (var ((p pointer))) (begin (extern malloc (int) pointer) (:= p (malloc 8))))'
        )
        self.assertIn('declare i8* @"malloc"(i32', ir)

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


@pytest.mark.slow
class TestBasicExecution(unittest.TestCase):
    """Test compiled programs produce correct output."""

    def test_basic_scalar_execution(self):
        source = """(program t (var ((x int) (a int) (b int) (flag bool)))
          (begin
            (print 42)
            (:= x 42)
            (meow x)
            (:= x 99)
            (print x)
            (:= x (+ 3 4))
            (print x)
            (:= x (- 10 3))
            (print x)
            (:= x (* 3 4))
            (print x)
            (:= x (/ 15 4))
            (print x)
            (:= x (+ (* 5 2) 3))
            (print x)
            (:= a 10)
            (:= b 20)
            (print (+ a b))
            (:= flag true)
            (print flag)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "42\n42\n99\n7\n7\n12\n3\n13\n30\ntrue")

    def test_function_call(self):
        source = """(program t (var ((x int)))
          (begin
            (function add ((a int) (b int)) int (return (+ a b)))
            (:= x (add 4 5))
            (print x)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "9")

    def test_nested_function_calls_as_arguments(self):
        source = """(program t (var ((x int)))
          (begin
            (function inc ((n int)) int (return (+ n 1)))
            (function add2 ((a int) (b int)) int (return (+ a b)))
            (:= x (add2 (inc 10) (inc 20)))
            (print x)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "32")

    def test_hyphenated_function_call(self):
        source = """(program t (var ((x int)))
          (begin
            (function double-it ((a int)) int (return (* a 2)))
            (:= x (double-it 7))
            (print x)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "14")

    def test_argc_and_argv(self):
        source = """(program t (var ((count int) (value int)))
          (begin
            (:= count (argc))
            (:= value (argv-int 0))
            (print count)
            (print value)))"""
        output = compile_and_run_with_args(source, ["7"])
        self.assertEqual(output, "1\n7")

    def test_extern_atoi(self):
        output = compile_and_run(
            '(program t (var ((x int))) (begin (extern atoi (string) int) (:= x (atoi "42")) (print x)))'
        )
        self.assertEqual(output, "42")

    def test_extern_atof(self):
        output = compile_and_run(
            '(program t (var ((x float))) (begin (extern atof (string) float) (:= x (atof "3.5")) (print x)))'
        )
        self.assertEqual(output, "3.500000")

    def test_extern_toupper(self):
        output = compile_and_run(
            "(program t (var ((x int))) (begin (extern toupper (int) int) (:= x (toupper 97)) (print x)))"
        )
        self.assertEqual(output, "65")

    def test_extern_as_function_value(self):
        output = compile_and_run(
            '(program t (var ((f (func (string) int)) (x int))) '
            '(begin (extern atoi (string) int) (:= f atoi) (:= x (f "42")) (print x)))'
        )
        self.assertEqual(output, "42")

    def test_extern_pointer_round_trip(self):
        output = compile_and_run(
            '(program t (var ((p pointer) (same bool))) '
            '(begin '
            '(extern malloc (int) pointer) '
            '(:= p (malloc 8)) '
            '(:= same (!= p 0)) '
            '(print same)))'
        )
        self.assertEqual(output, "true")

    def test_pointer_zero_round_trip(self):
        output = compile_and_run(
            '(program t (var ((p pointer) (same bool))) '
            '(begin '
            '(:= p 0) '
            '(:= same (= p 0)) '
            '(print same)))'
        )
        self.assertEqual(output, "true")

    def test_pointer_print_uses_pointer_runtime(self):
        ir = generate_ir('(program t (var ((p pointer))) (begin (:= p 0) (print p)))')
        self.assertIn('declare void @"nekoprint_pointer"', ir)
        self.assertIn('call void @"nekoprint_pointer"', ir)

    def test_pointer_rejects_nonzero_int_comparison_at_codegen(self):
        source = (
            '(program t (var ((p pointer))) '
            '(begin (extern malloc (int) pointer) (:= p (malloc 8)) (print (!= p 7))))'
        )
        parser = Parser(Lexer(source).tokenize())
        parser.set_source(source)
        ast = parser.parse()
        with self.assertRaisesRegex(RuntimeError, "pointer 仅支持从字面量 0 转换"):
            LLVMCodegen().generate(ast)

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

    def test_array_set_and_print(self):
        source = """(program t
          (var ((arr (array int 4))))
          (begin
            (array-set arr 0 42)
            (array-set arr 1 7)
            (array-print arr 0)
            (array-print arr 1)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "42\n7")

    def test_char_array_uses_byte_stride(self):
        source = """(program t
          (var ((arr (array char 3))))
          (begin
            (array-set arr 0 'A')
            (array-set arr 1 'B')
            (array-set arr 2 'C')
            (array-print arr 0)
            (array-print arr 1)
            (array-print arr 2)))"""
        result = compile_and_run_process(source)
        self.assertEqual(result.stdout, "A\nB\nC\n")

    def test_if_branch_can_return_without_breaking_fallthrough(self):
        source = """(program t
          (var ((result int)))
          (begin
            (function pick ((x int)) int
              (begin
                (if (> x 0)
                  (:= x 1)
                  (return 9))
                (return x)))
            (:= result (pick 1))
            (print result)
            (:= result (pick 0))
            (print result)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "1\n9")

    def test_direct_call_supports_eight_int_and_eight_float_args(self):
        source = """(program t
          (var ((result int)))
          (begin
            (function pick ((i0 int) (i1 int) (i2 int) (i3 int)
                            (i4 int) (i5 int) (i6 int) (i7 int)
                            (f0 float) (f1 float) (f2 float) (f3 float)
                            (f4 float) (f5 float) (f6 float) (f7 float)) int
              (return i7))
            (:= result (pick 0 1 2 3 4 5 6 7 1.0 2.0 3.0 4.0 5.0 6.0 7.0 8.0))
            (print result)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "7")

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


@pytest.mark.slow
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


@pytest.mark.slow
class TestComparisonOps(unittest.TestCase):
    """Test all comparison operators."""

    def test_comparison_operators(self):
        source = """(program t (var ((x int)))
          (begin
            (if (< 1 2) (:= x 1) (:= x 0))
            (print x)
            (if (> 2 1) (:= x 1) (:= x 0))
            (print x)
            (if (= 5 5) (:= x 1) (:= x 0))
            (print x)
            (if (!= 5 3) (:= x 1) (:= x 0))
            (print x)
            (if (<= 5 5) (:= x 1) (:= x 0))
            (print x)
            (if (>= 5 3) (:= x 1) (:= x 0))
            (print x)))"""
        self.assertEqual(compile_and_run(source), "1\n1\n1\n1\n1\n1")


@pytest.mark.slow
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


@pytest.mark.slow
class TestStringOperations(unittest.TestCase):
    """Test string type and operations."""

    def test_string_variable(self):
        source = """(program t
          (var ((s string)))
          (begin
            (:= s "Hello, Neko!")
            (print s)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "Hello, Neko!")

    def test_string_concat(self):
        source = """(program t
          (var ((s string)))
          (begin
            (:= s (+ "Hello, " "World"))
            (print s)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "Hello, World")

    def test_string_length(self):
        source = """(program t
          (var ((n int)))
          (begin
            (:= n (string-length "hello"))
            (print n)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "5")

    def test_string_at(self):
        source = """(program t
          (var ((c char)))
          (begin
            (:= c (string-at "hello" 1))
            (print c)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "e")

    def test_string_sub(self):
        source = """(program t
          (var ((s string)))
          (begin
            (:= s (string-sub "hello world" 6 5))
            (print s)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "world")

    def test_string_cmp_equal(self):
        source = """(program t
          (var ((n int)))
          (begin
            (:= n (string-cmp "abc" "abc"))
            (print n)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "0")

    def test_string_cmp_not_equal(self):
        source = """(program t
          (var ((n int) (result int)))
          (begin
            (:= n (string-cmp "abc" "def"))
            (if (< n 0)
              (:= result 1)
              (:= result 0))
            (print result)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "1")

    def test_string_contains(self):
        source = """(program t
          (var ((b bool)))
          (begin
            (:= b (string-contains "hello world" "world"))
            (print b)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "true")

    def test_string_contains_false(self):
        source = """(program t
          (var ((b bool)))
          (begin
            (:= b (string-contains "hello" "xyz"))
            (print b)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "false")

    def test_int_to_string(self):
        source = """(program t
          (var ((s string)))
          (begin
            (:= s (int-to-string 42))
            (print s)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "42")

    def test_string_to_int(self):
        source = """(program t
          (var ((n int)))
          (begin
            (:= n (string-to-int "123"))
            (print n)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "123")

    def test_string_concat_with_int_to_string(self):
        source = """(program t
          (var ((s string) (n int)))
          (begin
            (:= n 42)
            (:= s (+ "value=" (int-to-string n)))
            (print s)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "value=42")

    def test_string_eq(self):
        source = """(program t
          (var ((b bool)))
          (begin
            (:= b (= "abc" "abc"))
            (print b)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "true")

    def test_string_neq(self):
        source = """(program t
          (var ((b bool)))
          (begin
            (:= b (!= "abc" "def"))
            (print b)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "true")

    def test_string_eq_compares_contents(self):
        source = """(program t
          (var ((b bool) (s string)))
          (begin
            (:= s (+ "a" "b"))
            (:= b (= s "ab"))
            (print b)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "true")

    def test_string_neq_compares_contents(self):
        source = """(program t
          (var ((b bool) (s string)))
          (begin
            (:= s (+ "a" "b"))
            (:= b (!= s "ab"))
            (print b)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "false")

    def test_empty_string_length(self):
        """Empty string length should be 0."""
        source = """(program t (var ((n int))) (begin
            (:= n (string-length ""))
            (print n)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "0")

    def test_empty_string_concat(self):
        """Empty string concat should work."""
        source = """(program t (var ((s string))) (begin
            (:= s (+ "" "hello"))
            (print s)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "hello")

    def test_string_sub_zero_length(self):
        """String sub with zero length should return empty string."""
        source = """(program t (var ((s string))) (begin
            (:= s (string-sub "hello" 0 0))
            (print s)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "")

    def test_string_sub_full_length(self):
        """String sub with full length should return whole string."""
        source = """(program t (var ((s string))) (begin
            (:= s (string-sub "hello" 0 5))
            (print s)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "hello")

    def test_string_sub_middle(self):
        """String sub from middle should work."""
        source = """(program t (var ((s string))) (begin
            (:= s (string-sub "hello world" 6 5))
            (print s)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "world")

    def test_int_to_string_negative(self):
        """Int-to-string with negative number should work."""
        source = """(program t (var ((s string))) (begin
            (:= s (int-to-string (- 0 42)))
            (print s)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "-42")

    def test_int_to_string_zero(self):
        """Int-to-string with zero should work."""
        source = """(program t (var ((s string))) (begin
            (:= s (int-to-string 0))
            (print s)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "0")

    def test_string_to_int_zero(self):
        """String-to-int with "0" should work."""
        source = """(program t (var ((n int))) (begin
            (:= n (string-to-int "0"))
            (print n)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "0")

    def test_string_to_int_negative(self):
        """String-to-int with negative number should work."""
        source = """(program t (var ((n int))) (begin
            (:= n (string-to-int "-42"))
            (print n)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "-42")

    def test_empty_string_contains(self):
        """Empty string contains empty string should be true."""
        source = """(program t (var ((b bool))) (begin
            (:= b (string-contains "" ""))
            (print b)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "true")

    def test_string_contains_self(self):
        """String contains itself should be true."""
        source = """(program t (var ((b bool))) (begin
            (:= b (string-contains "hello" "hello"))
            (print b)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "true")

    def test_string_cmp_empty_strings(self):
        """Comparing two empty strings should return 0."""
        source = """(program t (var ((n int))) (begin
            (:= n (string-cmp "" ""))
            (print n)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "0")

    def test_string_eq_empty_strings(self):
        """Two empty strings should be equal."""
        source = """(program t (var ((b bool))) (begin
            (:= b (= "" ""))
            (print b)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "true")

    def test_string_multiple_concat(self):
        """Multiple string concatenations should work."""
        source = """(program t (var ((s string))) (begin
            (:= s (+ (+ "a" "b") (+ "c" "d")))
            (print s)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "abcd")

    def test_string_at_first_char(self):
        """String-at at index 0 should return first char."""
        source = """(program t (var ((c char))) (begin
            (:= c (string-at "hello" 0))
            (print c)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "h")

    def test_string_at_last_char(self):
        """String-at at last index should return last char."""
        source = """(program t (var ((c char))) (begin
            (:= c (string-at "hello" 4))
            (print c)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "o")

    def test_string_unicode(self):
        """Unicode string should work."""
        source = """(program t (var ((s string))) (begin
            (:= s "你好世界")
            (print s)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "你好世界")


@pytest.mark.slow
class TestCharOperations(unittest.TestCase):
    """Test char literal and char operations."""

    def test_char_literal(self):
        source = """(program t
          (var ((c char)))
          (begin
            (:= c 'A')
            (print c)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "A")

    def test_char_escape_newline(self):
        source = r"""(program t
          (var ((c char)))
          (begin
            (:= c '\n')
            (print c)))"""
        # nekoprint_char prints "%c\n", so '\n' char produces two newlines
        result = compile_and_run_process(source)
        self.assertEqual(result.stdout, "\n\n")

    def test_char_to_int(self):
        source = """(program t
          (var ((n int)))
          (begin
            (:= n (char-to-int 'A'))
            (print n)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "65")

    def test_int_to_char(self):
        source = """(program t
          (var ((c char)))
          (begin
            (:= c (int-to-char 65))
            (print c)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "A")

    def test_char_to_string(self):
        source = """(program t
          (var ((s string)))
          (begin
            (:= s (char-to-string 'X'))
            (print s)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "X")

    def test_is_letter(self):
        source = """(program t
          (var ((a bool) (b bool)))
          (begin
            (:= a (is-letter 'a'))
            (:= b (is-letter '5'))
            (print a)
            (print b)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "true\nfalse")

    def test_is_digit(self):
        source = """(program t
          (var ((a bool) (b bool)))
          (begin
            (:= a (is-digit '5'))
            (:= b (is-digit 'a'))
            (print a)
            (print b)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "true\nfalse")

    def test_char_upcase(self):
        source = """(program t
          (var ((c char)))
          (begin
            (:= c (char-upcase 'a'))
            (print c)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "A")

    def test_char_downcase(self):
        source = """(program t
          (var ((c char)))
          (begin
            (:= c (char-downcase 'Z'))
            (print c)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "z")

    def test_char_implicit_to_int(self):
        """char can be used in int context."""
        source = """(program t
          (var ((n int)))
          (begin
            (:= n (char-to-int 'A'))
            (:= n (+ n 1))
            (print n)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "66")


@pytest.mark.slow
class TestLambda(unittest.TestCase):
    """Test lambda expressions and function pointers."""

    def test_lambda_basic(self):
        source = """(program t
          (var ((f (func (int) int)) (r int)))
          (begin
            (:= f (lambda ((x int)) int (return (* x 2))))
            (:= r (f 5))
            (print r)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "10")

    def test_lambda_two_params(self):
        source = """(program t
          (var ((f (func (int int) int)) (r int)))
          (begin
            (:= f (lambda ((a int) (b int)) int (return (+ a b))))
            (:= r (f 3 4))
            (print r)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "7")

    def test_lambda_as_argument(self):
        source = """(program t
          (var ((f (func (int) int)) (r int)))
          (begin
            (function apply ((g (func (int) int)) (x int)) int
              (return (g x)))
            (:= f (lambda ((n int)) int (return (* n 3))))
            (:= r (apply f 4))
            (print r)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "12")

    def test_named_function_as_value(self):
        source = """(program t
          (var ((f (func (int) int)) (r int)))
          (begin
            (function square ((n int)) int (return (* n n)))
            (:= f square)
            (:= r (f 6))
            (print r)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "36")

    def test_lambda_demo_example(self):
        source = """(program t
          (var ((double (func (int) int))
                (add (func (int int) int))
                (f (func (int) int))
                (result int)))
          (begin
            (:= double (lambda ((n int)) int (return (* n 2))))
            (function apply ((g (func (int) int)) (x int)) int
              (return (g x)))
            (function apply2 ((g (func (int int) int)) (a int) (b int)) int
              (return (g a b)))
            (function square ((n int)) int (return (* n n)))
            (:= result (apply double 5))
            (print result)
            (:= add (lambda ((a int) (b int)) int (return (+ a b))))
            (:= result (apply2 add 3 4))
            (print result)
            (:= f square)
            (:= result (apply f 6))
            (print result)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "10\n7\n36")


@pytest.mark.slow
class TestArrayEdgeCases(unittest.TestCase):
    """Edge case tests for array operations."""

    def test_array_first_element(self):
        """Array first element access should work."""
        source = """(program t (var ((arr (array int 5)))) (begin
            (array-set arr 0 42)
            (array-print arr 0)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "42")

    def test_array_last_element(self):
        """Array last element access should work."""
        source = """(program t (var ((arr (array int 5)))) (begin
            (array-set arr 4 99)
            (array-print arr 4)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "99")

    def test_array_all_elements(self):
        """All array elements should be accessible."""
        source = """(program t (var ((arr (array int 3)))) (begin
            (array-set arr 0 10)
            (array-set arr 1 20)
            (array-set arr 2 30)
            (array-print arr 0)
            (array-print arr 1)
            (array-print arr 2)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "10\n20\n30")

    def test_array_overwrite_element(self):
        """Overwriting array element should work."""
        source = """(program t (var ((arr (array int 3)))) (begin
            (array-set arr 0 10)
            (array-set arr 0 99)
            (array-print arr 0)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "99")

    def test_array_with_expression_index(self):
        """Array with expression index should work."""
        source = """(program t (var ((arr (array int 5)) (i int))) (begin
            (:= i 2)
            (array-set arr i 42)
            (array-print arr 2)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "42")

    def test_array_with_expression_value(self):
        """Array with expression value should work."""
        source = """(program t (var ((arr (array int 3)))) (begin
            (array-set arr 0 (+ 10 20))
            (array-print arr 0)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "30")

    def test_array_with_nested_call_value(self):
        """Array element assignment should survive nested calls in the value expression."""
        source = """(program t (var ((arr (array int 1)))) (begin
            (function inc ((n int)) int (return (+ n 1)))
            (array-set arr 0 (inc 41))
            (array-print arr 0)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "42")

    def test_float_array(self):
        """Float array should work."""
        source = """(program t (var ((arr (array float 3)))) (begin
            (array-set arr 0 1.5)
            (array-set arr 1 2.5)
            (array-set arr 2 3.5)
            (array-print arr 0)
            (array-print arr 1)
            (array-print arr 2)))"""
        output = compile_and_run(source)
        self.assertIn("1.5", output)
        self.assertIn("2.5", output)
        self.assertIn("3.5", output)

    def test_bool_array(self):
        """Bool array should work."""
        source = """(program t (var ((arr (array bool 3)))) (begin
            (array-set arr 0 true)
            (array-set arr 1 false)
            (array-set arr 2 true)
            (array-print arr 0)
            (array-print arr 1)
            (array-print arr 2)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "true\nfalse\ntrue")

    def test_char_array_operations(self):
        """Char array operations should work."""
        source = """(program t (var ((arr (array char 4)))) (begin
            (array-set arr 0 'H')
            (array-set arr 1 'i')
            (array-set arr 2 '!')
            (array-print arr 0)
            (array-print arr 1)
            (array-print arr 2)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "H\ni\n!")

    def test_single_element_array(self):
        """Single element array should work."""
        source = """(program t (var ((arr (array int 1)))) (begin
            (array-set arr 0 42)
            (array-print arr 0)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "42")

    def test_array_in_loop(self):
        """Array operations in loop should work."""
        source = """(program t (var ((arr (array int 5)) (i int))) (begin
            (:= i 0)
            (while (< i 5)
                (begin
                    (array-set arr i (* i 10))
                    (:= i (+ i 1))))
            (:= i 0)
            (while (< i 5)
                (begin
                    (array-print arr i)
                    (:= i (+ i 1))))))"""
        output = compile_and_run(source)
        self.assertEqual(output, "0\n10\n20\n30\n40")


@pytest.mark.slow
class TestFileIOEdgeCases(unittest.TestCase):
    """Edge case tests for file I/O operations."""

    def test_write_and_read_int(self):
        """Write and read int should work."""
        source = """(program t (var ((x int))) (begin
            (write-int "/tmp/neko_test_int.txt" 42)
            (:= x (read-int "/tmp/neko_test_int.txt"))
            (print x)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "42")

    def test_write_and_read_float(self):
        """Write and read float should work."""
        source = """(program t (var ((x float))) (begin
            (write-float "/tmp/neko_test_float.txt" 3.14)
            (:= x (read-float "/tmp/neko_test_float.txt"))
            (print x)))"""
        output = compile_and_run(source)
        self.assertIn("3.14", output)

    def test_write_and_read_char(self):
        """Write and read char should work."""
        source = """(program t (var ((c char))) (begin
            (write-char "/tmp/neko_test_char.txt" 'A')
            (:= c (read-char "/tmp/neko_test_char.txt"))
            (print c)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "A")

    def test_write_and_read_bool(self):
        """Write and read bool should work."""
        source = """(program t (var ((b bool))) (begin
            (write-bool "/tmp/neko_test_bool.txt" true)
            (:= b (read-bool "/tmp/neko_test_bool.txt"))
            (print b)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "true")

    def test_write_overwrites_file(self):
        """Write should overwrite existing file."""
        source = """(program t (var ((x int))) (begin
            (write-int "/tmp/neko_test_overwrite.txt" 100)
            (write-int "/tmp/neko_test_overwrite.txt" 200)
            (:= x (read-int "/tmp/neko_test_overwrite.txt"))
            (print x)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "200")

    def test_write_negative_int(self):
        """Writing negative int should work."""
        source = """(program t (var ((x int))) (begin
            (write-int "/tmp/neko_test_neg.txt" (- 0 42))
            (:= x (read-int "/tmp/neko_test_neg.txt"))
            (print x)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "-42")

    def test_write_zero_int(self):
        """Writing zero should work."""
        source = """(program t (var ((x int))) (begin
            (write-int "/tmp/neko_test_zero.txt" 0)
            (:= x (read-int "/tmp/neko_test_zero.txt"))
            (print x)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "0")

    def test_write_large_int(self):
        """Writing large int should work."""
        source = """(program t (var ((x int))) (begin
            (write-int "/tmp/neko_test_large.txt" 999999)
            (:= x (read-int "/tmp/neko_test_large.txt"))
            (print x)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "999999")

    def test_write_negative_float(self):
        """Writing negative float should work."""
        source = """(program t (var ((x float))) (begin
            (write-float "/tmp/neko_test_negf.txt" (- 0.0 3.14))
            (:= x (read-float "/tmp/neko_test_negf.txt"))
            (print x)))"""
        output = compile_and_run(source)
        self.assertIn("-3.14", output)


@pytest.mark.slow
class TestArgvEdgeCases(unittest.TestCase):
    """Edge case tests for argv operations."""

    def test_argv_int_basic(self):
        """argv-int should parse integer argument."""
        source = """(program t (var ((x int))) (begin
            (:= x (argv-int 0))
            (print x)))"""
        result = compile_and_run_process(source, args=["42"])
        self.assertEqual(result.stdout.strip(), "42")

    def test_argv_int_negative(self):
        """argv-int should parse negative integer argument."""
        source = """(program t (var ((x int))) (begin
            (:= x (argv-int 0))
            (print x)))"""
        result = compile_and_run_process(source, args=["-42"])
        self.assertEqual(result.stdout.strip(), "-42")

    def test_argv_int_zero(self):
        """argv-int should parse zero argument."""
        source = """(program t (var ((x int))) (begin
            (:= x (argv-int 0))
            (print x)))"""
        result = compile_and_run_process(source, args=["0"])
        self.assertEqual(result.stdout.strip(), "0")

    def test_argv_float_basic(self):
        """argv-float should parse float argument."""
        source = """(program t (var ((x float))) (begin
            (:= x (argv-float 0))
            (print x)))"""
        result = compile_and_run_process(source, args=["3.14"])
        self.assertIn("3.14", result.stdout)

    def test_argv_float_negative(self):
        """argv-float should parse negative float argument."""
        source = """(program t (var ((x float))) (begin
            (:= x (argv-float 0))
            (print x)))"""
        result = compile_and_run_process(source, args=["-3.14"])
        self.assertIn("-3.14", result.stdout)

    def test_argv_char_basic(self):
        """argv-char should parse char argument."""
        source = """(program t (var ((c char))) (begin
            (:= c (argv-char 0))
            (print c)))"""
        result = compile_and_run_process(source, args=["A"])
        self.assertEqual(result.stdout.strip(), "A")

    def test_argv_bool_basic(self):
        """argv-bool should parse bool argument."""
        source = """(program t (var ((b bool))) (begin
            (:= b (argv-bool 0))
            (print b)))"""
        result = compile_and_run_process(source, args=["true"])
        self.assertEqual(result.stdout.strip(), "true")

    def test_argv_string_basic(self):
        """argv-string should return string argument."""
        source = """(program t (var ((s string))) (begin
            (:= s (argv-string 0))
            (print s)))"""
        result = compile_and_run_process(source, args=["hello"])
        self.assertEqual(result.stdout.strip(), "hello")

    def test_argv_string_inside_extern_call(self):
        """argv-string should remain valid when passed into another extern call."""
        source = """(program t (var ((x int))) (begin
            (extern atoi (string) int)
            (:= x (atoi (argv-string 0)))
            (print x)))"""
        result = compile_and_run_process(source, args=["42"])
        self.assertEqual(result.stdout.strip(), "42")

    def test_argv_multiple_args(self):
        """Multiple argv access should work."""
        source = """(program t (var ((a int) (b int))) (begin
            (:= a (argv-int 0))
            (:= b (argv-int 1))
            (print (+ a b))))"""
        result = compile_and_run_process(source, args=["10", "20"])
        self.assertEqual(result.stdout.strip(), "30")

    def test_argc_with_args(self):
        """argc should return correct count."""
        source = """(program t (var ((n int))) (begin
            (:= n (argc))
            (print n)))"""
        result = compile_and_run_process(source, args=["a", "b", "c"])
        self.assertEqual(result.stdout.strip(), "3")

    def test_argc_without_args(self):
        """argc with no args should return 0."""
        source = """(program t (var ((n int))) (begin
            (:= n (argc))
            (print n)))"""
        result = compile_and_run_process(source, args=[])
        self.assertEqual(result.stdout.strip(), "0")

    def test_argv_loop_over_args(self):
        """Looping over argv should work."""
        source = """(program t (var ((n int) (i int))) (begin
            (:= n (argc))
            (:= i 0)
            (while (< i n)
                (begin
                    (print (argv-int i))
                    (:= i (+ i 1))))))"""
        result = compile_and_run_process(source, args=["10", "20", "30"])
        self.assertEqual(result.stdout.strip(), "10\n20\n30")

    def test_argv_with_no_args_access(self):
        """Accessing argv with no args should fail at runtime."""
        source = """(program t (var ((x int))) (begin
            (:= x (argv-int 0))
            (print x)))"""
        result = compile_and_run_process(source, args=[])
        self.assertNotEqual(result.returncode, 0)


@pytest.mark.slow
class TestInputEdgeCases(unittest.TestCase):
    """Edge case tests for input operations."""

    def test_input_int_negative(self):
        """Input negative int should work."""
        output = compile_and_run_with_input(
            "(program t (var ((x int))) (begin (:= x (input-int)) (print x)))",
            "-42\n",
        )
        self.assertEqual(output, "-42")

    def test_input_int_zero(self):
        """Input zero should work."""
        output = compile_and_run_with_input(
            "(program t (var ((x int))) (begin (:= x (input-int)) (print x)))",
            "0\n",
        )
        self.assertEqual(output, "0")

    def test_input_float_negative(self):
        """Input negative float should work."""
        output = compile_and_run_with_input(
            "(program t (var ((x float))) (begin (:= x (input-float)) (print x)))",
            "-3.5\n",
        )
        self.assertIn("-3.5", output)

    def test_input_float_zero(self):
        """Input zero float should work."""
        output = compile_and_run_with_input(
            "(program t (var ((x float))) (begin (:= x (input-float)) (print x)))",
            "0.0\n",
        )
        self.assertIn("0.0", output)

    def test_input_bool_false(self):
        """Input false should work."""
        output = compile_and_run_with_input(
            "(program t (var ((x bool))) (begin (:= x (input-bool)) (print x)))",
            "false\n",
        )
        self.assertEqual(output, "false")

    def test_input_multiple_values(self):
        """Multiple input values should work."""
        output = compile_and_run_with_input(
            "(program t (var ((a int) (b int))) (begin (:= a (input-int)) (:= b (input-int)) (print (+ a b))))",
            "10\n20\n",
        )
        self.assertEqual(output, "30")

    def test_input_mixed_types(self):
        """Mixed type inputs should work."""
        output = compile_and_run_with_input(
            "(program t (var ((a int) (b float) (c bool))) (begin (:= a (input-int)) (:= b (input-float)) (:= c (input-bool)) (print a) (print b) (print c)))",
            "42\n3.14\ntrue\n",
        )
        self.assertIn("42", output)
        self.assertIn("3.14", output)
        self.assertIn("true", output)


@pytest.mark.slow
class TestRandEdgeCases(unittest.TestCase):
    """Edge case tests for random number operations."""

    def test_rand_range_same_seed_same_result(self):
        """Same seed should produce same result."""
        source = """(program t (var ((x int) (y int))) (begin
            (rand-seed 42)
            (:= x (rand-range 1 100))
            (rand-seed 42)
            (:= y (rand-range 1 100))
            (if (= x y)
                (print true)
                (print false))))"""
        output = compile_and_run(source)
        self.assertEqual(output, "true")

    def test_rand_range_min_equals_max(self):
        """rand-range with min=max should return that value."""
        source = """(program t (var ((x int))) (begin
            (rand-seed 42)
            (:= x (rand-range 5 5))
            (print x)))"""
        output = compile_and_run(source)
        self.assertEqual(output, "5")

    def test_rand_range_small_range(self):
        """rand-range with small range should work."""
        source = """(program t (var ((x int))) (begin
            (rand-seed 42)
            (:= x (rand-range 1 2))
            (if (= x 1)
                (print true)
                (if (= x 2)
                    (print true)
                    (print false)))))"""
        output = compile_and_run(source)
        self.assertEqual(output, "true")

    def test_rand_range_multiple_calls(self):
        """Multiple rand-range calls should work."""
        source = """(program t (var ((x int) (i int))) (begin
            (rand-seed 42)
            (:= i 0)
            (while (< i 5)
                (begin
                    (:= x (rand-range 1 100))
                    (print x)
                    (:= i (+ i 1))))))"""
        result = compile_and_run_process(source)
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.strip().split("\n")
        self.assertEqual(len(lines), 5)


@pytest.mark.slow
class TestCodegenEdgeCases(unittest.TestCase):
    """Edge case tests for code generation stability."""

    def test_negative_number_printing(self):
        """Negative number should be printed correctly."""
        source = """(program t (begin
            (print (- 0 5))
        ))"""
        output = compile_and_run(source)
        self.assertEqual(output, "-5")

    def test_large_integer_arithmetic(self):
        """Large integer arithmetic should work."""
        source = """(program t (var ((x int))) (begin
            (:= x (+ 1000000 2000000))
            (print x)
        ))"""
        output = compile_and_run(source)
        self.assertEqual(output, "3000000")

    def test_integer_overflow_behavior(self):
        """Integer overflow wraps around in 32-bit arithmetic."""
        source = """(program t (var ((x int))) (begin
            (:= x (+ 2147483647 1))
            (print x)
        ))"""
        output = compile_and_run(source)
        # In 32-bit signed arithmetic, this wraps to -2147483648
        self.assertEqual(output, "-2147483648")

    def test_float_negative(self):
        """Negative float should be printed correctly."""
        source = """(program t (var ((x float))) (begin
            (:= x (- 0.0 3.14))
            (print x)
        ))"""
        output = compile_and_run(source)
        self.assertIn("-3.14", output)

    def test_float_zero(self):
        """Zero float should be printed correctly."""
        source = """(program t (var ((x float))) (begin
            (:= x 0.0)
            (print x)
        ))"""
        output = compile_and_run(source)
        self.assertIn("0.0", output)

    def test_float_large_value(self):
        """Large float should be printed correctly."""
        source = """(program t (var ((x float))) (begin
            (:= x 999999.999)
            (print x)
        ))"""
        output = compile_and_run(source)
        self.assertIn("999999.999", output)

    def test_float_small_value(self):
        """Small float should be printed correctly."""
        source = """(program t (var ((x float))) (begin
            (:= x 0.000001)
            (print x)
        ))"""
        output = compile_and_run(source)
        self.assertIn("0.000001", output)

    def test_deeply_nested_expression(self):
        """Deeply nested expression should evaluate correctly."""
        source = """(program t (var ((x int))) (begin
            (:= x (+ (+ (+ (+ 1 2) 3) 4) 5))
            (print x)
        ))"""
        output = compile_and_run(source)
        self.assertEqual(output, "15")

    def test_multiple_arithmetic_operations(self):
        """Multiple arithmetic operations should work correctly."""
        source = """(program t (var ((x int))) (begin
            (:= x (+ (* 2 3) (- 10 5)))
            (print x)
        ))"""
        output = compile_and_run(source)
        self.assertEqual(output, "11")

    def test_division_truncation(self):
        """Integer division should truncate towards zero."""
        source = """(program t (var ((x int))) (begin
            (:= x (/ 7 2))
            (print x)
        ))"""
        output = compile_and_run(source)
        self.assertEqual(output, "3")

    def test_multiple_subtractions(self):
        """Multiple subtractions should work correctly."""
        source = """(program t (var ((x int))) (begin
            (:= x (- (- 10 3) 2))
            (print x)
        ))"""
        output = compile_and_run(source)
        self.assertEqual(output, "5")

    def test_comparison_operators(self):
        """All comparison operators should work correctly."""
        source = """(program t (begin
            (print (> 5 3))
            (print (< 3 5))
            (print (= 5 5))
            (print (>= 5 5))
            (print (<= 5 5))
            (print (!= 5 3))
        ))"""
        output = compile_and_run(source)
        self.assertEqual(output, "true\ntrue\ntrue\ntrue\ntrue\ntrue")

    def test_comparison_in_if_condition(self):
        """Comparison in if condition should work."""
        source = """(program t (begin
            (if (> 5 3)
                (print true)
                (print false))
        ))"""
        output = compile_and_run(source)
        self.assertEqual(output, "true")

    def test_bool_print(self):
        """Boolean print should work correctly."""
        source = """(program t (var ((a bool))) (begin
            (:= a true)
            (print a)
        ))"""
        output = compile_and_run(source)
        self.assertEqual(output, "true")

    def test_bool_false_print(self):
        """Boolean false print should work correctly."""
        source = """(program t (var ((a bool))) (begin
            (:= a false)
            (print a)
        ))"""
        output = compile_and_run(source)
        self.assertEqual(output, "false")

    def test_int_to_float_conversion(self):
        """Int to float conversion should work in arithmetic."""
        source = """(program t (var ((x float))) (begin
            (:= x (+ 1 2.5))
            (print x)
        ))"""
        output = compile_and_run(source)
        self.assertIn("3.5", output)

    def test_mixed_int_float_arithmetic(self):
        """Mixed int/float arithmetic should work correctly."""
        source = """(program t (var ((x float))) (begin
            (:= x (* 2 3.14))
            (print x)
        ))"""
        output = compile_and_run(source)
        self.assertIn("6.28", output)

    def test_function_with_multiple_returns(self):
        """Function with multiple returns should work correctly."""
        source = """(program t (begin
            (function abs ((n int)) int
                (if (< n 0)
                    (return (- 0 n))
                    (return n)))
            (print (abs 5))
            (print (abs (- 0 5)))
        ))"""
        output = compile_and_run(source)
        self.assertEqual(output, "5\n5")

    def test_recursive_function_factorial(self):
        """Recursive factorial function should work correctly."""
        source = """(program t (begin
            (function factorial ((n int)) int
                (if (<= n 1)
                    (return 1)
                    (return (* n (factorial (- n 1))))))
            (print (factorial 5))
            (print (factorial 10))
        ))"""
        output = compile_and_run(source)
        self.assertEqual(output, "120\n3628800")

    def test_while_loop_with_counter(self):
        """While loop with counter should work correctly."""
        source = """(program t (var ((i int) (sum int))) (begin
            (:= i 0)
            (:= sum 0)
            (while (< i 10)
                (begin
                    (:= sum (+ sum i))
                    (:= i (+ i 1))))
            (print sum)
        ))"""
        output = compile_and_run(source)
        self.assertEqual(output, "45")

    def test_nested_while_loops(self):
        """Nested while loops should work correctly."""
        source = """(program t (var ((i int) (j int) (count int))) (begin
            (:= i 0)
            (:= count 0)
            (while (< i 3)
                (begin
                    (:= j 0)
                    (while (< j 3)
                        (begin
                            (:= count (+ count 1))
                            (:= j (+ j 1))))
                    (:= i (+ i 1))))
            (print count)
        ))"""
        output = compile_and_run(source)
        self.assertEqual(output, "9")

    def test_if_else_with_nested_conditions(self):
        """If/else with nested conditions should work correctly."""
        source = """(program t (var ((x int) (y int))) (begin
            (:= x 5)
            (:= y 10)
            (if (> x 0)
                (if (< y 20)
                    (print 1)
                    (print 0))
                (print 0))
        ))"""
        output = compile_and_run(source)
        self.assertEqual(output, "1")

    def test_multiple_print_statements(self):
        """Multiple print statements should work correctly."""
        source = """(program t (begin
            (print 1)
            (print 2)
            (print 3)
        ))"""
        output = compile_and_run(source)
        self.assertEqual(output, "1\n2\n3")

    def test_print_mixed_types(self):
        """Print mixed types should work correctly."""
        source = """(program t (var ((x int) (y float) (z bool))) (begin
            (:= x 42)
            (:= y 3.14)
            (:= z true)
            (print x)
            (print y)
            (print z)
        ))"""
        output = compile_and_run(source)
        self.assertIn("42", output)
        self.assertIn("3.14", output)
        self.assertIn("true", output)

    def test_function_with_no_statements(self):
        """Function with no statements should work correctly."""
        source = """(program t (begin
            (function noop () int (return 0))
            (print (noop))
        ))"""
        output = compile_and_run(source)
        self.assertEqual(output, "0")

    def test_function_call_in_expression(self):
        """Function call in expression should work correctly."""
        source = """(program t (begin
            (function add ((a int) (b int)) int (return (+ a b)))
            (print (+ (add 1 2) (add 3 4)))
        ))"""
        output = compile_and_run(source)
        self.assertEqual(output, "10")


if __name__ == "__main__":
    unittest.main()
