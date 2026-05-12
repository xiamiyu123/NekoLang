import unittest
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


class TestSymbolTable(unittest.TestCase):
    def test_var_declaration(self):
        analyzer = compile_source("(program t (var ((a int))) (begin (:= a 1)))")
        entry = analyzer.symbol_table.lookup("a")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.type, "int")
        self.assertEqual(entry.cat, "v")

    def test_multiple_vars(self):
        analyzer = compile_source("(program t (var ((a int) (b float))) (begin (:= a 1)))")
        a = analyzer.symbol_table.lookup("a")
        b = analyzer.symbol_table.lookup("b")
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertEqual(a.type, "int")
        self.assertEqual(b.type, "float")

    def test_constant_table(self):
        analyzer = compile_source("(program t (var ((a int))) (begin (:= a 42)))")
        self.assertIn("42", analyzer.symbol_table.const_table)
        self.assertEqual(analyzer.symbol_table.const_table["42"], "C1")

    def test_temp_allocation(self):
        analyzer = compile_source("(program t (var ((a int))) (begin (:= a (+ 1 2))))")
        self.assertGreater(analyzer.symbol_table.temp_counter, 0)


class TestQuadruples(unittest.TestCase):
    def test_program_end(self):
        analyzer = compile_source("(program t (begin (print 0)))")
        first = str(analyzer.quadruples[0])
        last = str(analyzer.quadruples[-1])
        self.assertIn("program", first)
        self.assertIn("end", last)

    def test_assignment(self):
        analyzer = compile_source("(program t (var ((a int))) (begin (:= a 42)))")
        assigns = [q for q in analyzer.quadruples if q.op == ":="]
        self.assertGreaterEqual(len(assigns), 1)
        q = assigns[0]
        # I1 is the program name, I2 is the first variable
        self.assertEqual(q.t, "I2")

    def test_arithmetic(self):
        analyzer = compile_source("(program t (var ((a int))) (begin (:= a (+ 1 2))))")
        ops = [q for q in analyzer.quadruples if q.op == "+"]
        self.assertGreaterEqual(len(ops), 1)
        q = ops[0]
        self.assertEqual(q.ob1, "C1")
        self.assertEqual(q.ob2, "C2")
        self.assertTrue(q.t.startswith("T"))

    def test_nested_arithmetic(self):
        analyzer = compile_source("(program t (var ((a int))) (begin (:= a (+ (* 5 a) 2))))")
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn("*", ops)
        self.assertIn("+", ops)
        mul_idx = ops.index("*")
        add_idx = ops.index("+")
        self.assertLess(mul_idx, add_idx)

    def test_if_quadruples(self):
        analyzer = compile_source(
            "(program t (var ((x int))) (begin (if (> x 0) (:= x 1) (:= x 0))))"
        )
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn(">", ops)
        self.assertIn("if_false", ops)
        self.assertIn("goto", ops)
        self.assertIn("label", ops)

    def test_while_quadruples(self):
        analyzer = compile_source(
            "(program t (var ((i int))) (begin (while (< i 10) (:= i (+ i 1)))))"
        )
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn("<", ops)
        self.assertIn("if_false", ops)
        self.assertIn("goto", ops)
        self.assertGreaterEqual(ops.count("label"), 2)

    def test_function_call_quadruples(self):
        analyzer = compile_source(
            "(program t (var ((x int))) "
            "(begin "
            "(function add ((a int) (b int)) int (return (+ a b))) "
            "(:= x (add 1 2))))"
        )
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn("param", ops)
        self.assertIn("call", ops)
        self.assertIn("return", ops)

    def test_runtime_io_quadruples(self):
        analyzer = compile_source(
            '(program t (var ((x int))) '
            '(begin (:= x (argc)) (:= x (argv-int 0)) (:= x (read-int "in.txt")) '
            '(write-int "out.txt" x)))'
        )
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn("argc", ops)
        self.assertIn("argv-int", ops)
        self.assertIn("read-int", ops)
        self.assertIn("write-int", ops)

    def test_input_quadruples(self):
        analyzer = compile_source(
            "(program t (var ((x int) (y bool))) (begin (:= x (input-int)) (:= y (input-bool))))"
        )
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn("input-int", ops)
        self.assertIn("input-bool", ops)

    def test_random_quadruples(self):
        analyzer = compile_source(
            "(program t (var ((x int))) (begin (rand-seed 7) (:= x (rand-range 1 6))))"
        )
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn("rand-seed", ops)
        self.assertIn("rand-range", ops)


class TestSemanticErrors(unittest.TestCase):
    def test_undefined_variable(self):
        analyzer = compile_source("(program t (begin (:= x 1)))")
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("未定义", analyzer.errors[0].message)

    def test_duplicate_declaration(self):
        analyzer = compile_source("(program t (var ((a int) (a float))) (begin (:= a 1)))")
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("已经声明", analyzer.errors[0].message)

    def test_missing_return(self):
        analyzer = compile_source(
            "(program t (begin (function add ((a int) (b int)) int (print a))))"
        )
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("缺少 return", analyzer.errors[0].message)

    def test_function_argument_type_mismatch(self):
        analyzer = compile_source(
            "(program t (var ((x bool))) "
            "(begin "
            "(function keep ((flag bool)) bool (return flag)) "
            "(:= x (keep 1))))"
        )
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("参数", analyzer.errors[0].message)

    def test_file_path_must_be_string(self):
        analyzer = compile_source("(program t (begin (write-int 1 2)))")
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("文件路径", analyzer.errors[0].message)

    def test_rand_seed_requires_int(self):
        analyzer = compile_source("(program t (begin (rand-seed true)))")
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("rand-seed", analyzer.errors[0].message)

    def test_rand_range_requires_int_bounds(self):
        analyzer = compile_source("(program t (var ((x int))) (begin (:= x (rand-range 1 false))))")
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("rand-range", analyzer.errors[0].message)

    def test_lambda_missing_return(self):
        analyzer = compile_source(
            "(program t (var ((f (func (int) int)))) "
            "(begin (:= f (lambda ((x int)) int (print x)))))"
        )
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("lambda", analyzer.errors[0].message)

    def test_lambda_type_mismatch(self):
        analyzer = compile_source(
            "(program t (var ((f (func (int int) int)))) "
            "(begin (:= f (lambda ((x int)) int (return x)))))"
        )
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("类型", analyzer.errors[0].message)

    def test_function_as_value_type_check(self):
        analyzer = compile_source(
            "(program t (var ((f (func (int) int)))) "
            "(begin "
            "(function double ((n int)) int (return (* n 2))) "
            "(:= f double)))"
        )
        self.assertEqual(len(analyzer.errors), 0)

    def test_extern_call_before_declaration(self):
        analyzer = compile_source(
            '(program t (var ((x int))) (begin (:= x (atoi "42")) (extern atoi (string) int)))'
        )
        self.assertEqual(len(analyzer.errors), 0)

    def test_extern_call_after_declaration(self):
        analyzer = compile_source(
            '(program t (var ((x int))) (begin (extern atoi (string) int) (:= x (atoi "42"))))'
        )
        self.assertEqual(len(analyzer.errors), 0)

    def test_extern_argument_count_mismatch(self):
        analyzer = compile_source(
            '(program t (var ((x int))) (begin (extern atoi (string) int) (:= x (atoi "42" "43"))))'
        )
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("期望", analyzer.errors[0].message)

    def test_extern_argument_type_mismatch(self):
        analyzer = compile_source(
            "(program t (var ((x int))) (begin (extern atoi (string) int) (:= x (atoi 42))))"
        )
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("参数", analyzer.errors[0].message)

    def test_extern_duplicate_with_variable(self):
        analyzer = compile_source(
            "(program t (var ((atoi int))) (begin (extern atoi (string) int) (print atoi)))"
        )
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("已经声明", analyzer.errors[0].message)

    def test_extern_array_type_rejected(self):
        analyzer = compile_source(
            "(program t (begin (extern fill ((array int 4)) int)))"
        )
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("暂不支持", analyzer.errors[0].message)

    def test_extern_as_function_value_type_check(self):
        analyzer = compile_source(
            "(program t (var ((f (func (string) int)) (x int))) "
            "(begin (extern atoi (string) int) (:= f atoi) (:= x (f \"42\"))))"
        )
        self.assertEqual(len(analyzer.errors), 0)

    def test_extern_as_function_value_mismatch(self):
        analyzer = compile_source(
            "(program t (var ((f (func (int) int)))) (begin (extern atoi (string) int) (:= f atoi)))"
        )
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("无法将", analyzer.errors[0].message)

    def test_string_concat_type_error(self):
        analyzer = compile_source(
            '(program t (var ((s string))) (begin (:= s (+ "hello" 5))))'
        )
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("字符串拼接", analyzer.errors[0].message)

    def test_string_concat_ok(self):
        analyzer = compile_source(
            '(program t (var ((s string))) (begin (:= s (+ "hello" " world"))))'
        )
        self.assertEqual(len(analyzer.errors), 0)

    def test_char_to_int_compatible(self):
        analyzer = compile_source(
            "(program t (var ((n int))) (begin (:= n (char-to-int 'a'))))"
        )
        self.assertEqual(len(analyzer.errors), 0)

    def test_string_var_declaration(self):
        analyzer = compile_source(
            '(program t (var ((s string))) (begin (:= s "hello")))'
        )
        self.assertEqual(len(analyzer.errors), 0)
        entry = analyzer.symbol_table.lookup("s")
        self.assertEqual(entry.type, "string")


    def test_string_comparison_lt_rejected(self):
        analyzer = compile_source(
            '(program t (var ((b bool))) (begin (:= b (< "a" "b"))))'
        )
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("string-cmp", analyzer.errors[0].message)

    def test_string_comparison_eq_allowed(self):
        analyzer = compile_source(
            '(program t (var ((b bool))) (begin (:= b (= "a" "a"))))'
        )
        self.assertEqual(len(analyzer.errors), 0)

    def test_string_length_type_error(self):
        analyzer = compile_source(
            "(program t (var ((n int) (x int))) (begin (:= x 42) (:= n (string-length x))))"
        )
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("string-length", analyzer.errors[0].message)

    def test_char_to_int_type_error(self):
        analyzer = compile_source(
            '(program t (var ((n int) (s string))) (begin (:= s "hello") (:= n (char-to-int s))))'
        )
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("char-to-int", analyzer.errors[0].message)

    def test_string_condition_rejected(self):
        analyzer = compile_source(
            '(program t (var ((s string))) (begin (:= s "x") (if s (print 1) (print 0))))'
        )
        self.assertGreater(len(analyzer.errors), 0)
        self.assertIn("if", analyzer.errors[0].message)


class TestStringCharQuadruples(unittest.TestCase):
    def test_string_length_quadruple(self):
        analyzer = compile_source(
            '(program t (var ((n int))) (begin (:= n (string-length "hello"))))'
        )
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn("string-length", ops)

    def test_char_to_int_quadruple(self):
        analyzer = compile_source(
            "(program t (var ((n int))) (begin (:= n (char-to-int 'a'))))"
        )
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn("char-to-int", ops)

    def test_string_sub_quadruple_has_result_temp(self):
        analyzer = compile_source(
            '(program t (var ((s string))) (begin (:= s (string-sub "hello" 1 3))))'
        )
        quad = next(q for q in analyzer.quadruples if q.op == "string-sub")
        self.assertIn(",", quad.ob2)
        self.assertTrue(quad.t.startswith("T"))

    def test_extern_call_quadruple(self):
        analyzer = compile_source(
            '(program t (var ((x int))) (begin (extern atoi (string) int) (:= x (atoi "42"))))'
        )
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn("param", ops)
        self.assertIn("call", ops)


class TestLambdaQuadruples(unittest.TestCase):
    def test_lambda_quadruples(self):
        analyzer = compile_source(
            "(program t (var ((f (func (int) int)) (r int))) "
            "(begin "
            "(:= f (lambda ((x int)) int (return (* x 2)))) "
            "(:= r (f 5))))"
        )
        ops = [q.op for q in analyzer.quadruples]
        self.assertIn("return", ops)
        self.assertIn("lambda_ref", ops)
        self.assertIn("call", ops)


class TestAddressNaming(unittest.TestCase):
    def test_variable_addresses(self):
        analyzer = compile_source(
            "(program t (var ((a int) (b int))) (begin (:= a 1) (:= b 2)))"
        )
        assigns = [q for q in analyzer.quadruples if q.op == ":="]
        # I1 = program, I2 = a, I3 = b
        self.assertEqual(assigns[0].t, "I2")
        self.assertEqual(assigns[1].t, "I3")

    def test_constant_addresses(self):
        analyzer = compile_source("(program t (var ((a int))) (begin (:= a 42) (:= a 99)))")
        consts = analyzer.symbol_table.const_table
        self.assertEqual(consts["42"], "C1")
        self.assertEqual(consts["99"], "C2")


class TestSemanticEdgeCases(unittest.TestCase):
    """Edge case tests for semantic analyzer stability."""

    def test_division_by_zero_semantic(self):
        """Division by zero should be accepted at semantic level (runtime handles it)."""
        # Semantic analyzer should not reject division by zero
        # The runtime behavior is undefined in C
        analyzer = compile_source("(program t (var ((x int))) (begin (:= x (/ 10 0))))")
        self.assertEqual(len(analyzer.errors), 0)

    def test_assign_to_undefined_variable(self):
        """Assigning to undefined variable should be caught as error."""
        source = """(program t (begin
            (:= undefined_var 5)
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_recursive_function_call(self):
        """Recursive function call should be accepted."""
        source = """(program t (begin
            (function factorial ((n int)) int
                (if (<= n 1)
                    (return 1)
                    (return (* n (factorial (- n 1))))))
            (print (factorial 5))
        ))"""
        analyzer = compile_source(source)
        # Should not have errors
        self.assertEqual(len(analyzer.errors), 0)

    def test_mutual_recursion(self):
        """Mutual recursion should be accepted."""
        source = """(program t (begin
            (function is-even ((n int)) int
                (if (= n 0)
                    (return 1)
                    (return (is-odd (- n 1)))))
            (function is-odd ((n int)) int
                (if (= n 0)
                    (return 0)
                    (return (is-even (- n 1)))))
            (print (is-even 4))
        ))"""
        analyzer = compile_source(source)
        # Should not have errors
        self.assertEqual(len(analyzer.errors), 0)

    def test_extern_with_string_return(self):
        """Extern returning string should be accepted."""
        source = """(program t (var ((s string))) (begin
            (extern getenv (string) string)
            (:= s (getenv "PATH"))
        ))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)

    def test_extern_with_bool_return(self):
        """Extern returning bool should be accepted."""
        source = """(program t (var ((b bool))) (begin
            (extern isatty (int) bool)
            (:= b (isatty 0))
        ))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)

    def test_extern_with_zero_params(self):
        """Extern with zero parameters should be accepted."""
        source = """(program t (var ((pid int))) (begin
            (extern getpid () int)
            (:= pid (getpid))
        ))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)

    def test_extern_with_pointer_return(self):
        source = """(program t (var ((p pointer))) (begin
            (extern malloc (int) pointer)
            (:= p (malloc 16))
        ))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)

    def test_pointer_compares_with_pointer(self):
        source = """(program t (var ((p pointer) (q pointer) (same bool))) (begin
            (extern malloc (int) pointer)
            (:= p (malloc 8))
            (:= q p)
            (:= same (= p q))
        ))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)

    def test_pointer_accepts_zero_literal(self):
        source = """(program t (var ((p pointer) (is-null bool))) (begin
            (:= p 0)
            (:= is-null (= p 0))
        ))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)

    def test_pointer_rejects_string_assignment(self):
        source = """(program t (var ((p pointer))) (begin
            (:= p "hello")
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_extern_duplicate_declaration(self):
        """Duplicate extern declaration should be caught as error."""
        source = """(program t (begin
            (extern atoi (string) int)
            (extern atoi (string) int)
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_string_comparison_rejected(self):
        """String comparison with < should be rejected."""
        source = """(program t (var ((s string))) (begin
            (:= s "hello")
            (if (< s "world") (print 1) (print 0))
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_string_comparison_gt_rejected(self):
        """String comparison with > should be rejected."""
        source = """(program t (var ((s string))) (begin
            (:= s "hello")
            (if (> s "world") (print 1) (print 0))
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_string_comparison_le_rejected(self):
        """String comparison with <= should be rejected."""
        source = """(program t (var ((s string))) (begin
            (:= s "hello")
            (if (<= s "world") (print 1) (print 0))
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_string_comparison_ge_rejected(self):
        """String comparison with >= should be rejected."""
        source = """(program t (var ((s string))) (begin
            (:= s "hello")
            (if (>= s "world") (print 1) (print 0))
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_float_arithmetic_type_widening(self):
        """Int + float should produce float type."""
        source = """(program t (var ((x float))) (begin
            (:= x (+ 1 2.5))
        ))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)

    def test_float_arithmetic_both_float(self):
        """Float + float should produce float type."""
        source = """(program t (var ((x float))) (begin
            (:= x (+ 1.5 2.5))
        ))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)

    def test_nested_function_definitions(self):
        """Functions defined inside if/while should be collected."""
        source = """(program t (var ((x int))) (begin
            (if (> x 0)
                (begin
                    (function inner ((a int)) int (return a))
                    (print (inner 1)))
                (print 0))
        ))"""
        analyzer = compile_source(source)
        # Should not have errors
        self.assertEqual(len(analyzer.errors), 0)

    def test_undefined_variable_error(self):
        """Undefined variable should be caught as error."""
        source = """(program t (begin
            (:= x 5)
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_duplicate_variable_declaration(self):
        """Duplicate variable declaration should be caught as error."""
        source = """(program t (var ((x int) (x float))) (begin
            (:= x 5)
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_missing_return_in_function(self):
        """Missing return in non-void function should be caught as error."""
        source = """(program t (begin
            (function bad () int (begin (print 0)))
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_argument_count_mismatch(self):
        """Argument count mismatch should be caught as error."""
        source = """(program t (begin
            (function add ((a int) (b int)) int (return (+ a b)))
            (print (add 1))
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_argument_type_mismatch(self):
        """Argument type mismatch should be caught as error."""
        source = """(program t (begin
            (function add ((a int) (b int)) int (return (+ a b)))
            (print (add 1 2.5))
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_lambda_missing_return(self):
        """Lambda missing return should be caught as error."""
        source = """(program t (var ((f (func (int) int)))) (begin
            (:= f (lambda ((x int)) int (print x)))
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_lambda_type_mismatch(self):
        """Lambda type mismatch should be caught as error."""
        source = """(program t (var ((f (func (int) int)))) (begin
            (:= f (lambda ((x int)) float (return 1.5)))
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_array_element_type_check(self):
        """Array element type should be checked."""
        source = """(program t (var ((arr (array int 5)))) (begin
            (array-set arr 0 42)
        ))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)

    def test_string_concat_type_check(self):
        """String concat with non-string should be caught as error."""
        source = """(program t (var ((s string))) (begin
            (:= s (+ "hello" 42))
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_string_length_type_check(self):
        """String length on non-string should be caught as error."""
        source = """(program t (var ((x int))) (begin
            (:= x (string-length 42))
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_char_to_int_type_check(self):
        """Char-to-int on non-char should be caught as error."""
        source = """(program t (var ((x int))) (begin
            (:= x (char-to-int 42))
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_rand_seed_type_check(self):
        """Rand-seed with non-int should be caught as error."""
        source = """(program t (begin
            (rand-seed 3.14)
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_rand_range_type_check(self):
        """Rand-range with non-int should be caught as error."""
        source = """(program t (var ((x int))) (begin
            (:= x (rand-range 1.0 100))
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_file_path_type_check(self):
        """File path should be string type."""
        source = """(program t (var ((x int))) (begin
            (:= x (read-int 42))
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_extern_array_param_rejected(self):
        """Extern with array parameter should be rejected."""
        source = """(program t (begin
            (extern bad (int (array int 5)) int)
        ))"""
        analyzer = compile_source(source)
        self.assertGreater(len(analyzer.errors), 0)

    def test_comparison_returns_bool(self):
        """Comparison expressions should return bool type."""
        source = """(program t (var ((b bool))) (begin
            (:= b (> 5 3))
        ))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)

    def test_comparison_with_arithmetic(self):
        """Comparison with arithmetic expressions should work."""
        source = """(program t (var ((b bool))) (begin
            (:= b (> (+ 1 2) (- 5 3)))
        ))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)

    def test_function_as_value(self):
        """Function as value should be accepted."""
        source = """(program t (var ((f (func (int) int)))) (begin
            (function id ((x int)) int (return x))
            (:= f id)
        ))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)

    def test_multiple_lambdas(self):
        """Multiple lambdas should be accepted."""
        source = """(program t (var ((f (func (int) int)) (g (func (int) int)))) (begin
            (:= f (lambda ((x int)) int (return (* x 2))))
            (:= g (lambda ((x int)) int (return (+ x 1))))
        ))"""
        analyzer = compile_source(source)
        self.assertEqual(len(analyzer.errors), 0)


if __name__ == "__main__":
    unittest.main()
