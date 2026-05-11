import unittest
from neko.lexer import Lexer
from neko.parser import Parser
from neko.ast_nodes import (
    ProgramNode, BlockNode, VarDeclNode, BeginBlockNode,
    AssignNode, IfNode, WhileNode, PrintNode, BinOpNode,
    IdentifierNode, IntLiteralNode, FloatLiteralNode, BoolLiteralNode, StringLiteralNode,
    FuncDefNode, FuncCallNode, ReturnNode,
    ArgcNode, ArgvNode, InputNode, RandomSeedNode, RandomRangeNode, FileReadNode, FileWriteNode,
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


if __name__ == "__main__":
    unittest.main()
