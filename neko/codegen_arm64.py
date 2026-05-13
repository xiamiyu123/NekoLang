"""ARM64 assembly code generator for NekoLang on macOS."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from .ast_nodes import (
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
    FileReadNode,
    FileWriteNode,
    FloatLiteralNode,
    FuncCallNode,
    FuncDefNode,
    ExternDeclNode,
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
from .name_mangling import mangle_neko_function_name


CMP_OPS = {
    "<": "lt",
    ">": "gt",
    "=": "eq",
    "<=": "le",
    ">=": "ge",
    "!=": "ne",
}

ARITH_OPS = {
    "+": "add",
    "-": "sub",
    "*": "mul",
    "/": "sdiv",
}

FLOAT_ARITH_OPS = {
    "+": "fadd",
    "-": "fsub",
    "*": "fmul",
    "/": "fdiv",
}

FLOAT_ARG_REGS = [f"d{i}" for i in range(8)]
INT_ARG_REGS = [f"x{i}" for i in range(8)]
EXPR_TEMP_SLOTS = 8
CALL_ARG_SLOTS = 16
SCRATCH_SLOT_COUNT = EXPR_TEMP_SLOTS + CALL_ARG_SLOTS
CALL_SCRATCH_SIZE = SCRATCH_SLOT_COUNT * 8


def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def _type_size(type_str: str) -> int:
    if type_str == "int":
        return 4
    if type_str == "float":
        return 8
    if type_str == "char":
        return 1
    if type_str == "bool":
        return 1
    if type_str == "string":
        return 8
    if type_str == "pointer":
        return 8
    if type_str.startswith("(func"):
        return 8
    if type_str.startswith("(array"):
        elem_type = _array_element_type(type_str)
        count = _array_length(type_str)
        return _type_size(elem_type) * count
    return 8


def _type_alignment(type_str: str) -> int:
    if type_str.startswith("(array"):
        return max(1, min(_type_size(_array_element_type(type_str)), 8))
    return 8


def _array_element_type(type_str: str) -> str:
    parts = type_str.rstrip(")").split()
    return parts[1] if len(parts) > 1 else "int"


def _array_length(type_str: str) -> int:
    parts = type_str.rstrip(")").split()
    return int(parts[2]) if len(parts) > 2 else 1


def _parse_func_type_str(type_str: str) -> tuple[list[str], str]:
    inner = type_str[len("(func "):-1]
    paren_start = inner.index("(")
    paren_end = inner.index(")")
    param_str = inner[paren_start + 1:paren_end].strip()
    param_types = param_str.split() if param_str else []
    ret_type = inner[paren_end + 1:].strip()
    return param_types, ret_type


def _func_type_from_node(node: FuncDefNode | LambdaDefNode) -> str:
    params = " ".join(type_str for _, type_str in node.params)
    return f"(func ({params}) {node.return_type})"


def _is_float_type(type_str: str) -> bool:
    return type_str == "float"


def _is_string_type(type_str: str) -> bool:
    return type_str == "string"


def _is_char_type(type_str: str) -> bool:
    return type_str == "char"


def _is_bool_type(type_str: str) -> bool:
    return type_str == "bool"


def _is_int_type(type_str: str) -> bool:
    return type_str == "int"


def _is_pointer_type(type_str: str) -> bool:
    return type_str in {"string", "pointer"} or type_str.startswith("(func")


def _is_null_pointer_literal(node: ASTNode) -> bool:
    return isinstance(node, IntLiteralNode) and node.value == 0


def _asm_escape_string(value: str) -> str:
    chunks: list[str] = []
    for b in value.encode("utf-8"):
        ch = chr(b)
        if ch == "\\":
            chunks.append("\\\\")
        elif ch == '"':
            chunks.append('\\"')
        elif ch == "\n":
            chunks.append("\\n")
        elif ch == "\t":
            chunks.append("\\t")
        elif ch == "\r":
            chunks.append("\\r")
        elif 32 <= b <= 126:
            chunks.append(ch)
        else:
            chunks.append(f"\\x{b:02x}")
    return "".join(chunks)


@dataclass
class FrameLayout:
    frame_size: int
    save_area_size: int
    var_offsets: dict[str, int]
    var_types: dict[str, str]
    call_scratch_base: int


class ARM64Codegen:
    """Generate Darwin ARM64 assembly for NekoLang."""

    def __init__(self):
        self.lines: list[str] = []
        self.cstring_pool: dict[str, str] = {}
        self.float_pool: dict[int, str] = {}
        self.label_counter = 0
        self.function_nodes: dict[str, FuncDefNode | LambdaDefNode] = {}
        self.extern_nodes: dict[str, ExternDeclNode] = {}
        self.var_types: dict[str, str] = {}
        self.var_offsets: dict[str, int] = {}
        self.var_slot_kinds: dict[str, str] = {}
        self.current_return_type: str | None = None
        self.current_epilogue_label: str | None = None
        self.current_function_name: str | None = None
        self.is_main = False
        self.frame_layout: FrameLayout | None = None
        self.expr_temp_depth = 0

    def generate(self, ast: ProgramNode) -> str:
        self.lines = []
        self._emit(".section\t__TEXT,__text,regular,pure_instructions")
        self.function_nodes = self._collect_function_nodes(ast.block.body)
        self.extern_nodes = self._collect_extern_nodes(ast.block.body)
        self._gen_functions()
        self._gen_program(ast)
        self._emit_literal_sections()
        self._emit(".subsections_via_symbols")
        return "\n".join(self.lines) + "\n"

    def _emit(self, line: str = ""):
        self.lines.append(line)

    def _new_label(self, prefix: str) -> str:
        label = f"L{prefix}_{self.label_counter}"
        self.label_counter += 1
        return label

    def _function_symbol(self, name: str) -> str:
        return f"_{name}"

    def _neko_function_symbol(self, name: str) -> str:
        return self._function_symbol(mangle_neko_function_name(name))

    def _collect_function_nodes(self, node: ASTNode) -> dict[str, FuncDefNode | LambdaDefNode]:
        found: dict[str, FuncDefNode | LambdaDefNode] = {}

        def walk(stmt: ASTNode):
            if isinstance(stmt, FuncDefNode):
                found.setdefault(stmt.name, stmt)
                walk(stmt.body)
            elif isinstance(stmt, LambdaDefNode):
                found.setdefault(stmt.name, stmt)
                walk(stmt.body)
            elif isinstance(stmt, ExternDeclNode):
                return
            elif isinstance(stmt, AssignNode):
                walk(stmt.value)
            elif isinstance(stmt, BeginBlockNode):
                for inner in stmt.statements:
                    walk(inner)
            elif isinstance(stmt, IfNode):
                walk(stmt.condition)
                walk(stmt.then_branch)
                walk(stmt.else_branch)
            elif isinstance(stmt, WhileNode):
                walk(stmt.condition)
                walk(stmt.body)
            elif isinstance(stmt, PrintNode):
                walk(stmt.value)
            elif isinstance(stmt, ReturnNode):
                walk(stmt.value)
            elif isinstance(stmt, ArrayAssignNode):
                walk(stmt.index)
                walk(stmt.value)
            elif isinstance(stmt, ArrayPrintNode):
                walk(stmt.index)
            elif isinstance(stmt, FileWriteNode):
                walk(stmt.path)
                walk(stmt.value)
            elif isinstance(stmt, RandomSeedNode):
                walk(stmt.seed)
            elif isinstance(stmt, BinOpNode):
                walk(stmt.left)
                walk(stmt.right)
            elif isinstance(stmt, FuncCallNode):
                for arg in stmt.args:
                    walk(arg)
            elif isinstance(stmt, ArrayAccessNode):
                walk(stmt.index)
            elif isinstance(stmt, ArgvNode):
                walk(stmt.index)
            elif isinstance(stmt, ArgvStringNode):
                walk(stmt.index)
            elif isinstance(stmt, RandomRangeNode):
                walk(stmt.low)
                walk(stmt.high)
            elif isinstance(stmt, FileReadNode):
                walk(stmt.path)
            elif isinstance(stmt, StringLengthNode):
                walk(stmt.string_expr)
            elif isinstance(stmt, StringAtNode):
                walk(stmt.string_expr)
                walk(stmt.index)
            elif isinstance(stmt, StringSubNode):
                walk(stmt.string_expr)
                walk(stmt.start)
                walk(stmt.length)
            elif isinstance(stmt, StringCmpNode):
                walk(stmt.left)
                walk(stmt.right)
            elif isinstance(stmt, StringContainsNode):
                walk(stmt.haystack)
                walk(stmt.needle)
            elif isinstance(stmt, IntToStringNode):
                walk(stmt.int_expr)
            elif isinstance(stmt, StringToIntNode):
                walk(stmt.string_expr)
            elif isinstance(stmt, CharToIntNode):
                walk(stmt.char_expr)
            elif isinstance(stmt, IntToCharNode):
                walk(stmt.int_expr)
            elif isinstance(stmt, CharToStringNode):
                walk(stmt.char_expr)
            elif isinstance(stmt, IsLetterNode):
                walk(stmt.char_expr)
            elif isinstance(stmt, IsDigitNode):
                walk(stmt.char_expr)
            elif isinstance(stmt, CharUpcaseNode):
                walk(stmt.char_expr)
            elif isinstance(stmt, CharDowncaseNode):
                walk(stmt.char_expr)

        walk(node)
        return found

    def _collect_extern_nodes(self, node: ASTNode) -> dict[str, ExternDeclNode]:
        found: dict[str, ExternDeclNode] = {}

        def walk(stmt: ASTNode):
            if isinstance(stmt, ExternDeclNode):
                found.setdefault(stmt.name, stmt)
            elif isinstance(stmt, FuncDefNode):
                walk(stmt.body)
            elif isinstance(stmt, LambdaDefNode):
                walk(stmt.body)
            elif isinstance(stmt, AssignNode):
                walk(stmt.value)
            elif isinstance(stmt, BeginBlockNode):
                for inner in stmt.statements:
                    walk(inner)
            elif isinstance(stmt, IfNode):
                walk(stmt.condition)
                walk(stmt.then_branch)
                walk(stmt.else_branch)
            elif isinstance(stmt, WhileNode):
                walk(stmt.condition)
                walk(stmt.body)

        walk(node)
        return found

    def _compute_frame_layout(
        self,
        var_pairs: list[tuple[str, str]],
        save_main_args: bool,
    ) -> FrameLayout:
        save_area_size = 48 if save_main_args else 32
        current = save_area_size - 16
        var_offsets: dict[str, int] = {}
        var_types: dict[str, str] = {}

        for name, type_str in var_pairs:
            align = _type_alignment(type_str)
            current = _align(current, align)
            size = _align(8 if not type_str.startswith("(array") else _type_size(type_str), align)
            current += size
            var_offsets[name] = current
            var_types[name] = type_str

        current += CALL_SCRATCH_SIZE
        frame_size = _align(16 + current, 16)
        return FrameLayout(
            frame_size=frame_size,
            save_area_size=save_area_size,
            var_offsets=var_offsets,
            var_types=var_types,
            call_scratch_base=current - CALL_SCRATCH_SIZE,
        )

    def _emit_function_prologue(
        self,
        name: str,
        frame_size: int,
        save_main_args: bool,
        *,
        mangle_name: bool = False,
    ):
        symbol = self._neko_function_symbol(name) if mangle_name else self._function_symbol(name)
        self._emit(f".globl\t{symbol}")
        self._emit(".p2align\t2")
        self._emit(f"{symbol}:")
        self._emit(f"\tsub\tsp, sp, #{frame_size}")
        self._emit(f"\tstp\tx29, x30, [sp, #{frame_size - 16}]")
        if save_main_args:
            self._emit(f"\tstr\tx20, [sp, #{frame_size - 24}]")
            self._emit(f"\tstr\tx21, [sp, #{frame_size - 32}]")
            self._emit(f"\tstr\tx19, [sp, #{frame_size - 40}]")
            self._emit(f"\tstr\td8, [sp, #{frame_size - 48}]")
        else:
            self._emit(f"\tstr\tx19, [sp, #{frame_size - 24}]")
            self._emit(f"\tstr\td8, [sp, #{frame_size - 32}]")
        self._emit(f"\tadd\tx29, sp, #{frame_size - 16}")
        if save_main_args:
            self._emit("\tmov\tx20, x0")
            self._emit("\tmov\tx21, x1")

    def _emit_function_epilogue(self, frame_size: int, save_main_args: bool):
        if save_main_args:
            self._emit(f"\tldr\td8, [sp, #{frame_size - 48}]")
            self._emit(f"\tldr\tx19, [sp, #{frame_size - 40}]")
            self._emit(f"\tldr\tx21, [sp, #{frame_size - 32}]")
            self._emit(f"\tldr\tx20, [sp, #{frame_size - 24}]")
        else:
            self._emit(f"\tldr\td8, [sp, #{frame_size - 32}]")
            self._emit(f"\tldr\tx19, [sp, #{frame_size - 24}]")
        self._emit(f"\tldp\tx29, x30, [sp, #{frame_size - 16}]")
        self._emit(f"\tadd\tsp, sp, #{frame_size}")
        self._emit("\tret")

    def _emit_var_zero_init(self, name: str, type_str: str):
        if type_str.startswith("(array"):
            return
        self._materialize_var_address(name, "x9")
        if _is_float_type(type_str) or _is_pointer_type(type_str):
            self._emit("\tstr\txzr, [x9]")
        elif _is_char_type(type_str) or _is_bool_type(type_str):
            self._emit("\tstrb\twzr, [x9]")
        else:
            self._emit("\tstr\twzr, [x9]")

    def _materialize_offset(self, reg: str, value: int):
        if value <= 4095:
            self._emit(f"\tmov\t{reg}, #{value}")
            return
        self._emit_load_imm(reg, value, bits=64)

    def _materialize_var_address(self, name: str, reg: str = "x9"):
        offset = self.var_offsets[name]
        if offset <= 4095:
            self._emit(f"\tsub\t{reg}, x29, #{offset}")
            return
        self._materialize_offset("x10", offset)
        self._emit(f"\tsub\t{reg}, x29, x10")

    def _scratch_slot_offset(self, index: int) -> int:
        if not self.frame_layout:
            raise RuntimeError("frame layout is not available")
        return self.frame_layout.call_scratch_base + 8 * (EXPR_TEMP_SLOTS + index + 1)

    def _expr_slot_offset(self, index: int) -> int:
        if not self.frame_layout:
            raise RuntimeError("frame layout is not available")
        return self.frame_layout.call_scratch_base + 8 * (index + 1)

    def _emit_store_scratch(self, slot: int, type_str: str):
        self._emit_store_to_offset(self._scratch_slot_offset(slot), type_str, base="x29")

    def _emit_load_scratch(self, slot: int, type_str: str, target_reg: str | None = None):
        self._emit_load_from_offset(self._scratch_slot_offset(slot), type_str, base="x29", target_reg=target_reg)

    def _push_expr_temp(self, type_str: str) -> int:
        slot = self.expr_temp_depth
        if slot >= EXPR_TEMP_SLOTS:
            raise RuntimeError("表达式嵌套过深：超出临时槽上限")
        self.expr_temp_depth += 1
        self._emit_store_to_offset(self._expr_slot_offset(slot), type_str, base="x29")
        return slot

    def _load_expr_temp(self, slot: int, type_str: str, target_reg: str | None = None):
        self._emit_load_from_offset(self._expr_slot_offset(slot), type_str, base="x29", target_reg=target_reg)

    def _pop_expr_temp(self):
        self.expr_temp_depth -= 1

    def _emit_store_to_offset(self, offset: int, type_str: str, base: str = "x29"):
        self._materialize_offset("x11", offset)
        self._emit(f"\tsub\tx10, {base}, x11")
        if _is_float_type(type_str):
            self._emit("\tstr\td0, [x10]")
        elif _is_char_type(type_str) or _is_bool_type(type_str):
            self._emit("\tstrb\tw0, [x10]")
        elif _is_pointer_type(type_str):
            self._emit("\tstr\tx0, [x10]")
        else:
            self._emit("\tstr\tw0, [x10]")

    def _emit_load_from_offset(
        self,
        offset: int,
        type_str: str,
        base: str = "x29",
        target_reg: str | None = None,
    ):
        self._materialize_offset("x11", offset)
        self._emit(f"\tsub\tx10, {base}, x11")
        if _is_float_type(type_str):
            reg = target_reg or "d0"
            self._emit(f"\tldr\t{reg}, [x10]")
        elif _is_char_type(type_str) or _is_bool_type(type_str):
            reg = target_reg or "w0"
            self._emit(f"\tldrb\t{reg}, [x10]")
        elif _is_pointer_type(type_str):
            reg = target_reg or "x0"
            self._emit(f"\tldr\t{reg}, [x10]")
        else:
            reg = target_reg or "w0"
            self._emit(f"\tldr\t{reg}, [x10]")

    def _gen_functions(self):
        for node in self.function_nodes.values():
            self._gen_function(node)

    def _gen_function(self, node: FuncDefNode | LambdaDefNode):
        saved_types = self.var_types
        saved_offsets = self.var_offsets
        saved_slots = self.var_slot_kinds
        saved_return_type = self.current_return_type
        saved_epilogue = self.current_epilogue_label
        saved_name = self.current_function_name
        saved_is_main = self.is_main
        saved_layout = self.frame_layout

        self.current_return_type = node.return_type
        self.current_epilogue_label = self._new_label("epilogue")
        self.current_function_name = node.name
        self.is_main = False
        self.frame_layout = self._compute_frame_layout(node.params, save_main_args=False)
        self.var_types = dict(self.frame_layout.var_types)
        self.var_offsets = dict(self.frame_layout.var_offsets)
        self.var_slot_kinds = {name: type_str for name, type_str in node.params}
        self.expr_temp_depth = 0

        self._emit_function_prologue(node.name, self.frame_layout.frame_size, save_main_args=False, mangle_name=True)
        for name, type_str in node.params:
            self._emit_var_zero_init(name, type_str)

        self._spill_params(node.params)
        self._gen_statement(node.body)

        if not self._statement_guarantees_return(node.body):
            self._emit_default_return(node.return_type)
            self._emit(f"\tb\t{self.current_epilogue_label}")

        self._emit(f"{self.current_epilogue_label}:")
        self._emit_function_epilogue(self.frame_layout.frame_size, save_main_args=False)
        self._emit()

        self.var_types = saved_types
        self.var_offsets = saved_offsets
        self.var_slot_kinds = saved_slots
        self.current_return_type = saved_return_type
        self.current_epilogue_label = saved_epilogue
        self.current_function_name = saved_name
        self.is_main = saved_is_main
        self.frame_layout = saved_layout

    def _spill_params(self, params: list[tuple[str, str]]):
        int_index = 0
        float_index = 0
        for name, type_str in params:
            if _is_float_type(type_str):
                if float_index >= len(FLOAT_ARG_REGS):
                    raise RuntimeError("函数参数过多：float 参数超过 8 个")
                reg = FLOAT_ARG_REGS[float_index]
                self._materialize_var_address(name, "x9")
                self._emit(f"\tstr\t{reg}, [x9]")
                float_index += 1
            else:
                if int_index >= len(INT_ARG_REGS):
                    raise RuntimeError("函数参数过多：整数类参数超过 8 个")
                addr_reg = "x9"
                self._materialize_var_address(name, addr_reg)
                src_reg = f"w{int_index}"
                src_xreg = f"x{int_index}"
                if _is_char_type(type_str) or _is_bool_type(type_str):
                    self._emit(f"\tstrb\t{src_reg}, [{addr_reg}]")
                elif _is_pointer_type(type_str):
                    self._emit(f"\tstr\t{src_xreg}, [{addr_reg}]")
                else:
                    self._emit(f"\tstr\t{src_reg}, [{addr_reg}]")
                int_index += 1

    def _gen_program(self, node: ProgramNode):
        saved_types = self.var_types
        saved_offsets = self.var_offsets
        saved_slots = self.var_slot_kinds
        saved_return_type = self.current_return_type
        saved_epilogue = self.current_epilogue_label
        saved_name = self.current_function_name
        saved_is_main = self.is_main
        saved_layout = self.frame_layout

        pairs: list[tuple[str, str]] = []
        for decl in node.block.var_decls:
            pairs.extend(decl.variables)

        self.current_return_type = "int"
        self.current_epilogue_label = self._new_label("epilogue")
        self.current_function_name = "main"
        self.is_main = True
        self.frame_layout = self._compute_frame_layout(pairs, save_main_args=True)
        self.var_types = dict(self.frame_layout.var_types)
        self.var_offsets = dict(self.frame_layout.var_offsets)
        self.var_slot_kinds = {name: type_str for name, type_str in pairs}
        self.expr_temp_depth = 0

        self._emit_function_prologue("main", self.frame_layout.frame_size, save_main_args=True)
        self._gen_block(node.block)
        self._emit("\tmov\tw0, #0")
        self._emit(f"{self.current_epilogue_label}:")
        self._emit_function_epilogue(self.frame_layout.frame_size, save_main_args=True)
        self._emit()

        self.var_types = saved_types
        self.var_offsets = saved_offsets
        self.var_slot_kinds = saved_slots
        self.current_return_type = saved_return_type
        self.current_epilogue_label = saved_epilogue
        self.current_function_name = saved_name
        self.is_main = saved_is_main
        self.frame_layout = saved_layout

    def _gen_block(self, node: BlockNode):
        for decl in node.var_decls:
            self._gen_var_decl(decl.variables)
        self._gen_begin_block(node.body)

    def _gen_var_decl(self, variables: list[tuple[str, str]]):
        for name, type_str in variables:
            self._emit_var_zero_init(name, type_str)

    def _gen_begin_block(self, node: BeginBlockNode):
        for stmt in node.statements:
            self._gen_statement(stmt)

    def _gen_statement(self, node: ASTNode):
        if isinstance(node, AssignNode):
            self._gen_assign(node)
        elif isinstance(node, IfNode):
            self._gen_if(node)
        elif isinstance(node, WhileNode):
            self._gen_while(node)
        elif isinstance(node, PrintNode):
            self._gen_print(node)
        elif isinstance(node, BeginBlockNode):
            self._gen_begin_block(node)
        elif isinstance(node, ExternDeclNode):
            return
        elif isinstance(node, (FuncDefNode, LambdaDefNode)):
            return
        elif isinstance(node, ReturnNode):
            self._gen_return(node)
        elif isinstance(node, ArrayAssignNode):
            self._gen_array_assign(node)
        elif isinstance(node, ArrayPrintNode):
            self._gen_array_print(node)
        elif isinstance(node, FileWriteNode):
            self._gen_file_write(node)
        elif isinstance(node, RandomSeedNode):
            self._gen_rand_seed(node)

    def _gen_assign(self, node: AssignNode):
        target_type = self.var_types.get(node.target, "int")
        expr_type = self._infer_expression_type(node.value)
        self._gen_expression(node.value)
        self._coerce_value(expr_type, target_type, node.value)
        self._materialize_var_address(node.target, "x9")
        self._emit_store_by_type("x9", target_type)

    def _gen_if(self, node: IfNode):
        else_label = self._new_label("if_else")
        end_label = self._new_label("if_end")
        then_returns = self._statement_guarantees_return(node.then_branch)
        else_returns = self._statement_guarantees_return(node.else_branch)
        cond_type = self._infer_expression_type(node.condition)
        self._gen_expression(node.condition)
        self._coerce_to_condition(cond_type)
        self._emit("\tcmp\tw0, #0")
        self._emit(f"\tb.eq\t{else_label}")
        self._gen_statement(node.then_branch)
        if not then_returns:
            self._emit(f"\tb\t{end_label}")
        self._emit(f"{else_label}:")
        self._gen_statement(node.else_branch)
        if not then_returns or not else_returns:
            self._emit(f"{end_label}:")

    def _gen_while(self, node: WhileNode):
        start_label = self._new_label("while_cond")
        end_label = self._new_label("while_end")
        self._emit(f"{start_label}:")
        cond_type = self._infer_expression_type(node.condition)
        self._gen_expression(node.condition)
        self._coerce_to_condition(cond_type)
        self._emit("\tcmp\tw0, #0")
        self._emit(f"\tb.eq\t{end_label}")
        self._gen_statement(node.body)
        if not self._statement_guarantees_return(node.body):
            self._emit(f"\tb\t{start_label}")
        self._emit(f"{end_label}:")

    def _gen_print(self, node: PrintNode):
        value_type = self._infer_expression_type(node.value)
        self._gen_expression(node.value)
        self._emit_call_with_live_args(
            self._function_symbol(self._print_runtime_name(value_type)),
            [value_type],
        )

    def _gen_rand_seed(self, node: RandomSeedNode):
        seed_type = self._infer_expression_type(node.seed)
        self._gen_expression(node.seed)
        self._coerce_value(seed_type, "int")
        self._emit_call_with_live_args(self._function_symbol("neko_rand_seed"), ["int"])

    def _gen_return(self, node: ReturnNode):
        if not self.current_return_type or not self.current_epilogue_label:
            raise RuntimeError("return used outside of function")
        value_type = self._infer_expression_type(node.value)
        self._gen_expression(node.value)
        self._coerce_value(value_type, self.current_return_type, node.value)
        self._emit(f"\tb\t{self.current_epilogue_label}")

    def _gen_array_assign(self, node: ArrayAssignNode):
        array_type = self.var_types.get(node.name, "(array int 1)")
        elem_type = _array_element_type(array_type)
        self._compute_array_element_address(node.name, node.index)
        self._emit("\tmov\tx0, x9")
        self._emit_store_scratch(0, "string")
        value_type = self._infer_expression_type(node.value)
        self._gen_expression(node.value)
        self._coerce_value(value_type, elem_type, node.value)
        self._emit_load_scratch(0, "string", target_reg="x9")
        self._emit_store_by_type("x9", elem_type)

    def _gen_array_print(self, node: ArrayPrintNode):
        array_type = self.var_types.get(node.name, "(array int 1)")
        elem_type = _array_element_type(array_type)
        self._compute_array_element_address(node.name, node.index)
        self._emit_load_by_type("x9", elem_type)
        self._emit_call_with_live_args(
            self._function_symbol(self._print_runtime_name(elem_type)),
            [elem_type],
        )

    def _gen_file_write(self, node: FileWriteNode):
        self._prepare_call_arguments([node.path, node.value], ["string", node.value_type])
        self._emit(f"\tbl\t{self._function_symbol(f'neko_write_{node.value_type}')}")

    def _gen_expression(self, node: ASTNode):
        if isinstance(node, IntLiteralNode):
            self._emit_load_imm("w0", node.value, bits=32)
            return
        if isinstance(node, FloatLiteralNode):
            label = self._intern_float(node.value)
            self._emit(f"\tadrp\tx9, {label}@PAGE")
            self._emit(f"\tldr\td0, [x9, {label}@PAGEOFF]")
            return
        if isinstance(node, BoolLiteralNode):
            self._emit(f"\tmov\tw0, #{1 if node.value else 0}")
            return
        if isinstance(node, StringLiteralNode):
            label = self._intern_cstring(node.value)
            self._emit(f"\tadrp\tx0, {label}@PAGE")
            self._emit(f"\tadd\tx0, x0, {label}@PAGEOFF")
            return
        if isinstance(node, CharLiteralNode):
            self._emit_load_imm("w0", ord(node.value), bits=32)
            return
        if isinstance(node, IdentifierNode):
            if node.name in self.function_nodes:
                symbol = self._neko_function_symbol(node.name)
                self._emit(f"\tadrp\tx0, {symbol}@PAGE")
                self._emit(f"\tadd\tx0, x0, {symbol}@PAGEOFF")
                return
            if node.name in self.extern_nodes:
                symbol = self._function_symbol(node.name)
                self._emit(f"\tadrp\tx0, {symbol}@GOTPAGE")
                self._emit(f"\tldr\tx0, [x0, {symbol}@GOTPAGEOFF]")
                return
            type_str = self.var_types.get(node.name)
            if type_str is None:
                raise RuntimeError(f"Undefined variable: {node.name}")
            if type_str.startswith("(array"):
                self._materialize_var_address(node.name, "x0")
                return
            self._materialize_var_address(node.name, "x9")
            self._emit_load_by_type("x9", type_str)
            return
        if isinstance(node, BinOpNode):
            self._gen_binop(node)
            return
        if isinstance(node, LambdaDefNode):
            symbol = self._neko_function_symbol(node.name)
            self._emit(f"\tadrp\tx0, {symbol}@PAGE")
            self._emit(f"\tadd\tx0, x0, {symbol}@PAGEOFF")
            return
        if isinstance(node, FuncCallNode):
            self._gen_func_call(node)
            return
        if isinstance(node, ArrayAccessNode):
            array_type = self.var_types.get(node.name, "(array int 1)")
            elem_type = _array_element_type(array_type)
            self._compute_array_element_address(node.name, node.index)
            self._emit_load_by_type("x9", elem_type)
            return
        if isinstance(node, ArgcNode):
            self._emit("\tsub\tw0, w20, #1")
            return
        if isinstance(node, ArgvNode):
            self._emit_runtime_expr_call(
                self._function_symbol(f"neko_argv_{node.value_type}"),
                [("int", ArgcNode()), ("string", IdentifierNode(name="__argv_placeholder")), ("int", node.index)],
                direct_special="argv",
                value_type=node.value_type,
            )
            return
        if isinstance(node, InputNode):
            self._emit_call_no_args(self._function_symbol(f"neko_input_{node.value_type}"))
            return
        if isinstance(node, RandomRangeNode):
            self._emit_runtime_expr_call(
                self._function_symbol("neko_rand_range"),
                [("int", node.low), ("int", node.high)],
            )
            return
        if isinstance(node, FileReadNode):
            self._emit_runtime_expr_call(
                self._function_symbol(f"neko_read_{node.value_type}"),
                [("string", node.path)],
            )
            return
        if isinstance(node, StringLengthNode):
            self._emit_runtime_expr_call(self._function_symbol("neko_string_length"), [("string", node.string_expr)])
            return
        if isinstance(node, StringAtNode):
            self._emit_runtime_expr_call(
                self._function_symbol("neko_string_at"),
                [("string", node.string_expr), ("int", node.index)],
            )
            return
        if isinstance(node, StringSubNode):
            self._emit_runtime_expr_call(
                self._function_symbol("neko_string_sub"),
                [("string", node.string_expr), ("int", node.start), ("int", node.length)],
            )
            return
        if isinstance(node, StringCmpNode):
            self._emit_runtime_expr_call(
                self._function_symbol("neko_string_cmp"),
                [("string", node.left), ("string", node.right)],
            )
            return
        if isinstance(node, StringContainsNode):
            self._emit_runtime_expr_call(
                self._function_symbol("neko_string_contains"),
                [("string", node.haystack), ("string", node.needle)],
            )
            return
        if isinstance(node, IntToStringNode):
            self._emit_runtime_expr_call(self._function_symbol("neko_int_to_string"), [("int", node.int_expr)])
            return
        if isinstance(node, StringToIntNode):
            self._emit_runtime_expr_call(self._function_symbol("neko_string_to_int"), [("string", node.string_expr)])
            return
        if isinstance(node, ArgvStringNode):
            self._emit_runtime_expr_call(
                self._function_symbol("neko_argv_string"),
                [("int", ArgcNode()), ("string", IdentifierNode(name="__argv_placeholder")), ("int", node.index)],
                direct_special="argv_string",
                value_type="string",
            )
            return
        if isinstance(node, CharToIntNode):
            self._emit_runtime_expr_call(self._function_symbol("neko_char_to_int"), [("char", node.char_expr)])
            return
        if isinstance(node, IntToCharNode):
            self._emit_runtime_expr_call(self._function_symbol("neko_int_to_char"), [("int", node.int_expr)])
            return
        if isinstance(node, CharToStringNode):
            self._emit_runtime_expr_call(self._function_symbol("neko_char_to_string"), [("char", node.char_expr)])
            return
        if isinstance(node, IsLetterNode):
            self._emit_runtime_expr_call(self._function_symbol("neko_is_letter"), [("char", node.char_expr)])
            return
        if isinstance(node, IsDigitNode):
            self._emit_runtime_expr_call(self._function_symbol("neko_is_digit"), [("char", node.char_expr)])
            return
        if isinstance(node, CharUpcaseNode):
            self._emit_runtime_expr_call(self._function_symbol("neko_char_upcase"), [("char", node.char_expr)])
            return
        if isinstance(node, CharDowncaseNode):
            self._emit_runtime_expr_call(self._function_symbol("neko_char_downcase"), [("char", node.char_expr)])
            return
        raise RuntimeError(f"Unknown expression type: {type(node).__name__}")

    def _gen_binop(self, node: BinOpNode):
        left_type = self._infer_expression_type(node.left)
        right_type = self._infer_expression_type(node.right)

        if node.op == "+" and left_type == "string" and right_type == "string":
            self._gen_expression(node.left)
            slot = self._push_expr_temp("string")
            self._gen_expression(node.right)
            self._emit("\tmov\tx1, x0")
            self._load_expr_temp(slot, "string")
            self._pop_expr_temp()
            self._emit("\tbl\t_neko_string_concat")
            return

        if node.op in {"=", "!="} and left_type == "string" and right_type == "string":
            self._gen_expression(node.left)
            slot = self._push_expr_temp("string")
            self._gen_expression(node.right)
            self._emit("\tmov\tx1, x0")
            self._load_expr_temp(slot, "string")
            self._pop_expr_temp()
            self._emit("\tbl\t_neko_string_cmp")
            self._emit("\tcmp\tw0, #0")
            self._emit(f"\tcset\tw0, {'eq' if node.op == '=' else 'ne'}")
            return

        if left_type == "float" or right_type == "float":
            self._gen_expression(node.left)
            self._coerce_value(left_type, "float")
            slot = self._push_expr_temp("float")
            self._gen_expression(node.right)
            self._coerce_value(right_type, "float")
            if node.op in FLOAT_ARITH_OPS:
                self._load_expr_temp(slot, "float", target_reg="d1")
                self._pop_expr_temp()
                self._emit(f"\t{FLOAT_ARITH_OPS[node.op]}\td0, d1, d0")
                return
            self._load_expr_temp(slot, "float", target_reg="d1")
            self._pop_expr_temp()
            self._emit("\tfcmp\td1, d0")
            self._emit(f"\tcset\tw0, {CMP_OPS[node.op]}")
            return

        if left_type == "pointer" or right_type == "pointer":
            if left_type == "pointer" and right_type == "pointer":
                left_storage_type = "pointer"
                right_storage_type = "pointer"
            elif left_type == "pointer" and right_type == "int" and _is_null_pointer_literal(node.right):
                left_storage_type = "pointer"
                right_storage_type = "pointer"
            elif right_type == "pointer" and left_type == "int" and _is_null_pointer_literal(node.left):
                left_storage_type = "pointer"
                right_storage_type = "pointer"
            else:
                raise RuntimeError(f"pointer 只能与 pointer 或字面量 0 比较，但得到 {left_type} 与 {right_type}")
            self._gen_expression(node.left)
            self._coerce_value(left_type, "pointer", node.left)
            slot = self._push_expr_temp(left_storage_type)
            self._gen_expression(node.right)
            self._coerce_value(right_type, "pointer", node.right)
            self._load_expr_temp(slot, right_storage_type, target_reg="x1")
            self._pop_expr_temp()
            self._emit("\tcmp\tx1, x0")
            self._emit(f"\tcset\tw0, {CMP_OPS[node.op]}")
            return

        self._gen_expression(node.left)
        self._coerce_value(left_type, "int")
        slot = self._push_expr_temp("int")
        self._gen_expression(node.right)
        self._coerce_value(right_type, "int")
        if node.op in ARITH_OPS:
            self._load_expr_temp(slot, "int", target_reg="w1")
            self._pop_expr_temp()
            self._emit(f"\t{ARITH_OPS[node.op]}\tw0, w1, w0")
            return
        self._load_expr_temp(slot, "int", target_reg="w1")
        self._pop_expr_temp()
        self._emit("\tcmp\tw1, w0")
        self._emit(f"\tcset\tw0, {CMP_OPS[node.op]}")

    def _gen_func_call(self, node: FuncCallNode):
        func_node = self.function_nodes.get(node.name)
        extern_node = self.extern_nodes.get(node.name)
        if func_node is not None or extern_node is not None:
            if func_node is not None:
                param_types = [type_str for _, type_str in func_node.params]
                symbol = self._neko_function_symbol(node.name)
            else:
                param_types = list(extern_node.param_types)
                symbol = self._function_symbol(node.name)
            self._prepare_call_arguments(node.args, param_types)
            self._emit(f"\tbl\t{symbol}")
            return

        var_type = self.var_types.get(node.name, "")
        if not var_type.startswith("(func"):
            raise RuntimeError(f"Undefined function: {node.name}")

        param_types, _ = _parse_func_type_str(var_type)
        if len(node.args) != len(param_types):
            raise RuntimeError(f"Function '{node.name}' argument count mismatch")

        self._materialize_var_address(node.name, "x9")
        self._emit("\tldr\tx9, [x9]")
        self._emit("\tmov\tx0, x9")
        slot = self._push_expr_temp("string")
        self._prepare_call_arguments(node.args, param_types)
        self._load_expr_temp(slot, "string", target_reg="x9")
        self._pop_expr_temp()
        self._emit("\tblr\tx9")

    def _prepare_call_arguments(self, args: list[ASTNode], param_types: list[str]):
        if len(args) != len(param_types):
            raise RuntimeError("call argument count mismatch")

        int_count = 0
        float_count = 0
        for expected_type in param_types:
            if _is_float_type(expected_type):
                float_count += 1
            else:
                int_count += 1
        if int_count > len(INT_ARG_REGS):
            raise RuntimeError("函数调用参数过多：整数类参数超过 8 个")
        if float_count > len(FLOAT_ARG_REGS):
            raise RuntimeError("函数调用参数过多：float 参数超过 8 个")
        if len(args) > CALL_ARG_SLOTS:
            raise RuntimeError("函数调用参数过多：超过临时参数槽上限")

        for index, (arg_node, expected_type) in enumerate(zip(args, param_types)):
            actual_type = self._infer_expression_type(arg_node)
            self._gen_expression(arg_node)
            self._coerce_value(actual_type, expected_type, arg_node)
            self._emit_store_scratch(index, expected_type)

        int_index = 0
        float_index = 0
        for index, expected_type in enumerate(param_types):
            if _is_float_type(expected_type):
                self._emit_load_scratch(index, expected_type, target_reg=FLOAT_ARG_REGS[float_index])
                float_index += 1
            else:
                target_reg = INT_ARG_REGS[int_index] if _is_pointer_type(expected_type) else f"w{int_index}"
                self._emit_load_scratch(index, expected_type, target_reg=target_reg)
                int_index += 1

    def _compute_array_element_address(self, name: str, index_node: ASTNode):
        array_type = self.var_types.get(name)
        if array_type is None:
            raise RuntimeError(f"Undefined array: {name}")
        elem_type = _array_element_type(array_type)
        elem_size = _type_size(elem_type)
        self._gen_expression(index_node)
        index_type = self._infer_expression_type(index_node)
        self._coerce_value(index_type, "int")
        self._materialize_var_address(name, "x9")
        if elem_size == 1:
            self._emit("\tuxtw\tx10, w0")
        else:
            self._emit_load_imm("w11", elem_size, bits=32)
            self._emit("\tmul\tw10, w0, w11")
            self._emit("\tuxtw\tx10, w10")
        self._emit("\tadd\tx9, x9, x10")

    def _emit_store_by_type(self, address_reg: str, type_str: str):
        if _is_float_type(type_str):
            self._emit(f"\tstr\td0, [{address_reg}]")
        elif _is_char_type(type_str) or _is_bool_type(type_str):
            self._emit(f"\tstrb\tw0, [{address_reg}]")
        elif _is_pointer_type(type_str):
            self._emit(f"\tstr\tx0, [{address_reg}]")
        else:
            self._emit(f"\tstr\tw0, [{address_reg}]")

    def _emit_load_by_type(self, address_reg: str, type_str: str):
        if _is_float_type(type_str):
            self._emit(f"\tldr\td0, [{address_reg}]")
        elif _is_char_type(type_str) or _is_bool_type(type_str):
            self._emit(f"\tldrb\tw0, [{address_reg}]")
        elif _is_pointer_type(type_str):
            self._emit(f"\tldr\tx0, [{address_reg}]")
        else:
            self._emit(f"\tldr\tw0, [{address_reg}]")

    def _emit_call_with_live_args(self, symbol: str, arg_types: list[str]):
        int_index = 0
        float_index = 0
        for index, type_str in enumerate(arg_types):
            self._emit_store_scratch(index, type_str)
        for index, type_str in enumerate(arg_types):
            if _is_float_type(type_str):
                self._emit_load_scratch(index, type_str, target_reg=FLOAT_ARG_REGS[float_index])
                float_index += 1
            else:
                target = INT_ARG_REGS[int_index] if _is_pointer_type(type_str) else f"w{int_index}"
                self._emit_load_scratch(index, type_str, target_reg=target)
                int_index += 1
        self._emit(f"\tbl\t{symbol}")

    def _emit_call_no_args(self, symbol: str):
        self._emit(f"\tbl\t{symbol}")

    def _emit_runtime_expr_call(
        self,
        symbol: str,
        args: list[tuple[str, ASTNode]],
        direct_special: str | None = None,
        value_type: str | None = None,
    ):
        if direct_special in {"argv", "argv_string"}:
            index_type = self._infer_expression_type(args[2][1])
            self._gen_expression(args[2][1])
            self._coerce_value(index_type, "int")
            slot = self._push_expr_temp("int")
            self._emit("\tmov\tw0, w20")
            self._emit("\tmov\tx1, x21")
            self._load_expr_temp(slot, "int", target_reg="w2")
            self._pop_expr_temp()
            self._emit(f"\tbl\t{symbol}")
            return

        nodes = [expr for _, expr in args]
        types = [type_str for type_str, _ in args]
        self._prepare_call_arguments(nodes, types)
        self._emit(f"\tbl\t{symbol}")

    def _emit_default_return(self, type_str: str):
        if _is_float_type(type_str):
            self._emit("\tfmov\td0, xzr")
        elif _is_pointer_type(type_str):
            self._emit("\tmov\tx0, #0")
        else:
            self._emit("\tmov\tw0, #0")

    def _coerce_value(self, actual_type: str | None, target_type: str, node: ASTNode | None = None):
        if actual_type is None or actual_type == target_type:
            return

        if target_type == "float" and actual_type in {"int", "char", "bool"}:
            self._emit("\tscvtf\td0, w0")
            return
        if target_type == "int" and actual_type == "float":
            self._emit("\tfcvtzs\tw0, d0")
            return
        if target_type == "int" and actual_type in {"char", "bool"}:
            return
        if target_type == "char" and actual_type in {"int", "bool"}:
            self._emit("\tand\tw0, w0, #0xff")
            return
        if target_type == "bool" and actual_type in {"int", "char"}:
            self._emit("\tcmp\tw0, #0")
            self._emit("\tcset\tw0, ne")
            return
        if target_type == "bool" and actual_type == "float":
            self._emit("\tfmov\td1, xzr")
            self._emit("\tfcmp\td0, d1")
            self._emit("\tcset\tw0, ne")
            return
        if target_type == "float" and actual_type == "float":
            return
        if target_type == "string" and actual_type == "string":
            return
        if target_type == "pointer" and actual_type == "pointer":
            return
        if target_type == "pointer" and actual_type == "int":
            if node is None or not _is_null_pointer_literal(node):
                raise RuntimeError("pointer 仅支持从字面量 0 转换")
            self._emit("\tuxtw\tx0, w0")
            return
        if target_type.startswith("(func") and actual_type.startswith("(func"):
            return
        raise RuntimeError(f"Cannot coerce {actual_type} to {target_type}")

    def _coerce_to_condition(self, type_str: str | None):
        if type_str == "bool":
            return
        if type_str == "float":
            self._emit("\tfmov\td1, xzr")
            self._emit("\tfcmp\td0, d1")
            self._emit("\tcset\tw0, ne")
            return
        self._emit("\tcmp\tw0, #0")
        self._emit("\tcset\tw0, ne")

    def _infer_expression_type(self, node: ASTNode) -> str | None:
        if isinstance(node, IntLiteralNode):
            return "int"
        if isinstance(node, FloatLiteralNode):
            return "float"
        if isinstance(node, BoolLiteralNode):
            return "bool"
        if isinstance(node, StringLiteralNode):
            return "string"
        if isinstance(node, CharLiteralNode):
            return "char"
        if isinstance(node, IdentifierNode):
            if node.name in self.function_nodes:
                return _func_type_from_node(self.function_nodes[node.name])
            if node.name in self.extern_nodes:
                extern = self.extern_nodes[node.name]
                return f"(func ({' '.join(extern.param_types)}) {extern.return_type})"
            return self.var_types.get(node.name)
        if isinstance(node, LambdaDefNode):
            return _func_type_from_node(node)
        if isinstance(node, FuncCallNode):
            func = self.function_nodes.get(node.name)
            if func is not None:
                return func.return_type
            extern = self.extern_nodes.get(node.name)
            if extern is not None:
                return extern.return_type
            entry_type = self.var_types.get(node.name)
            if entry_type and entry_type.startswith("(func"):
                _, ret_type = _parse_func_type_str(entry_type)
                return ret_type
            return None
        if isinstance(node, ArrayAccessNode):
            entry_type = self.var_types.get(node.name)
            if entry_type and entry_type.startswith("(array"):
                return _array_element_type(entry_type)
            return None
        if isinstance(node, ArgcNode):
            return "int"
        if isinstance(node, ArgvNode):
            return node.value_type
        if isinstance(node, InputNode):
            return node.value_type
        if isinstance(node, RandomRangeNode):
            return "int"
        if isinstance(node, FileReadNode):
            return node.value_type
        if isinstance(node, StringLengthNode):
            return "int"
        if isinstance(node, StringAtNode):
            return "char"
        if isinstance(node, StringSubNode):
            return "string"
        if isinstance(node, StringCmpNode):
            return "int"
        if isinstance(node, StringContainsNode):
            return "bool"
        if isinstance(node, IntToStringNode):
            return "string"
        if isinstance(node, StringToIntNode):
            return "int"
        if isinstance(node, ArgvStringNode):
            return "string"
        if isinstance(node, CharToIntNode):
            return "int"
        if isinstance(node, IntToCharNode):
            return "char"
        if isinstance(node, CharToStringNode):
            return "string"
        if isinstance(node, IsLetterNode):
            return "bool"
        if isinstance(node, IsDigitNode):
            return "bool"
        if isinstance(node, CharUpcaseNode):
            return "char"
        if isinstance(node, CharDowncaseNode):
            return "char"
        if isinstance(node, BinOpNode):
            left_type = self._infer_expression_type(node.left)
            right_type = self._infer_expression_type(node.right)
            if left_type is None or right_type is None:
                return None
            if node.op in {"<", ">", "=", "<=", ">=", "!="}:
                return "bool"
            if node.op == "+" and left_type == "string" and right_type == "string":
                return "string"
            if left_type == "float" or right_type == "float":
                return "float"
            return "int"
        return None

    def _statement_guarantees_return(self, node: ASTNode) -> bool:
        if isinstance(node, ReturnNode):
            return True
        if isinstance(node, BeginBlockNode):
            for stmt in node.statements:
                if self._statement_guarantees_return(stmt):
                    return True
            return False
        if isinstance(node, IfNode):
            return self._statement_guarantees_return(node.then_branch) and self._statement_guarantees_return(node.else_branch)
        return False

    def _print_runtime_name(self, type_str: str | None) -> str:
        if type_str == "float":
            return "nekoprint_float"
        if type_str == "string":
            return "nekoprint_string"
        if type_str == "pointer":
            return "nekoprint_pointer"
        if type_str == "bool":
            return "nekoprint_bool"
        if type_str == "char":
            return "nekoprint_char"
        return "nekoprint_int"

    def _intern_cstring(self, value: str) -> str:
        label = self.cstring_pool.get(value)
        if label is None:
            label = f"l_.str.{len(self.cstring_pool)}"
            self.cstring_pool[value] = label
        return label

    def _intern_float(self, value: float) -> str:
        bits = struct.unpack("<Q", struct.pack("<d", value))[0]
        label = self.float_pool.get(bits)
        if label is None:
            label = f".LCPI_{len(self.float_pool)}"
            self.float_pool[bits] = label
        return label

    def _emit_literal_sections(self):
        if self.cstring_pool:
            self._emit(".section\t__TEXT,__cstring,cstring_literals")
            for value, label in self.cstring_pool.items():
                self._emit(f"{label}:")
                self._emit(f'\t.asciz\t"{_asm_escape_string(value)}"')
            self._emit()

        if self.float_pool:
            self._emit(".section\t__TEXT,__const")
            for bits, label in self.float_pool.items():
                self._emit(".p2align\t3")
                self._emit(f"{label}:")
                self._emit(f"\t.quad\t0x{bits:016x}")
            self._emit()

    def _emit_load_imm(self, reg: str, value: int, bits: int = 32):
        mask = (1 << bits) - 1
        unsigned = value & mask
        reg_prefix = reg[0]
        pieces = [(unsigned >> shift) & 0xFFFF for shift in range(0, bits, 16)]
        first_index = next((i for i, piece in enumerate(pieces) if piece), None)
        if first_index is None:
            self._emit(f"\tmov\t{reg}, #0")
            return
        shift = first_index * 16
        self._emit(f"\tmovz\t{reg}, #{pieces[first_index]}, lsl #{shift}")
        for idx in range(first_index + 1, len(pieces)):
            piece = pieces[idx]
            if piece:
                self._emit(f"\tmovk\t{reg}, #{piece}, lsl #{idx * 16}")
