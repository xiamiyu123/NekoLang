"""Tests for neko.viz_serializers — JSON serialization of compiler data structures."""

import dataclasses
import unittest

from neko import ast_nodes
from neko.build_utils import compile_source
from neko.ast_nodes import (
    ASTNode,
    ArgcNode,
    ArgvNode,
    ArrayAccessNode,
    ArrayAssignNode,
    AssignNode,
    BeginBlockNode,
    BinOpNode,
    BlockNode,
    BoolLiteralNode,
    CharLiteralNode,
    ExternDeclNode,
    FloatLiteralNode,
    FuncCallNode,
    FuncDefNode,
    IdentifierNode,
    IfNode,
    ImportNode,
    InputNode,
    IntLiteralNode,
    LambdaDefNode,
    PrintNode,
    ProgramNode,
    RandomRangeNode,
    ReturnNode,
    StringLiteralNode,
    VarDeclNode,
    WhileNode,
)
from neko.lexer import Lexer
from neko.tokens import Token, TokenType


class TestTokenSerializer(unittest.TestCase):
    def test_serialize_single_token(self):
        from neko.viz_serializers import serialize_token

        token = Token(type=TokenType.VAR, value="var", line=1, column=1)
        result = serialize_token(token)
        self.assertEqual(result, {"type": "var", "value": "var", "line": 1, "column": 1})

    def test_serialize_token_with_symbol_value(self):
        from neko.viz_serializers import serialize_token

        token = Token(type=TokenType.ASSIGN, value=":=", line=2, column=5)
        result = serialize_token(token)
        self.assertEqual(result["type"], ":=")

    def test_serialize_token_list(self):
        from neko.viz_serializers import serialize_tokens

        tokens = Lexer("(nya t (paw (meow 0)))").tokenize()
        result = serialize_tokens(tokens)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        # First token is '(' (LPAREN), last is EOF
        self.assertEqual(result[0]["type"], "(")
        self.assertEqual(result[-1]["type"], "EOF")
        # 'nya' maps to TokenType.PROGRAM whose value is "program"
        program_tokens = [t for t in result if t["type"] == "program"]
        self.assertEqual(len(program_tokens), 1)

    def test_token_type_uses_enum_value(self):
        from neko.viz_serializers import serialize_token

        token = Token(type=TokenType.KW_INT, value="int", line=1, column=1)
        result = serialize_token(token)
        self.assertEqual(result["type"], "int")

    def test_serialize_empty_token_list(self):
        from neko.viz_serializers import serialize_tokens

        result = serialize_tokens([])
        self.assertEqual(result, [])


class TestASTSerializer(unittest.TestCase):
    # --- Leaf nodes ---

    def test_serialize_identifier_node(self):
        from neko.viz_serializers import serialize_ast

        node = IdentifierNode(name="x", line=3, column=5)
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "Identifier")
        self.assertEqual(result["name"], "x")
        self.assertEqual(result["line"], 3)
        self.assertEqual(result["column"], 5)

    def test_serialize_int_literal_node(self):
        from neko.viz_serializers import serialize_ast

        node = IntLiteralNode(value=42, line=1, column=1)
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "IntLiteral")
        self.assertEqual(result["value"], 42)

    def test_serialize_float_literal_node(self):
        from neko.viz_serializers import serialize_ast

        node = FloatLiteralNode(value=3.14, line=1, column=1)
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "FloatLiteral")
        self.assertAlmostEqual(result["value"], 3.14)

    def test_serialize_bool_literal_node(self):
        from neko.viz_serializers import serialize_ast

        node = BoolLiteralNode(value=True, line=1, column=1)
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "BoolLiteral")
        self.assertTrue(result["value"])

    def test_serialize_string_literal_node(self):
        from neko.viz_serializers import serialize_ast

        node = StringLiteralNode(value="hello", line=1, column=1)
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "StringLiteral")
        self.assertEqual(result["value"], "hello")

    def test_serialize_char_literal_node(self):
        from neko.viz_serializers import serialize_ast

        node = CharLiteralNode(value="a", line=1, column=1)
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "CharLiteral")
        self.assertEqual(result["value"], "a")

    def test_bare_ast_node_uses_fallback(self):
        from neko.viz_serializers import serialize_ast

        # A bare ASTNode uses the fallback serializer (for default-constructed children)
        node = ASTNode()
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "ASTNode")
        self.assertEqual(result["line"], 0)
        self.assertEqual(result["column"], 0)

    # --- Container nodes ---

    def test_serialize_program_node(self):
        from neko.viz_serializers import serialize_ast

        node = ProgramNode(name="test", block=BlockNode(), imports=[ImportNode(path="foo")])
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "Program")
        self.assertEqual(result["name"], "test")
        self.assertIn("block", result)
        self.assertEqual(len(result["imports"]), 1)
        self.assertEqual(result["imports"][0]["path"], "foo")

    def test_serialize_block_node(self):
        from neko.viz_serializers import serialize_ast

        node = BlockNode(
            var_decls=[VarDeclNode(variables=[("a", "int")])],
            body=BeginBlockNode(),
        )
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "Block")
        self.assertEqual(len(result["varDecls"]), 1)
        self.assertIn("body", result)

    def test_serialize_var_decl_node(self):
        from neko.viz_serializers import serialize_ast

        node = VarDeclNode(variables=[("a", "int"), ("b", "float")])
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "VarDecl")
        self.assertEqual(result["variables"], [{"name": "a", "type": "int"}, {"name": "b", "type": "float"}])

    # --- Statement nodes ---

    def test_serialize_assign_node(self):
        from neko.viz_serializers import serialize_ast

        node = AssignNode(target="x", value=IntLiteralNode(value=5, line=1, column=8), line=1, column=1)
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "Assign")
        self.assertEqual(result["target"], "x")
        self.assertEqual(result["value"]["nodeType"], "IntLiteral")
        self.assertEqual(result["value"]["value"], 5)

    def test_serialize_if_node(self):
        from neko.viz_serializers import serialize_ast

        node = IfNode(
            condition=BoolLiteralNode(value=True),
            then_branch=PrintNode(value=IntLiteralNode(value=1)),
            else_branch=PrintNode(value=IntLiteralNode(value=0)),
        )
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "If")
        self.assertEqual(result["condition"]["nodeType"], "BoolLiteral")
        self.assertEqual(result["thenBranch"]["nodeType"], "Print")
        self.assertEqual(result["elseBranch"]["nodeType"], "Print")

    def test_serialize_while_node(self):
        from neko.viz_serializers import serialize_ast

        node = WhileNode(
            condition=BoolLiteralNode(value=True),
            body=PrintNode(value=IntLiteralNode(value=0)),
        )
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "While")
        self.assertIn("condition", result)
        self.assertIn("body", result)

    def test_serialize_print_node(self):
        from neko.viz_serializers import serialize_ast

        node = PrintNode(value=IntLiteralNode(value=42, line=1, column=8), line=1, column=1)
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "Print")
        self.assertEqual(result["value"]["nodeType"], "IntLiteral")

    def test_serialize_func_def_node(self):
        from neko.viz_serializers import serialize_ast

        node = FuncDefNode(
            name="add",
            params=[("x", "int"), ("y", "int")],
            return_type="int",
            body=IntLiteralNode(value=0),
        )
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "FuncDef")
        self.assertEqual(result["name"], "add")
        self.assertEqual(result["params"], [{"name": "x", "type": "int"}, {"name": "y", "type": "int"}])
        self.assertEqual(result["returnType"], "int")

    def test_serialize_extern_decl_node(self):
        from neko.viz_serializers import serialize_ast

        node = ExternDeclNode(name="putchar", param_types=["int"], return_type="int")
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "ExternDecl")
        self.assertEqual(result["name"], "putchar")
        self.assertEqual(result["paramTypes"], ["int"])
        self.assertEqual(result["returnType"], "int")

    def test_serialize_func_call_node(self):
        from neko.viz_serializers import serialize_ast

        node = FuncCallNode(name="add", args=[IntLiteralNode(value=1), IntLiteralNode(value=2)])
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "FuncCall")
        self.assertEqual(result["name"], "add")
        self.assertEqual(len(result["args"]), 2)

    def test_serialize_return_node(self):
        from neko.viz_serializers import serialize_ast

        node = ReturnNode(value=IntLiteralNode(value=0))
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "Return")
        self.assertEqual(result["value"]["nodeType"], "IntLiteral")

    # --- Expression nodes ---

    def test_serialize_binop_node(self):
        from neko.viz_serializers import serialize_ast

        node = BinOpNode(op="+", left=IntLiteralNode(value=1), right=IntLiteralNode(value=2))
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "BinOp")
        self.assertEqual(result["op"], "+")
        self.assertEqual(result["left"]["nodeType"], "IntLiteral")
        self.assertEqual(result["right"]["nodeType"], "IntLiteral")

    def test_serialize_array_access_node(self):
        from neko.viz_serializers import serialize_ast

        node = ArrayAccessNode(name="arr", index=IntLiteralNode(value=0))
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "ArrayAccess")
        self.assertEqual(result["name"], "arr")
        self.assertEqual(result["index"]["nodeType"], "IntLiteral")

    def test_serialize_argc_node(self):
        from neko.viz_serializers import serialize_ast

        node = ArgcNode()
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "Argc")
        self.assertIn("line", result)
        self.assertIn("column", result)

    def test_serialize_random_range_node(self):
        from neko.viz_serializers import serialize_ast

        node = RandomRangeNode(low=IntLiteralNode(value=0), high=IntLiteralNode(value=100))
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "RandomRange")
        self.assertIn("low", result)
        self.assertIn("high", result)

    def test_serialize_input_node(self):
        from neko.viz_serializers import serialize_ast

        node = InputNode(value_type="float")
        result = serialize_ast(node)
        self.assertEqual(result["nodeType"], "Input")
        self.assertEqual(result["valueType"], "float")

    # --- Full pipeline test ---

    def test_serialize_full_ast_from_source(self):
        from neko.viz_serializers import serialize_ast

        source = "(nya t (nyan ((a int))) (paw (:= a 42) (meow a)))"
        tokens = Lexer(source).tokenize()
        from neko.parser import Parser

        parser = Parser(tokens)
        parser.set_source(source)
        ast = parser.parse()
        result = serialize_ast(ast)
        self.assertEqual(result["nodeType"], "Program")
        self.assertEqual(result["name"], "t")
        self.assertIn("block", result)

    # --- Completeness check ---

    def test_all_node_types_registered(self):
        from neko.viz_serializers import _AST_SERIALIZERS

        # Collect all concrete dataclass subclasses of ASTNode
        expected = set()
        for name in dir(ast_nodes):
            obj = getattr(ast_nodes, name)
            if (
                isinstance(obj, type)
                and issubclass(obj, ASTNode)
                and obj is not ASTNode
                and dataclasses.is_dataclass(obj)
            ):
                expected.add(name)

        registered = set(_AST_SERIALIZERS.keys())
        missing = expected - registered
        self.assertEqual(missing, set(), f"Missing serializers for: {missing}")


class TestErrorSerializer(unittest.TestCase):
    def test_serialize_semantic_error(self):
        from neko.errors import SemanticError
        from neko.viz_serializers import serialize_error

        err = SemanticError(
            message="undefined var",
            line=5,
            column=3,
            source_line="(:= x 1)",
            suggestion_key="undefined_var",
        )
        result = serialize_error(err)
        self.assertEqual(result["phase"], "Semantic")
        self.assertEqual(result["message"], "undefined var")
        self.assertEqual(result["line"], 5)
        self.assertEqual(result["column"], 3)
        self.assertEqual(result["sourceLine"], "(:= x 1)")
        self.assertNotEqual(result["suggestion"], "")

    def test_serialize_lex_error(self):
        from neko.errors import LexError
        from neko.viz_serializers import serialize_error

        err = LexError(message="invalid char", line=1, column=5)
        result = serialize_error(err)
        self.assertEqual(result["phase"], "Lexer")

    def test_serialize_parse_error(self):
        from neko.errors import ParseError
        from neko.viz_serializers import serialize_error

        err = ParseError(message="unexpected token", line=2, column=1)
        result = serialize_error(err)
        self.assertEqual(result["phase"], "Parser")

    def test_error_without_suggestion(self):
        from neko.errors import SemanticError
        from neko.viz_serializers import serialize_error

        err = SemanticError(message="type mismatch", line=1, column=1)
        result = serialize_error(err)
        self.assertEqual(result["suggestion"], "")

    def test_serialize_error_list(self):
        from neko.errors import SemanticError
        from neko.viz_serializers import serialize_errors

        errors = [
            SemanticError(message="err1", line=1, column=1),
            SemanticError(message="err2", line=2, column=1),
        ]
        result = serialize_errors(errors)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["message"], "err1")
        self.assertEqual(result[1]["message"], "err2")


class TestQuadrupleSerializer(unittest.TestCase):
    def test_serialize_quadruple(self):
        from neko.semantic import Quadruple
        from neko.viz_serializers import serialize_quadruple

        q = Quadruple(op=":=", ob1="C1", ob2="_", t="I2")
        result = serialize_quadruple(q)
        self.assertEqual(result, {"op": ":=", "ob1": "C1", "ob2": "_", "t": "I2"})

    def test_serialize_quadruple_with_defaults(self):
        from neko.semantic import Quadruple
        from neko.viz_serializers import serialize_quadruple

        q = Quadruple(op="end")
        result = serialize_quadruple(q)
        self.assertEqual(result["op"], "end")
        self.assertEqual(result["ob1"], "_")
        self.assertEqual(result["ob2"], "_")
        self.assertEqual(result["t"], "_")

    def test_serialize_quadruple_list(self):
        from neko.semantic import Quadruple
        from neko.viz_serializers import serialize_quadruples

        quads = [
            Quadruple(op="program", ob1="t"),
            Quadruple(op=":=", ob1="C1", t="I1"),
            Quadruple(op="end"),
        ]
        result = serialize_quadruples(quads)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["op"], "program")


class TestSymbolTableSerializer(unittest.TestCase):
    def test_serialize_symbol_entry(self):
        from neko.symbol_table import SymbolEntry
        from neko.viz_serializers import serialize_symbol_entry

        entry = SymbolEntry(name="x", type="int", cat="v", addr=0, scope="global", addr_name="I1")
        result = serialize_symbol_entry(entry)
        self.assertEqual(
            result,
            {
                "name": "x",
                "type": "int",
                "category": "v",
                "address": 0,
                "addressName": "I1",
                "scope": "global",
            },
        )

    def test_serialize_symbol_table(self):
        from neko.viz_serializers import serialize_symbol_table

        cr = compile_source("(nya t (nyan ((a int))) (paw (:= a 42)))")
        result = serialize_symbol_table(cr.analyzer.symbol_table)
        self.assertIn("entries", result)
        self.assertIn("constants", result)
        self.assertGreater(len(result["entries"]), 0)
        self.assertEqual(result["entries"][0]["category"], "program")
        self.assertEqual(result["entries"][1]["addressName"], "I1")
        self.assertEqual(result["entries"][1]["scope"], "global")
        self.assertIn("42", result["constants"])

    def test_serialize_empty_symbol_table(self):
        from neko.symbol_table import SymbolTable
        from neko.viz_serializers import serialize_symbol_table

        table = SymbolTable()
        result = serialize_symbol_table(table)
        self.assertEqual(result["entries"], [])
        self.assertEqual(result["constants"], {})


class TestCompilationResultSerializer(unittest.TestCase):
    def test_serialize_compilation_result_success(self):
        from neko.viz_serializers import serialize_compilation_result

        source = "(nya t (nyan ((a int))) (paw (:= a 42) (meow a)))"
        result = compile_source(source)
        serialized = serialize_compilation_result(result, backend="llvm")
        self.assertIn("source", serialized)
        self.assertIn("tokens", serialized)
        self.assertIn("ast", serialized)
        self.assertIn("symbols", serialized)
        self.assertIn("quadruples", serialized)
        self.assertIn("quadrupleDag", serialized)
        self.assertIn("quadrupleOptimization", serialized)
        self.assertIn("assembly", serialized)
        self.assertIn("errors", serialized)
        self.assertEqual(serialized["backend"], "llvm")
        self.assertGreater(len(serialized["tokens"]), 0)
        self.assertEqual(serialized["ast"]["nodeType"], "Program")
        self.assertGreater(len(serialized["symbols"]["entries"]), 0)
        self.assertGreater(len(serialized["quadruples"]), 0)
        self.assertEqual(
            serialized["quadrupleOptimization"]["beforeCount"],
            len(serialized["quadruples"]),
        )
        self.assertIsInstance(serialized["assembly"], str)
        self.assertEqual(serialized["errors"], [])

    def test_serialize_compilation_result_includes_quadruple_dag(self):
        from neko.viz_serializers import serialize_compilation_result

        source = "(nya t (nyan ((a int) (b int) (c int))) (paw (:= a (+ b c)) (:= b (+ b c))))"
        result = compile_source(source)
        serialized = serialize_compilation_result(result, backend="llvm")
        dag = serialized["quadrupleDag"]["blocks"][0]

        plus_nodes = [node for node in dag["nodes"] if node["op"] == "+"]
        self.assertEqual(len(plus_nodes), 1)
        self.assertIn("T1", plus_nodes[0]["names"])
        self.assertIn("T2", plus_nodes[0]["names"])
        self.assertEqual(len(dag["edges"]), 2)

    def test_quadruple_dag_uses_source_names_and_constant_values(self):
        from neko.viz_serializers import serialize_compilation_result

        source = "(nya t (nyan ((a int) (b int))) (paw (:= b 5) (:= a (+ b 3))))"
        result = compile_source(source)
        serialized = serialize_compilation_result(result, backend="llvm")
        dag = serialized["quadrupleDag"]["blocks"][0]
        values = {node["value"] for node in dag["nodes"] if node["op"] == "value"}
        names = {name for node in dag["nodes"] for name in node["names"]}

        self.assertIn("5", values)
        self.assertIn("3", values)
        self.assertIn("b", names)
        self.assertIn("a", names)

    def test_quadruple_dag_omits_blocks_without_nodes(self):
        from neko.viz_serializers import serialize_compilation_result

        source = "(nya t (paw (meow 1)))"
        result = compile_source(source)
        serialized = serialize_compilation_result(result, backend="llvm")

        self.assertEqual(serialized["quadrupleDag"]["blocks"], [])

    def test_serialize_compilation_result_includes_optimized_quadruples(self):
        from neko.viz_serializers import serialize_compilation_result

        source = "(nya t (nyan ((a int))) (paw (:= a (+ 2 3)) (meow a)))"
        result = compile_source(source)
        serialized = serialize_compilation_result(result, backend="llvm")
        optimization = serialized["quadrupleOptimization"]

        self.assertTrue(optimization["changed"])
        self.assertEqual(optimization["beforeCount"], 5)
        self.assertEqual(optimization["afterCount"], 4)
        self.assertEqual([q["op"] for q in optimization["initial"]], ["program", "+", ":=", "print", "end"])
        self.assertEqual([q["op"] for q in optimization["optimized"]], ["program", ":=", "print", "end"])
        self.assertEqual(optimization["optimized"][1]["ob1"], "C1")
        self.assertEqual(optimization["optimizedConstants"], {"5": "C1"})
        self.assertEqual(optimization["diagnostics"], [])
        self.assertEqual(optimization["steps"][1]["name"], "O1 常量折叠")
        self.assertTrue(optimization["steps"][1]["changed"])
        self.assertTrue(optimization["steps"][3]["changed"])

    def test_serialize_compilation_result_eliminates_repeated_quadruple_expression(self):
        from neko.viz_serializers import serialize_compilation_result

        source = "(nya t (nyan ((a int) (b int) (x int) (y int))) (paw (:= x (+ a b)) (:= y (+ a b))))"
        result = compile_source(source)
        serialized = serialize_compilation_result(result, backend="llvm")
        optimization = serialized["quadrupleOptimization"]

        self.assertTrue(optimization["changed"])
        self.assertEqual(optimization["beforeCount"], 6)
        self.assertEqual(optimization["afterCount"], 5)
        self.assertEqual(
            [q["op"] for q in optimization["optimized"]],
            ["program", "+", ":=", ":=", "end"],
        )
        self.assertEqual(optimization["optimized"][3]["ob1"], "T1")
        self.assertEqual(optimization["optimized"][3]["t"], "I4")
        self.assertTrue(optimization["steps"][2]["changed"])

    def test_serialize_compilation_result_with_errors(self):
        from neko.viz_serializers import serialize_compilation_result

        source = "(nya t (paw (:= undefined_var 1)))"
        result = compile_source(source)
        serialized = serialize_compilation_result(result, backend="llvm")
        self.assertGreater(len(serialized["errors"]), 0)
        self.assertEqual(serialized["errors"][0]["phase"], "Semantic")
        self.assertFalse(serialized["quadrupleOptimization"]["enabled"])
        # AST still available even with errors
        self.assertIsNotNone(serialized["ast"])

    def test_serialize_compilation_result_with_llvm_backend(self):
        from neko.viz_serializers import serialize_compilation_result

        source = "(nya t (nyan ((a int))) (paw (:= a 1) (meow a)))"
        result = compile_source(source)
        serialized = serialize_compilation_result(result, backend="llvm")
        self.assertIn("define", serialized["assembly"])
