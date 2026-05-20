"""JSON serializers for NekoLang compiler data structures.

Converts Token, AST, Error, Quadruple, and SymbolTable instances into
plain dicts suitable for JSON encoding. Used by the NekoScope API layer.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Callable

from neko.ast_nodes import (
    ASTNode,
    ArgcNode,
    ArgvNode,
    ArgvStringNode,
    ArrayAccessNode,
    ArrayAssignNode,
    ArrayPrintNode,
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
    ExternDeclNode,
    FileReadNode,
    FileWriteNode,
    FloatLiteralNode,
    FuncCallNode,
    FuncDefNode,
    IdentifierNode,
    IfNode,
    ImportNode,
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
    VarDeclNode,
    WhileNode,
)
from neko.build_utils import CompilationResult, generate_code
from neko.dag import build_quadruple_dags
from neko.errors import NekoError, SUGGESTIONS
from neko.quadruple_optimizer import optimize_quadruples
from neko.semantic import Quadruple
from neko.symbol_table import SymbolEntry, SymbolTable
from neko.tokens import Token


# ---------------------------------------------------------------------------
# Token serialization
# ---------------------------------------------------------------------------


def serialize_token(token: Token) -> dict[str, Any]:
    return {
        "type": token.type.value,
        "value": token.value,
        "line": token.line,
        "column": token.column,
    }


def serialize_tokens(tokens: list[Token]) -> list[dict[str, Any]]:
    return [serialize_token(t) for t in tokens]


# ---------------------------------------------------------------------------
# AST node serialization (registry pattern)
# ---------------------------------------------------------------------------

_AST_SERIALIZERS: dict[str, Callable[[ASTNode], dict[str, Any]]] = {}


def _register(node_class: type) -> Callable:
    def decorator(fn: Callable) -> Callable:
        _AST_SERIALIZERS[node_class.__name__] = fn
        return fn

    return decorator


def serialize_ast(node: ASTNode) -> dict[str, Any]:
    handler = _AST_SERIALIZERS.get(type(node).__name__)
    if handler is None:
        raise ValueError(f"No serializer for AST node type: {type(node).__name__}")
    return handler(node)


def _base(node: ASTNode, node_type: str) -> dict[str, Any]:
    return {"nodeType": node_type, "line": node.line, "column": node.column}


def _serialize_params(params: list[tuple[str, str]]) -> list[dict[str, str]]:
    return [{"name": n, "type": t} for n, t in params]


def _serialize_child(node: ASTNode) -> dict[str, Any]:
    return serialize_ast(node)


# --- Fallback for bare ASTNode (default-constructed children) ---

_AST_SERIALIZERS["ASTNode"] = lambda node: {"nodeType": "ASTNode", "line": node.line, "column": node.column}


# --- Leaf nodes ---


@_register(ImportNode)
def _serialize_import(node: ImportNode) -> dict[str, Any]:
    return {**_base(node, "Import"), "path": node.path}


@_register(ProgramNode)
def _serialize_program(node: ProgramNode) -> dict[str, Any]:
    return {
        **_base(node, "Program"),
        "name": node.name,
        "block": _serialize_child(node.block),
        "imports": [_serialize_child(i) for i in node.imports],
    }


@_register(BlockNode)
def _serialize_block(node: BlockNode) -> dict[str, Any]:
    return {
        **_base(node, "Block"),
        "varDecls": [_serialize_child(d) for d in node.var_decls],
        "body": _serialize_child(node.body),
    }


@_register(VarDeclNode)
def _serialize_var_decl(node: VarDeclNode) -> dict[str, Any]:
    return {
        **_base(node, "VarDecl"),
        "variables": _serialize_params(node.variables),
    }


@_register(BeginBlockNode)
def _serialize_begin_block(node: BeginBlockNode) -> dict[str, Any]:
    return {
        **_base(node, "BeginBlock"),
        "statements": [_serialize_child(s) for s in node.statements],
    }


@_register(AssignNode)
def _serialize_assign(node: AssignNode) -> dict[str, Any]:
    return {
        **_base(node, "Assign"),
        "target": node.target,
        "value": _serialize_child(node.value),
    }


@_register(IfNode)
def _serialize_if(node: IfNode) -> dict[str, Any]:
    return {
        **_base(node, "If"),
        "condition": _serialize_child(node.condition),
        "thenBranch": _serialize_child(node.then_branch),
        "elseBranch": _serialize_child(node.else_branch),
    }


@_register(WhileNode)
def _serialize_while(node: WhileNode) -> dict[str, Any]:
    return {
        **_base(node, "While"),
        "condition": _serialize_child(node.condition),
        "body": _serialize_child(node.body),
    }


@_register(PrintNode)
def _serialize_print(node: PrintNode) -> dict[str, Any]:
    return {**_base(node, "Print"), "value": _serialize_child(node.value)}


@_register(BinOpNode)
def _serialize_binop(node: BinOpNode) -> dict[str, Any]:
    return {
        **_base(node, "BinOp"),
        "op": node.op,
        "left": _serialize_child(node.left),
        "right": _serialize_child(node.right),
    }


@_register(IdentifierNode)
def _serialize_identifier(node: IdentifierNode) -> dict[str, Any]:
    return {**_base(node, "Identifier"), "name": node.name}


@_register(IntLiteralNode)
def _serialize_int_literal(node: IntLiteralNode) -> dict[str, Any]:
    return {**_base(node, "IntLiteral"), "value": node.value}


@_register(FloatLiteralNode)
def _serialize_float_literal(node: FloatLiteralNode) -> dict[str, Any]:
    return {**_base(node, "FloatLiteral"), "value": node.value}


@_register(BoolLiteralNode)
def _serialize_bool_literal(node: BoolLiteralNode) -> dict[str, Any]:
    return {**_base(node, "BoolLiteral"), "value": node.value}


@_register(StringLiteralNode)
def _serialize_string_literal(node: StringLiteralNode) -> dict[str, Any]:
    return {**_base(node, "StringLiteral"), "value": node.value}


@_register(CharLiteralNode)
def _serialize_char_literal(node: CharLiteralNode) -> dict[str, Any]:
    return {**_base(node, "CharLiteral"), "value": node.value}


@_register(FuncDefNode)
def _serialize_func_def(node: FuncDefNode) -> dict[str, Any]:
    return {
        **_base(node, "FuncDef"),
        "name": node.name,
        "params": _serialize_params(node.params),
        "returnType": node.return_type,
        "body": _serialize_child(node.body),
    }


@_register(ExternDeclNode)
def _serialize_extern_decl(node: ExternDeclNode) -> dict[str, Any]:
    return {
        **_base(node, "ExternDecl"),
        "name": node.name,
        "paramTypes": list(node.param_types),
        "returnType": node.return_type,
    }


@_register(LambdaDefNode)
def _serialize_lambda_def(node: LambdaDefNode) -> dict[str, Any]:
    return {
        **_base(node, "LambdaDef"),
        "name": node.name,
        "params": _serialize_params(node.params),
        "returnType": node.return_type,
        "body": _serialize_child(node.body),
    }


@_register(FuncCallNode)
def _serialize_func_call(node: FuncCallNode) -> dict[str, Any]:
    return {
        **_base(node, "FuncCall"),
        "name": node.name,
        "args": [_serialize_child(a) for a in node.args],
    }


@_register(ReturnNode)
def _serialize_return(node: ReturnNode) -> dict[str, Any]:
    return {**_base(node, "Return"), "value": _serialize_child(node.value)}


@_register(ArrayAccessNode)
def _serialize_array_access(node: ArrayAccessNode) -> dict[str, Any]:
    return {
        **_base(node, "ArrayAccess"),
        "name": node.name,
        "index": _serialize_child(node.index),
    }


@_register(ArrayAssignNode)
def _serialize_array_assign(node: ArrayAssignNode) -> dict[str, Any]:
    return {
        **_base(node, "ArrayAssign"),
        "name": node.name,
        "index": _serialize_child(node.index),
        "value": _serialize_child(node.value),
    }


@_register(ArrayPrintNode)
def _serialize_array_print(node: ArrayPrintNode) -> dict[str, Any]:
    return {
        **_base(node, "ArrayPrint"),
        "name": node.name,
        "index": _serialize_child(node.index),
    }


@_register(ArgcNode)
def _serialize_argc(node: ArgcNode) -> dict[str, Any]:
    return _base(node, "Argc")


@_register(ArgvNode)
def _serialize_argv(node: ArgvNode) -> dict[str, Any]:
    return {
        **_base(node, "Argv"),
        "valueType": node.value_type,
        "index": _serialize_child(node.index),
    }


@_register(InputNode)
def _serialize_input(node: InputNode) -> dict[str, Any]:
    return {**_base(node, "Input"), "valueType": node.value_type}


@_register(RandomSeedNode)
def _serialize_random_seed(node: RandomSeedNode) -> dict[str, Any]:
    return {**_base(node, "RandomSeed"), "seed": _serialize_child(node.seed)}


@_register(RandomRangeNode)
def _serialize_random_range(node: RandomRangeNode) -> dict[str, Any]:
    return {
        **_base(node, "RandomRange"),
        "low": _serialize_child(node.low),
        "high": _serialize_child(node.high),
    }


@_register(FileReadNode)
def _serialize_file_read(node: FileReadNode) -> dict[str, Any]:
    return {
        **_base(node, "FileRead"),
        "valueType": node.value_type,
        "path": _serialize_child(node.path),
    }


@_register(FileWriteNode)
def _serialize_file_write(node: FileWriteNode) -> dict[str, Any]:
    return {
        **_base(node, "FileWrite"),
        "valueType": node.value_type,
        "path": _serialize_child(node.path),
        "value": _serialize_child(node.value),
    }


@_register(StringLengthNode)
def _serialize_string_length(node: StringLengthNode) -> dict[str, Any]:
    return {**_base(node, "StringLength"), "stringExpr": _serialize_child(node.string_expr)}


@_register(StringAtNode)
def _serialize_string_at(node: StringAtNode) -> dict[str, Any]:
    return {
        **_base(node, "StringAt"),
        "stringExpr": _serialize_child(node.string_expr),
        "index": _serialize_child(node.index),
    }


@_register(StringSubNode)
def _serialize_string_sub(node: StringSubNode) -> dict[str, Any]:
    return {
        **_base(node, "StringSub"),
        "stringExpr": _serialize_child(node.string_expr),
        "start": _serialize_child(node.start),
        "length": _serialize_child(node.length),
    }


@_register(StringCmpNode)
def _serialize_string_cmp(node: StringCmpNode) -> dict[str, Any]:
    return {
        **_base(node, "StringCmp"),
        "left": _serialize_child(node.left),
        "right": _serialize_child(node.right),
    }


@_register(StringContainsNode)
def _serialize_string_contains(node: StringContainsNode) -> dict[str, Any]:
    return {
        **_base(node, "StringContains"),
        "haystack": _serialize_child(node.haystack),
        "needle": _serialize_child(node.needle),
    }


@_register(IntToStringNode)
def _serialize_int_to_string(node: IntToStringNode) -> dict[str, Any]:
    return {**_base(node, "IntToString"), "intExpr": _serialize_child(node.int_expr)}


@_register(StringToIntNode)
def _serialize_string_to_int(node: StringToIntNode) -> dict[str, Any]:
    return {**_base(node, "StringToInt"), "stringExpr": _serialize_child(node.string_expr)}


@_register(ArgvStringNode)
def _serialize_argv_string(node: ArgvStringNode) -> dict[str, Any]:
    return {**_base(node, "ArgvString"), "index": _serialize_child(node.index)}


@_register(CharToIntNode)
def _serialize_char_to_int(node: CharToIntNode) -> dict[str, Any]:
    return {**_base(node, "CharToInt"), "charExpr": _serialize_child(node.char_expr)}


@_register(IntToCharNode)
def _serialize_int_to_char(node: IntToCharNode) -> dict[str, Any]:
    return {**_base(node, "IntToChar"), "intExpr": _serialize_child(node.int_expr)}


@_register(CharToStringNode)
def _serialize_char_to_string(node: CharToStringNode) -> dict[str, Any]:
    return {**_base(node, "CharToString"), "charExpr": _serialize_child(node.char_expr)}


@_register(IsLetterNode)
def _serialize_is_letter(node: IsLetterNode) -> dict[str, Any]:
    return {**_base(node, "IsLetter"), "charExpr": _serialize_child(node.char_expr)}


@_register(IsDigitNode)
def _serialize_is_digit(node: IsDigitNode) -> dict[str, Any]:
    return {**_base(node, "IsDigit"), "charExpr": _serialize_child(node.char_expr)}


@_register(CharUpcaseNode)
def _serialize_char_upcase(node: CharUpcaseNode) -> dict[str, Any]:
    return {**_base(node, "CharUpcase"), "charExpr": _serialize_child(node.char_expr)}


@_register(CharDowncaseNode)
def _serialize_char_downcase(node: CharDowncaseNode) -> dict[str, Any]:
    return {**_base(node, "CharDowncase"), "charExpr": _serialize_child(node.char_expr)}


# ---------------------------------------------------------------------------
# Error serialization
# ---------------------------------------------------------------------------


def serialize_error(err: NekoError) -> dict[str, Any]:
    suggestion = ""
    if err.suggestion_key and err.suggestion_key in SUGGESTIONS:
        suggestion = SUGGESTIONS[err.suggestion_key]
    return {
        "phase": err.phase,
        "message": err.message,
        "line": err.line,
        "column": err.column,
        "sourceLine": err.source_line,
        "suggestion": suggestion,
    }


def serialize_errors(errors: list[NekoError]) -> list[dict[str, Any]]:
    return [serialize_error(e) for e in errors]


# ---------------------------------------------------------------------------
# Quadruple serialization
# ---------------------------------------------------------------------------


def serialize_quadruple(q: Quadruple) -> dict[str, str]:
    return {"op": q.op, "ob1": q.ob1, "ob2": q.ob2, "t": q.t}


def serialize_quadruples(quads: list[Quadruple]) -> list[dict[str, str]]:
    return [serialize_quadruple(q) for q in quads]


def _quadruple_rows_equal(left: list[Quadruple], right: list[Quadruple]) -> bool:
    return [serialize_quadruple(q) for q in left] == [serialize_quadruple(q) for q in right]


def _quadruple_row_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (row["op"], row["ob1"], row["ob2"], row["t"])


def _step_row_changes(
    before: list[Quadruple],
    after: list[Quadruple],
) -> tuple[list[dict[str, str]], list[dict[str, dict[str, str]]]]:
    before_rows = serialize_quadruples(before)
    after_rows = serialize_quadruples(after)
    matcher = SequenceMatcher(
        None,
        [_quadruple_row_key(row) for row in before_rows],
        [_quadruple_row_key(row) for row in after_rows],
        autojunk=False,
    )
    removed: list[dict[str, str]] = []
    rewritten: list[dict[str, dict[str, str]]] = []

    for tag, before_start, before_end, after_start, after_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "delete":
            removed.extend(before_rows[before_start:before_end])
            continue
        if tag == "replace":
            before_slice = before_rows[before_start:before_end]
            after_slice = after_rows[after_start:after_end]
            pair_count = min(len(before_slice), len(after_slice))
            rewritten.extend(
                {"before": before_slice[index], "after": after_slice[index]}
                for index in range(pair_count)
            )
            removed.extend(before_slice[pair_count:])

    return removed, rewritten


def _optimization_step(
    name: str,
    detail: str,
    before: list[Quadruple],
    after: list[Quadruple],
    changed: bool,
) -> dict[str, Any]:
    removed_rows, rewritten_rows = _step_row_changes(before, after)
    return {
        "name": name,
        "detail": detail,
        "beforeCount": len(before),
        "afterCount": len(after),
        "changed": changed,
        "beforeRows": serialize_quadruples(before),
        "afterRows": serialize_quadruples(after),
        "removedRows": removed_rows,
        "rewrittenRows": rewritten_rows,
    }


def serialize_quadruple_optimization(result: CompilationResult) -> dict[str, Any]:
    initial = serialize_quadruples(result.analyzer.quadruples)
    base = {
        "level": "O1",
        "source": "Quadruple DAG optimizer",
        "enabled": not result.analyzer.errors,
        "changed": False,
        "beforeCount": len(result.analyzer.quadruples),
        "afterCount": len(result.analyzer.quadruples),
        "initial": initial,
        "optimized": initial,
        "initialConstants": dict(result.analyzer.symbol_table.const_table),
        "optimizedConstants": dict(result.analyzer.symbol_table.const_table),
        "steps": [],
        "diagnostics": [],
    }

    if result.analyzer.errors:
        base["steps"] = [
            {
                "name": "跳过优化",
                "detail": "语义分析存在错误，优化结果可能不可靠。",
                "beforeCount": len(result.analyzer.quadruples),
                "afterCount": len(result.analyzer.quadruples),
                "changed": False,
            }
        ]
        return base

    try:
        optimized_result = optimize_quadruples(
            result.analyzer.quadruples,
            result.analyzer.symbol_table.const_table,
        )
    except Exception as exc:
        base["enabled"] = False
        base["diagnostics"] = [
            {
                "phase": "Optimization",
                "message": str(exc),
                "line": 0,
                "column": 0,
                "sourceLine": "",
                "suggestion": "",
            }
        ]
        base["steps"] = [
            {
                "name": "优化失败",
                "detail": "O1 优化未能生成可展示的四元式结果。",
                "beforeCount": len(result.analyzer.quadruples),
                "afterCount": len(result.analyzer.quadruples),
                "changed": False,
            }
        ]
        return base

    optimized = serialize_quadruples(optimized_result.quadruples)
    changed = not _quadruple_rows_equal(result.analyzer.quadruples, optimized_result.quadruples)
    base.update(
        {
            "changed": changed,
            "afterCount": len(optimized_result.quadruples),
            "optimized": optimized,
            "optimizedConstants": dict(optimized_result.constants),
            "diagnostics": [],
            "steps": [
                _optimization_step(
                    "读取初始四元式",
                    "语义分析先生成未优化的线性中间表示。",
                    result.analyzer.quadruples,
                    result.analyzer.quadruples,
                    False,
                ),
                _optimization_step(
                    "O1 常量折叠",
                    "在四元式上折叠常量算术、比较和等值判断。",
                    result.analyzer.quadruples,
                    optimized_result.folded_quadruples,
                    optimized_result.folded_count > 0,
                ),
                _optimization_step(
                    "O1 公共子表达式消除",
                    "按基本块的 DAG 值编号复用重复计算结果。",
                    optimized_result.folded_quadruples,
                    optimized_result.cse_quadruples,
                    optimized_result.cse_count > 0,
                ),
                _optimization_step(
                    "删除死临时赋值",
                    "移除折叠和复用后不再被读取的临时结果。",
                    optimized_result.cse_quadruples,
                    optimized_result.pruned_quadruples,
                    optimized_result.removed_temp_count > 0,
                ),
            ],
        }
    )
    return base


# ---------------------------------------------------------------------------
# SymbolTable serialization
# ---------------------------------------------------------------------------


def serialize_symbol_entry(entry: SymbolEntry) -> dict[str, Any]:
    return {
        "name": entry.name,
        "type": entry.type,
        "category": entry.cat,
        "address": entry.addr,
        "addressName": entry.addr_name,
        "scope": entry.scope,
    }


def serialize_symbol_table(table: SymbolTable) -> dict[str, Any]:
    return {
        "entries": [serialize_symbol_entry(e) for e in table.entries],
        "constants": dict(table.const_table),
    }


def _dag_operand_labels(table: SymbolTable) -> dict[str, str]:
    labels: dict[str, str] = {}
    for entry in table.entries:
        if entry.addr_name:
            labels[entry.addr_name] = entry.name
    for value, address in table.const_table.items():
        labels[str(address)] = str(value)
    return labels


# ---------------------------------------------------------------------------
# Full compilation result serialization
# ---------------------------------------------------------------------------


def serialize_compilation_result(
    result: CompilationResult,
    backend: str = "auto",
) -> dict[str, Any]:
    assembly = ""
    if not result.analyzer.errors:
        try:
            assembly = generate_code(result.ast, backend=backend).text
        except Exception:
            assembly = ""

    return {
        "source": result.source,
        "tokens": serialize_tokens(result.tokens),
        "ast": serialize_ast(result.ast),
        "symbols": serialize_symbol_table(result.analyzer.symbol_table),
        "quadruples": serialize_quadruples(result.analyzer.quadruples),
        "quadrupleDag": build_quadruple_dags(
            result.analyzer.quadruples,
            labels=_dag_operand_labels(result.analyzer.symbol_table),
        ),
        "quadrupleOptimization": serialize_quadruple_optimization(result),
        "assembly": assembly,
        "errors": serialize_errors(result.analyzer.errors),
        "backend": backend,
    }
