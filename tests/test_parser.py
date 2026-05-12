import unittest
from neko.lexer import Lexer
from neko.parser import Parser
from neko.ast_nodes import (
    ProgramNode, BlockNode, VarDeclNode, BeginBlockNode,
    AssignNode, IfNode, WhileNode, PrintNode, BinOpNode,
    IdentifierNode, IntLiteralNode, FloatLiteralNode, BoolLiteralNode, StringLiteralNode,
    CharLiteralNode,
    FuncDefNode, ExternDeclNode, LambdaDefNode, FuncCallNode, ReturnNode,
    ArgcNode, ArgvNode, InputNode, RandomSeedNode, RandomRangeNode, FileReadNode, FileWriteNode,
    StringLengthNode, StringAtNode, StringSubNode, StringCmpNode, StringContainsNode,
    IntToStringNode, StringToIntNode, ArgvStringNode,
    CharToIntNode, IntToCharNode, CharToStringNode, IsLetterNode, IsDigitNode,
    CharUpcaseNode, CharDowncaseNode,
)
from neko.errors import ParseError


def parse(source: str) -> ProgramNode:
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    parser.set_source(source)
    return parser.parse()


class TestParserProgram(unittest.TestCase):
    def test_minimal_program(self):
        ast = parse("(program test (begin (print 0)))")
        self.assertIsInstance(ast, ProgramNode)
        self.assertEqual(ast.name, "test")

    def test_program_with_vars(self):
        ast = parse("(program test (var ((x int))) (begin (:= x 1)))")
        self.assertIsInstance(ast, ProgramNode)
        self.assertEqual(len(ast.block.var_decls), 1)
        self.assertEqual(ast.block.var_decls[0].variables, [("x", "int")])


class TestParserVarDecl(unittest.TestCase):
    def test_single_var(self):
        ast = parse("(program t (var ((x int))) (begin (print 0)))")
        decl = ast.block.var_decls[0]
        self.assertEqual(decl.variables, [("x", "int")])

    def test_multiple_vars(self):
        ast = parse("(program t (var ((a int) (b float) (c char))) (begin (print 0)))")
        decl = ast.block.var_decls[0]
        self.assertEqual(decl.variables, [("a", "int"), ("b", "float"), ("c", "char")])

    def test_neko_box_array_alias(self):
        ast = parse("(program t (var ((arr (neko-box int 5)))) (begin (print 0)))")
        decl = ast.block.var_decls[0]
        self.assertEqual(decl.variables, [("arr", "(array int 5)")])


class TestParserAssign(unittest.TestCase):
    def test_assign_literal(self):
        ast = parse("(program t (var ((x int))) (begin (:= x 42)))")
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, AssignNode)
        self.assertEqual(stmt.target, "x")
        self.assertIsInstance(stmt.value, IntLiteralNode)
        self.assertEqual(stmt.value.value, 42)

    def test_assign_expression(self):
        ast = parse("(program t (var ((x int))) (begin (:= x (+ 1 2))))")
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, AssignNode)
        self.assertIsInstance(stmt.value, BinOpNode)
        self.assertEqual(stmt.value.op, "+")


class TestParserExpressions(unittest.TestCase):
    def test_simple_add(self):
        ast = parse("(program t (var ((x int))) (begin (:= x (+ 1 2))))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, BinOpNode)
        self.assertEqual(expr.op, "+")
        self.assertIsInstance(expr.left, IntLiteralNode)
        self.assertIsInstance(expr.right, IntLiteralNode)

    def test_nested_expression(self):
        ast = parse("(program t (var ((x int))) (begin (:= x (+ (* 5 a) 2))))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, BinOpNode)
        self.assertEqual(expr.op, "+")
        self.assertIsInstance(expr.left, BinOpNode)
        self.assertEqual(expr.left.op, "*")

    def test_identifier_expression(self):
        ast = parse("(program t (var ((x int) (y int))) (begin (:= x y)))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, IdentifierNode)
        self.assertEqual(expr.name, "y")

    def test_bool_literal_expression(self):
        ast = parse("(program t (var ((flag bool))) (begin (:= flag true)))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, BoolLiteralNode)
        self.assertTrue(expr.value)

    def test_string_literal_expression(self):
        ast = parse('(program t (begin (print "hello.txt")))')
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, StringLiteralNode)
        self.assertEqual(expr.value, "hello.txt")

    def test_argc_expression(self):
        ast = parse("(program t (var ((x int))) (begin (:= x (argc))))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, ArgcNode)

    def test_argv_expression(self):
        ast = parse("(program t (var ((x int))) (begin (:= x (argv-int 0))))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, ArgvNode)
        self.assertEqual(expr.value_type, "int")

    def test_file_read_expression(self):
        ast = parse('(program t (var ((x int))) (begin (:= x (read-int "input.txt"))))')
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, FileReadNode)
        self.assertEqual(expr.value_type, "int")

    def test_input_expression(self):
        ast = parse("(program t (var ((x int))) (begin (:= x (input-int))))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, InputNode)
        self.assertEqual(expr.value_type, "int")

    def test_rand_range_expression(self):
        ast = parse("(program t (var ((x int))) (begin (:= x (rand-range 1 10))))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, RandomRangeNode)


class TestParserIf(unittest.TestCase):
    def test_if_statement(self):
        ast = parse("(program t (var ((x int))) (begin (if (> x 0) (:= x 1) (:= x 0))))")
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, IfNode)
        self.assertIsInstance(stmt.condition, BinOpNode)
        self.assertEqual(stmt.condition.op, ">")
        self.assertIsInstance(stmt.then_branch, AssignNode)
        self.assertIsInstance(stmt.else_branch, AssignNode)


class TestParserWhile(unittest.TestCase):
    def test_while_statement(self):
        ast = parse("(program t (var ((i int))) (begin (while (< i 10) (:= i (+ i 1)))))")
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, WhileNode)
        self.assertIsInstance(stmt.condition, BinOpNode)
        self.assertEqual(stmt.condition.op, "<")
        self.assertIsInstance(stmt.body, AssignNode)


class TestParserFunctions(unittest.TestCase):
    def test_function_definition(self):
        ast = parse(
            "(program t (begin (function add ((a int) (b int)) int (return (+ a b)))))"
        )
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, FuncDefNode)
        self.assertEqual(stmt.name, "add")
        self.assertEqual(stmt.params, [("a", "int"), ("b", "int")])
        self.assertEqual(stmt.return_type, "int")
        self.assertIsInstance(stmt.body, ReturnNode)

    def test_function_call_expression(self):
        ast = parse(
            "(program t (var ((x int))) (begin "
            "(function add ((a int) (b int)) int (return (+ a b))) "
            "(:= x (add 1 2))))"
        )
        expr = ast.block.body.statements[1].value
        self.assertIsInstance(expr, FuncCallNode)
        self.assertEqual(expr.name, "add")
        self.assertEqual(len(expr.args), 2)

    def test_extern_declaration(self):
        ast = parse("(program t (begin (extern atoi (string) int)))")
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, ExternDeclNode)
        self.assertEqual(stmt.name, "atoi")
        self.assertEqual(stmt.param_types, ["string"])
        self.assertEqual(stmt.return_type, "int")

    def test_extern_zero_args(self):
        ast = parse("(program t (begin (extern getpid () int)))")
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, ExternDeclNode)
        self.assertEqual(stmt.param_types, [])

    def test_extern_pointer_signature(self):
        ast = parse("(program t (begin (extern malloc (int) pointer)))")
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, ExternDeclNode)
        self.assertEqual(stmt.param_types, ["int"])
        self.assertEqual(stmt.return_type, "pointer")

    def test_extern_inside_begin_with_other_statements(self):
        ast = parse(
            "(program t (var ((x int))) (begin (extern atoi (string) int) (:= x (atoi \"42\"))))"
        )
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, ExternDeclNode)
        expr = ast.block.body.statements[1].value
        self.assertIsInstance(expr, FuncCallNode)
        self.assertEqual(expr.name, "atoi")


class TestParserPrint(unittest.TestCase):
    def test_print_literal(self):
        ast = parse("(program t (begin (print 42)))")
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, PrintNode)
        self.assertIsInstance(stmt.value, IntLiteralNode)

    def test_print_identifier(self):
        ast = parse("(program t (var ((x int))) (begin (print x)))")
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, PrintNode)
        self.assertIsInstance(stmt.value, IdentifierNode)

    def test_meow_is_print_alias(self):
        ast = parse("(program t (var ((x int))) (begin (meow x)))")
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, PrintNode)
        self.assertIsInstance(stmt.value, IdentifierNode)

    def test_meow_is_not_assignment_alias(self):
        with self.assertRaises(ParseError):
            parse("(program t (var ((x int))) (begin (meow x 1)))")


class TestParserRuntimeIO(unittest.TestCase):
    def test_write_statement(self):
        ast = parse('(program t (begin (write-int "out.txt" 42)))')
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, FileWriteNode)
        self.assertEqual(stmt.value_type, "int")
        self.assertIsInstance(stmt.path, StringLiteralNode)

    def test_rand_seed_statement(self):
        ast = parse("(program t (begin (rand-seed 123)))")
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, RandomSeedNode)


class TestParserBeginBlock(unittest.TestCase):
    def test_nested_begin(self):
        ast = parse("(program t (begin (begin (print 1))))")
        outer = ast.block.body.statements[0]
        self.assertIsInstance(outer, BeginBlockNode)
        # The inner begin block contains a print statement
        self.assertIsInstance(outer.statements[0], PrintNode)


class TestParserErrors(unittest.TestCase):
    def test_missing_paren(self):
        with self.assertRaises(ParseError):
            parse("(program test (begin (print 0))")

    def test_unexpected_token(self):
        with self.assertRaises(ParseError):
            parse("(program test (begin (unknown 1)))")

    def test_trailing_token_rejected(self):
        with self.assertRaises(ParseError):
            parse("(program test (begin (print 0))))")


class TestParserCharLiteral(unittest.TestCase):
    def test_char_literal(self):
        ast = parse("(program t (var ((c char))) (begin (:= c 'a')))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, CharLiteralNode)
        self.assertEqual(expr.value, "a")

    def test_char_escape(self):
        ast = parse(r"(program t (var ((c char))) (begin (:= c '\n')))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, CharLiteralNode)
        self.assertEqual(expr.value, "\n")


class TestParserStringVarDecl(unittest.TestCase):
    def test_string_var(self):
        ast = parse("(program t (var ((s string))) (begin (:= s \"hello\")))")
        decl = ast.block.var_decls[0]
        self.assertEqual(decl.variables, [("s", "string")])

    def test_string_assign(self):
        ast = parse('(program t (var ((s string))) (begin (:= s "hello")))')
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, AssignNode)
        self.assertIsInstance(stmt.value, StringLiteralNode)


class TestParserStringOps(unittest.TestCase):
    def test_string_length(self):
        ast = parse('(program t (var ((n int))) (begin (:= n (string-length "hello"))))')
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, StringLengthNode)

    def test_string_at(self):
        ast = parse('(program t (var ((c char))) (begin (:= c (string-at "hello" 0))))')
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, StringAtNode)

    def test_string_sub(self):
        ast = parse('(program t (var ((s string))) (begin (:= s (string-sub "hello" 1 3))))')
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, StringSubNode)

    def test_string_cmp(self):
        ast = parse('(program t (var ((n int))) (begin (:= n (string-cmp "a" "b"))))')
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, StringCmpNode)

    def test_string_contains(self):
        ast = parse('(program t (var ((b bool))) (begin (:= b (string-contains "hello" "ell"))))')
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, StringContainsNode)

    def test_int_to_string(self):
        ast = parse('(program t (var ((s string))) (begin (:= s (int-to-string 42))))')
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, IntToStringNode)

    def test_string_to_int(self):
        ast = parse('(program t (var ((n int))) (begin (:= n (string-to-int "42"))))')
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, StringToIntNode)

    def test_argv_string(self):
        ast = parse("(program t (var ((s string))) (begin (:= s (argv-string 0))))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, ArgvStringNode)


class TestParserCharOps(unittest.TestCase):
    def test_char_to_int(self):
        ast = parse("(program t (var ((n int))) (begin (:= n (char-to-int 'a'))))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, CharToIntNode)

    def test_int_to_char(self):
        ast = parse("(program t (var ((c char))) (begin (:= c (int-to-char 65))))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, IntToCharNode)

    def test_char_to_string(self):
        ast = parse("(program t (var ((s string))) (begin (:= s (char-to-string 'a'))))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, CharToStringNode)

    def test_is_letter(self):
        ast = parse("(program t (var ((b bool))) (begin (:= b (is-letter 'a'))))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, IsLetterNode)

    def test_is_digit(self):
        ast = parse("(program t (var ((b bool))) (begin (:= b (is-digit '5'))))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, IsDigitNode)

    def test_char_upcase(self):
        ast = parse("(program t (var ((c char))) (begin (:= c (char-upcase 'a'))))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, CharUpcaseNode)

    def test_char_downcase(self):
        ast = parse("(program t (var ((c char))) (begin (:= c (char-downcase 'A'))))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, CharDowncaseNode)


class TestParserLambda(unittest.TestCase):
    def test_lambda_definition(self):
        ast = parse(
            "(program t (var ((f (func (int) int)))) "
            "(begin (:= f (lambda ((x int)) int (return (* x 2))))))"
        )
        assign = ast.block.body.statements[0]
        self.assertIsInstance(assign, AssignNode)
        self.assertIsInstance(assign.value, LambdaDefNode)
        lam = assign.value
        self.assertEqual(lam.params, [("x", "int")])
        self.assertEqual(lam.return_type, "int")
        self.assertIsInstance(lam.body, ReturnNode)

    def test_lambda_two_params(self):
        ast = parse(
            "(program t (var ((f (func (int int) int)))) "
            "(begin (:= f (lambda ((a int) (b int)) int (return (+ a b))))))"
        )
        lam = ast.block.body.statements[0].value
        self.assertIsInstance(lam, LambdaDefNode)
        self.assertEqual(len(lam.params), 2)
        self.assertEqual(lam.params[0], ("a", "int"))
        self.assertEqual(lam.params[1], ("b", "int"))

    def test_func_type_in_var(self):
        ast = parse(
            "(program t (var ((f (func (int) int)))) (begin (:= f 0)))"
        )
        decl = ast.block.var_decls[0]
        self.assertEqual(decl.variables[0], ("f", "(func (int) int)"))

    def test_func_type_in_param(self):
        ast = parse(
            "(program t (begin "
            "(function apply ((f (func (int) int)) (x int)) int (return (f x))) "
            "(:= x 1)))"
        )
        func = ast.block.body.statements[0]
        self.assertIsInstance(func, FuncDefNode)
        self.assertEqual(func.params[0], ("f", "(func (int) int)"))


class TestParserEdgeCases(unittest.TestCase):
    """Edge case tests for parser stability."""

    def test_empty_begin_block(self):
        """Empty begin block should parse successfully."""
        ast = parse("(program t (begin))")
        self.assertIsInstance(ast, ProgramNode)
        self.assertIsInstance(ast.block.body, BeginBlockNode)
        self.assertEqual(len(ast.block.body.statements), 0)

    def test_begin_with_single_statement(self):
        """Begin block with single statement should parse correctly."""
        ast = parse("(program t (begin (print 0)))")
        self.assertIsInstance(ast, ProgramNode)
        self.assertEqual(len(ast.block.body.statements), 1)

    def test_if_without_else_should_fail(self):
        """If without else should raise ParseError."""
        with self.assertRaises(ParseError):
            parse("(program t (var ((x int))) (begin (if (> x 0) (:= x 1))))")

    def test_deeply_nested_expression(self):
        """Deeply nested expression should parse correctly."""
        ast = parse("(program t (begin (print (+ (* (+ 1 2) 3) 4))))")
        self.assertIsInstance(ast, ProgramNode)
        # Should not raise any errors

    def test_multiple_var_blocks(self):
        """Multiple var blocks should parse correctly."""
        ast = parse("(program t (var ((a int))) (var ((b float))) (begin (print 0)))")
        self.assertIsInstance(ast, ProgramNode)
        self.assertEqual(len(ast.block.var_decls), 2)
        self.assertEqual(ast.block.var_decls[0].variables, [("a", "int")])
        self.assertEqual(ast.block.var_decls[1].variables, [("b", "float")])

    def test_function_with_no_params(self):
        """Function with no parameters should parse correctly."""
        ast = parse("(program t (begin (function f () int (return 0)) (print 0)))")
        func = ast.block.body.statements[0]
        self.assertIsInstance(func, FuncDefNode)
        self.assertEqual(func.name, "f")
        self.assertEqual(len(func.params), 0)
        self.assertEqual(func.return_type, "int")

    def test_function_with_multiple_params(self):
        """Function with multiple parameters should parse correctly."""
        ast = parse("(program t (begin (function add ((a int) (b int)) int (return (+ a b))) (print 0)))")
        func = ast.block.body.statements[0]
        self.assertIsInstance(func, FuncDefNode)
        self.assertEqual(len(func.params), 2)
        self.assertEqual(func.params[0], ("a", "int"))
        self.assertEqual(func.params[1], ("b", "int"))

    def test_nested_function_calls(self):
        """Nested function calls should parse correctly."""
        ast = parse("(program t (begin (print (f (g 1) (h 2)))))")
        self.assertIsInstance(ast, ProgramNode)

    def test_multiple_statements_in_begin(self):
        """Multiple statements in begin block should parse correctly."""
        source = """(program t (begin
            (print 1)
            (print 2)
            (print 3)
        ))"""
        ast = parse(source)
        self.assertIsInstance(ast, ProgramNode)
        self.assertEqual(len(ast.block.body.statements), 3)

    def test_while_with_empty_body(self):
        """While with empty body should parse correctly."""
        ast = parse("(program t (var ((x int))) (begin (while (< x 10) (begin))))")
        self.assertIsInstance(ast, ProgramNode)

    def test_if_with_empty_branches(self):
        """If with empty branches should parse correctly."""
        ast = parse("(program t (var ((x int))) (begin (if (> x 0) (begin) (begin))))")
        self.assertIsInstance(ast, ProgramNode)

    def test_complex_nested_control_flow(self):
        """Complex nested control flow should parse correctly."""
        source = """(program t (var ((x int) (y int))) (begin
            (if (> x 0)
                (begin
                    (while (< y 10)
                        (begin
                            (:= y (+ y 1))
                            (print y))))
                (begin
                    (print 0)))
        ))"""
        ast = parse(source)
        self.assertIsInstance(ast, ProgramNode)

    def test_extern_with_zero_params(self):
        """Extern with zero parameters should parse correctly."""
        ast = parse("(program t (begin (extern getpid () int) (print 0)))")
        extern = ast.block.body.statements[0]
        self.assertIsInstance(extern, ExternDeclNode)
        self.assertEqual(extern.name, "getpid")
        self.assertEqual(len(extern.param_types), 0)
        self.assertEqual(extern.return_type, "int")

    def test_extern_with_multiple_params(self):
        """Extern with multiple parameters should parse correctly."""
        ast = parse("(program t (begin (extern myfunc (int float string) int) (print 0)))")
        extern = ast.block.body.statements[0]
        self.assertIsInstance(extern, ExternDeclNode)
        self.assertEqual(extern.name, "myfunc")
        self.assertEqual(extern.param_types, ["int", "float", "string"])
        self.assertEqual(extern.return_type, "int")

    def test_lambda_with_no_params(self):
        """Lambda with no parameters should parse correctly."""
        ast = parse("(program t (var ((f (func () int)))) (begin (:= f (lambda () int (return 0)))))")
        assign = ast.block.body.statements[0]
        lam = assign.value
        self.assertIsInstance(lam, LambdaDefNode)
        self.assertEqual(len(lam.params), 0)

    def test_array_operations_parsing(self):
        """Array operations should parse correctly."""
        source = """(program t (var ((arr (array int 5)))) (begin
            (array-set arr 0 42)
            (array-print arr 0)
        ))"""
        ast = parse(source)
        self.assertIsInstance(ast, ProgramNode)

    def test_string_operations_parsing(self):
        """String operations should parse correctly."""
        source = """(program t (var ((s string))) (begin
            (:= s "hello")
            (print (string-length s))
            (print (string-at s 0))
            (print (string-sub s 0 3))
        ))"""
        ast = parse(source)
        self.assertIsInstance(ast, ProgramNode)

    def test_char_operations_parsing(self):
        """Char operations should parse correctly."""
        source = """(program t (var ((c char))) (begin
            (:= c 'A')
            (print (char-to-int c))
            (print (int-to-char 65))
        ))"""
        ast = parse(source)
        self.assertIsInstance(ast, ProgramNode)

    def test_mixed_expressions_and_statements(self):
        """Mixed expressions and statements should parse correctly."""
        source = """(program t (var ((x int) (y float))) (begin
            (:= x (+ 1 2))
            (:= y (* 3.14 2.0))
            (if (> x 0)
                (print x)
                (print y))
        ))"""
        ast = parse(source)
        self.assertIsInstance(ast, ProgramNode)

    def test_deeply_nested_parentheses(self):
        """Deeply nested parentheses should parse correctly."""
        source = "(program t (begin (print (+ (+ (+ (+ 1 2) 3) 4) 5))))"
        ast = parse(source)
        self.assertIsInstance(ast, ProgramNode)

    def test_multiple_functions(self):
        """Multiple functions should parse correctly."""
        source = """(program t (begin
            (function add ((a int) (b int)) int (return (+ a b)))
            (function sub ((a int) (b int)) int (return (- a b)))
            (print (add 1 2))
        ))"""
        ast = parse(source)
        self.assertIsInstance(ast, ProgramNode)

    def test_function_call_as_argument(self):
        """Function call as argument should parse correctly."""
        source = "(program t (begin (function id ((x int)) int (return x)) (print (id 42))))"
        ast = parse(source)
        self.assertIsInstance(ast, ProgramNode)


if __name__ == "__main__":
    unittest.main()
