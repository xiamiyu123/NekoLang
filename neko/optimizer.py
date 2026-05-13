"""Small AST-level optimization passes for backend code generation."""

from __future__ import annotations

import copy
from dataclasses import replace

from .ast_nodes import (
    ASTNode,
    ArrayAccessNode,
    ArrayAssignNode,
    ArrayPrintNode,
    ArgvNode,
    ArgvStringNode,
    AssignNode,
    BeginBlockNode,
    BinOpNode,
    BlockNode,
    BoolLiteralNode,
    CharDowncaseNode,
    CharLiteralNode,
    CharToIntNode,
    CharToStringNode,
    CharUpcaseNode,
    FileReadNode,
    FileWriteNode,
    FloatLiteralNode,
    FuncCallNode,
    FuncDefNode,
    IdentifierNode,
    IfNode,
    InputNode,
    IntLiteralNode,
    IntToCharNode,
    IntToStringNode,
    IsDigitNode,
    IsLetterNode,
    LambdaDefNode,
    PrintNode,
    ProgramNode,
    RandomRangeNode,
    RandomSeedNode,
    ReturnNode,
    StringAtNode,
    StringCmpNode,
    StringContainsNode,
    StringLengthNode,
    StringLiteralNode,
    StringSubNode,
    StringToIntNode,
    WhileNode,
)


def optimize_ast_for_arm64(ast: ProgramNode, opt_level: int = 0) -> ProgramNode:
    """Return an optimized copy of an AST for ARM64 code generation."""
    if opt_level <= 0:
        return ast
    return _fold_node(copy.deepcopy(ast))


def _copy_location(src: ASTNode, dst: ASTNode) -> ASTNode:
    dst.line = getattr(src, "line", 0)
    dst.column = getattr(src, "column", 0)
    return dst


def _int_value(node: ASTNode) -> int | None:
    if isinstance(node, IntLiteralNode):
        return node.value
    if isinstance(node, BoolLiteralNode):
        return 1 if node.value else 0
    if isinstance(node, CharLiteralNode):
        return ord(node.value)
    return None


def _trunc_div(left: int, right: int) -> int:
    return abs(left) // abs(right) * (-1 if (left < 0) ^ (right < 0) else 1)


def _ascii_is_letter(value: str) -> bool:
    return ("a" <= value <= "z") or ("A" <= value <= "Z")


def _ascii_is_digit(value: str) -> bool:
    return "0" <= value <= "9"


def _ascii_upcase(value: str) -> str:
    if "a" <= value <= "z":
        return chr(ord(value) - 32)
    return value


def _ascii_downcase(value: str) -> str:
    if "A" <= value <= "Z":
        return chr(ord(value) + 32)
    return value


def _fold_binop(node: BinOpNode) -> ASTNode:
    left = _fold_node(node.left)
    right = _fold_node(node.right)
    folded = replace(node, left=left, right=right)

    left_int = _int_value(left)
    right_int = _int_value(right)
    if left_int is None or right_int is None:
        return folded

    if node.op == "+":
        return _copy_location(node, IntLiteralNode(value=left_int + right_int))
    if node.op == "-":
        return _copy_location(node, IntLiteralNode(value=left_int - right_int))
    if node.op == "*":
        return _copy_location(node, IntLiteralNode(value=left_int * right_int))
    if node.op == "/" and right_int != 0:
        return _copy_location(node, IntLiteralNode(value=_trunc_div(left_int, right_int)))
    if node.op == "<":
        return _copy_location(node, BoolLiteralNode(value=left_int < right_int))
    if node.op == ">":
        return _copy_location(node, BoolLiteralNode(value=left_int > right_int))
    if node.op == "=":
        return _copy_location(node, BoolLiteralNode(value=left_int == right_int))
    if node.op == "<=":
        return _copy_location(node, BoolLiteralNode(value=left_int <= right_int))
    if node.op == ">=":
        return _copy_location(node, BoolLiteralNode(value=left_int >= right_int))
    if node.op == "!=":
        return _copy_location(node, BoolLiteralNode(value=left_int != right_int))
    return folded


def _fold_node(node: ASTNode) -> ASTNode:
    if isinstance(node, ProgramNode):
        node.block = _fold_node(node.block)
        return node
    if isinstance(node, BlockNode):
        node.body = _fold_node(node.body)
        return node
    if isinstance(node, BeginBlockNode):
        node.statements = [_fold_node(stmt) for stmt in node.statements]
        return node
    if isinstance(node, AssignNode):
        node.value = _fold_node(node.value)
        return node
    if isinstance(node, IfNode):
        node.condition = _fold_node(node.condition)
        node.then_branch = _fold_node(node.then_branch)
        node.else_branch = _fold_node(node.else_branch)
        return node
    if isinstance(node, WhileNode):
        node.condition = _fold_node(node.condition)
        node.body = _fold_node(node.body)
        return node
    if isinstance(node, PrintNode):
        node.value = _fold_node(node.value)
        return node
    if isinstance(node, FuncDefNode):
        node.body = _fold_node(node.body)
        return node
    if isinstance(node, LambdaDefNode):
        node.body = _fold_node(node.body)
        return node
    if isinstance(node, ReturnNode):
        node.value = _fold_node(node.value)
        return node
    if isinstance(node, ArrayAccessNode):
        node.index = _fold_node(node.index)
        return node
    if isinstance(node, ArrayAssignNode):
        node.index = _fold_node(node.index)
        node.value = _fold_node(node.value)
        return node
    if isinstance(node, ArrayPrintNode):
        node.index = _fold_node(node.index)
        return node
    if isinstance(node, FileWriteNode):
        node.path = _fold_node(node.path)
        node.value = _fold_node(node.value)
        return node
    if isinstance(node, RandomSeedNode):
        node.seed = _fold_node(node.seed)
        return node
    if isinstance(node, BinOpNode):
        return _fold_binop(node)
    if isinstance(node, FuncCallNode):
        node.args = [_fold_node(arg) for arg in node.args]
        return node
    if isinstance(node, ArgvNode):
        node.index = _fold_node(node.index)
        return node
    if isinstance(node, ArgvStringNode):
        node.index = _fold_node(node.index)
        return node
    if isinstance(node, RandomRangeNode):
        node.low = _fold_node(node.low)
        node.high = _fold_node(node.high)
        return node
    if isinstance(node, FileReadNode):
        node.path = _fold_node(node.path)
        return node
    if isinstance(node, StringLengthNode):
        node.string_expr = _fold_node(node.string_expr)
        return node
    if isinstance(node, StringAtNode):
        node.string_expr = _fold_node(node.string_expr)
        node.index = _fold_node(node.index)
        return node
    if isinstance(node, StringSubNode):
        node.string_expr = _fold_node(node.string_expr)
        node.start = _fold_node(node.start)
        node.length = _fold_node(node.length)
        return node
    if isinstance(node, StringCmpNode):
        node.left = _fold_node(node.left)
        node.right = _fold_node(node.right)
        return node
    if isinstance(node, StringContainsNode):
        node.haystack = _fold_node(node.haystack)
        node.needle = _fold_node(node.needle)
        return node
    if isinstance(node, IntToStringNode):
        node.int_expr = _fold_node(node.int_expr)
        return node
    if isinstance(node, StringToIntNode):
        node.string_expr = _fold_node(node.string_expr)
        return node
    if isinstance(node, CharToIntNode):
        node.char_expr = _fold_node(node.char_expr)
        if isinstance(node.char_expr, CharLiteralNode):
            return _copy_location(node, IntLiteralNode(value=ord(node.char_expr.value)))
        return node
    if isinstance(node, IntToCharNode):
        node.int_expr = _fold_node(node.int_expr)
        value = _int_value(node.int_expr)
        if value is not None:
            return _copy_location(node, CharLiteralNode(value=chr(value & 0xFF)))
        return node
    if isinstance(node, CharToStringNode):
        node.char_expr = _fold_node(node.char_expr)
        return node
    if isinstance(node, IsLetterNode):
        node.char_expr = _fold_node(node.char_expr)
        if isinstance(node.char_expr, CharLiteralNode):
            return _copy_location(node, BoolLiteralNode(value=_ascii_is_letter(node.char_expr.value)))
        return node
    if isinstance(node, IsDigitNode):
        node.char_expr = _fold_node(node.char_expr)
        if isinstance(node.char_expr, CharLiteralNode):
            return _copy_location(node, BoolLiteralNode(value=_ascii_is_digit(node.char_expr.value)))
        return node
    if isinstance(node, CharUpcaseNode):
        node.char_expr = _fold_node(node.char_expr)
        if isinstance(node.char_expr, CharLiteralNode):
            return _copy_location(node, CharLiteralNode(value=_ascii_upcase(node.char_expr.value)))
        return node
    if isinstance(node, CharDowncaseNode):
        node.char_expr = _fold_node(node.char_expr)
        if isinstance(node.char_expr, CharLiteralNode):
            return _copy_location(node, CharLiteralNode(value=_ascii_downcase(node.char_expr.value)))
        return node
    if isinstance(
        node,
        (
            IdentifierNode,
            IntLiteralNode,
            FloatLiteralNode,
            BoolLiteralNode,
            StringLiteralNode,
            CharLiteralNode,
            InputNode,
        ),
    ):
        return node
    return node
