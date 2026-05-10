import unittest
from neko.lexer import Lexer
from neko.parser import Parser
from neko.ast_nodes import (
    ProgramNode, BlockNode, VarDeclNode, PawBlockNode,
    AssignNode, IfNode, WhileNode, PrintNode, BinOpNode,
    IdentifierNode, IntLiteralNode, FloatLiteralNode,
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
        ast = parse("(nya test (paw (purr 0)))")
        self.assertIsInstance(ast, ProgramNode)
        self.assertEqual(ast.name, "test")

    def test_program_with_vars(self):
        ast = parse("(nya test (nyan ((x int))) (paw (meow x 1)))")
        self.assertIsInstance(ast, ProgramNode)
        self.assertEqual(len(ast.block.var_decls), 1)
        self.assertEqual(ast.block.var_decls[0].variables, [("x", "int")])


class TestParserVarDecl(unittest.TestCase):
    def test_single_var(self):
        ast = parse("(nya t (nyan ((x int))) (paw (purr 0)))")
        decl = ast.block.var_decls[0]
        self.assertEqual(decl.variables, [("x", "int")])

    def test_multiple_vars(self):
        ast = parse("(nya t (nyan ((a int) (b float) (c char))) (paw (purr 0)))")
        decl = ast.block.var_decls[0]
        self.assertEqual(decl.variables, [("a", "int"), ("b", "float"), ("c", "char")])


class TestParserAssign(unittest.TestCase):
    def test_assign_literal(self):
        ast = parse("(nya t (nyan ((x int))) (paw (meow x 42)))")
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, AssignNode)
        self.assertEqual(stmt.target, "x")
        self.assertIsInstance(stmt.value, IntLiteralNode)
        self.assertEqual(stmt.value.value, 42)

    def test_assign_expression(self):
        ast = parse("(nya t (nyan ((x int))) (paw (meow x (+ 1 2))))")
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, AssignNode)
        self.assertIsInstance(stmt.value, BinOpNode)
        self.assertEqual(stmt.value.op, "+")


class TestParserExpressions(unittest.TestCase):
    def test_simple_add(self):
        ast = parse("(nya t (nyan ((x int))) (paw (meow x (+ 1 2))))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, BinOpNode)
        self.assertEqual(expr.op, "+")
        self.assertIsInstance(expr.left, IntLiteralNode)
        self.assertIsInstance(expr.right, IntLiteralNode)

    def test_nested_expression(self):
        ast = parse("(nya t (nyan ((x int))) (paw (meow x (+ (* 5 a) 2))))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, BinOpNode)
        self.assertEqual(expr.op, "+")
        self.assertIsInstance(expr.left, BinOpNode)
        self.assertEqual(expr.left.op, "*")

    def test_identifier_expression(self):
        ast = parse("(nya t (nyan ((x int) (y int))) (paw (meow x y)))")
        expr = ast.block.body.statements[0].value
        self.assertIsInstance(expr, IdentifierNode)
        self.assertEqual(expr.name, "y")


class TestParserIf(unittest.TestCase):
    def test_if_statement(self):
        ast = parse("(nya t (nyan ((x int))) (paw (if-nya (> x 0) (meow x 1) (meow x 0))))")
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, IfNode)
        self.assertIsInstance(stmt.condition, BinOpNode)
        self.assertEqual(stmt.condition.op, ">")
        self.assertIsInstance(stmt.then_branch, AssignNode)
        self.assertIsInstance(stmt.else_branch, AssignNode)


class TestParserWhile(unittest.TestCase):
    def test_while_statement(self):
        ast = parse("(nya t (nyan ((i int))) (paw (purr-while (< i 10) (meow i (+ i 1)))))")
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, WhileNode)
        self.assertIsInstance(stmt.condition, BinOpNode)
        self.assertEqual(stmt.condition.op, "<")
        self.assertIsInstance(stmt.body, AssignNode)


class TestParserPrint(unittest.TestCase):
    def test_print_literal(self):
        ast = parse("(nya t (paw (purr 42)))")
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, PrintNode)
        self.assertIsInstance(stmt.value, IntLiteralNode)

    def test_print_identifier(self):
        ast = parse("(nya t (nyan ((x int))) (paw (purr x)))")
        stmt = ast.block.body.statements[0]
        self.assertIsInstance(stmt, PrintNode)
        self.assertIsInstance(stmt.value, IdentifierNode)


class TestParserPawBlock(unittest.TestCase):
    def test_nested_paw(self):
        ast = parse("(nya t (paw (paw (purr 1))))")
        outer = ast.block.body.statements[0]
        self.assertIsInstance(outer, PawBlockNode)
        # The inner paw block contains a print statement
        self.assertIsInstance(outer.statements[0], PrintNode)


class TestParserErrors(unittest.TestCase):
    def test_missing_paren(self):
        with self.assertRaises(ParseError):
            parse("(nya test (paw (purr 0))")

    def test_unexpected_token(self):
        with self.assertRaises(ParseError):
            parse("(nya test (paw (unknown 1)))")


if __name__ == "__main__":
    unittest.main()
