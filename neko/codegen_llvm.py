"""LLVM IR code generator for NekoLang. Walks the AST and emits LLVM IR."""

import llvmlite.ir as ir
from llvmlite import binding as llvm

from .ast_nodes import (
    ASTNode, ProgramNode, BlockNode, VarDeclNode, BeginBlockNode,
    AssignNode, IfNode, WhileNode, PrintNode, BinOpNode,
    IdentifierNode, IntLiteralNode, FloatLiteralNode, BoolLiteralNode, StringLiteralNode,
    CharLiteralNode,
    FuncDefNode, ExternDeclNode, LambdaDefNode, FuncCallNode, ReturnNode,
    ArrayAccessNode, ArrayAssignNode, ArrayPrintNode,
    ArgcNode, ArgvNode, InputNode, RandomSeedNode, RandomRangeNode, FileReadNode, FileWriteNode,
    StringLengthNode, StringAtNode, StringSubNode, StringCmpNode, StringContainsNode,
    IntToStringNode, StringToIntNode, ArgvStringNode,
    CharToIntNode, IntToCharNode, CharToStringNode, IsLetterNode, IsDigitNode,
    CharUpcaseNode, CharDowncaseNode,
)
from .name_mangling import mangle_neko_function_name


TYPE_MAP = {
    "int": ir.IntType(32),
    "float": ir.DoubleType(),
    "char": ir.IntType(8),
    "bool": ir.IntType(1),
    "string": ir.IntType(8).as_pointer(),
    "pointer": ir.IntType(8).as_pointer(),
}

CMP_OPS = {
    "<": ("<", "olt"),
    ">": (">", "ogt"),
    "=": ("==", "oeq"),
    "<=": ("<=", "ole"),
    ">=": (">=", "oge"),
    "!=": ("!=", "one"),
}

CMP_STR_OPS = {
    "=": "==",
    "!=": "!=",
}

ARITH_OPS = {
    "+": ("add", "fadd"),
    "-": ("sub", "fsub"),
    "*": ("mul", "fmul"),
    "/": ("sdiv", "fdiv"),
}


def _llvm_type(type_str: str) -> ir.Type:
    if type_str in TYPE_MAP:
        return TYPE_MAP[type_str]
    if type_str.startswith("(array"):
        parts = type_str.rstrip(")").split()
        elem_type = TYPE_MAP.get(parts[1], ir.IntType(32))
        count = int(parts[2])
        return ir.ArrayType(elem_type, count)
    if type_str.startswith("(func"):
        return ir.IntType(8).as_pointer()
    return ir.IntType(32)


def _parse_func_type_str(type_str: str) -> tuple[list[str], str]:
    """Parse '(func (p1 p2 ...) ret)' into (param_types, return_type)."""
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


class LLVMCodegen:
    """Generate LLVM IR from a NekoLang AST."""

    def __init__(self):
        self.module = ir.Module(name="neko")
        self.module.triple = llvm.get_default_triple()
        self.builder: ir.IRBuilder | None = None
        self.named_values: dict[str, ir.NamedValue] = {}
        self.var_types: dict[str, str] = {}
        self.function_nodes: dict[str, FuncDefNode | LambdaDefNode] = {}
        self.extern_nodes: dict[str, ExternDeclNode] = {}
        self.global_strings: dict[str, ir.GlobalVariable] = {}
        self.nekoprint_int: ir.Function | None = None
        self.nekoprint_float: ir.Function | None = None
        self.nekoprint_char: ir.Function | None = None
        self.nekoprint_bool: ir.Function | None = None
        self.nekoprint_string: ir.Function | None = None
        self.nekoprint_pointer: ir.Function | None = None
        self.neko_argv_int: ir.Function | None = None
        self.neko_argv_float: ir.Function | None = None
        self.neko_argv_char: ir.Function | None = None
        self.neko_argv_bool: ir.Function | None = None
        self.neko_input_int: ir.Function | None = None
        self.neko_input_float: ir.Function | None = None
        self.neko_input_char: ir.Function | None = None
        self.neko_input_bool: ir.Function | None = None
        self.neko_rand_seed: ir.Function | None = None
        self.neko_rand_range: ir.Function | None = None
        self.neko_read_int: ir.Function | None = None
        self.neko_read_float: ir.Function | None = None
        self.neko_read_char: ir.Function | None = None
        self.neko_read_bool: ir.Function | None = None
        self.neko_write_int: ir.Function | None = None
        self.neko_write_float: ir.Function | None = None
        self.neko_write_char: ir.Function | None = None
        self.neko_write_bool: ir.Function | None = None
        self.neko_string_concat: ir.Function | None = None
        self.neko_string_length: ir.Function | None = None
        self.neko_string_at: ir.Function | None = None
        self.neko_string_sub: ir.Function | None = None
        self.neko_string_cmp: ir.Function | None = None
        self.neko_string_contains: ir.Function | None = None
        self.neko_int_to_string: ir.Function | None = None
        self.neko_string_to_int: ir.Function | None = None
        self.neko_argv_string: ir.Function | None = None
        self.neko_char_to_int: ir.Function | None = None
        self.neko_int_to_char: ir.Function | None = None
        self.neko_char_to_string: ir.Function | None = None
        self.neko_is_letter: ir.Function | None = None
        self.neko_is_digit: ir.Function | None = None
        self.neko_char_upcase: ir.Function | None = None
        self.neko_char_downcase: ir.Function | None = None
        self.argc_value: ir.Value | None = None
        self.argv_value: ir.Value | None = None
        self.current_return_type: str | None = None

    def _function_symbol(self, name: str) -> str:
        return mangle_neko_function_name(name)

    def generate(self, ast: ProgramNode) -> str:
        self._declare_runtime()
        self.function_nodes = self._collect_function_nodes(ast.block.body)
        self.extern_nodes = self._collect_extern_nodes(ast.block.body)
        self._declare_functions()
        self._declare_externs()
        self._gen_functions()
        self._gen_program(ast)
        return str(self.module)

    def _declare_runtime(self):
        self.nekoprint_int = ir.Function(
            self.module, ir.FunctionType(ir.VoidType(), [ir.IntType(32)]), name="nekoprint_int"
        )
        self.nekoprint_float = ir.Function(
            self.module, ir.FunctionType(ir.VoidType(), [ir.DoubleType()]), name="nekoprint_float"
        )
        self.nekoprint_char = ir.Function(
            self.module, ir.FunctionType(ir.VoidType(), [ir.IntType(8)]), name="nekoprint_char"
        )
        self.nekoprint_bool = ir.Function(
            self.module, ir.FunctionType(ir.VoidType(), [ir.IntType(1)]), name="nekoprint_bool"
        )
        self.nekoprint_string = ir.Function(
            self.module, ir.FunctionType(ir.VoidType(), [ir.IntType(8).as_pointer()]), name="nekoprint_string"
        )
        self.nekoprint_pointer = ir.Function(
            self.module, ir.FunctionType(ir.VoidType(), [ir.IntType(8).as_pointer()]), name="nekoprint_pointer"
        )
        runtime_arg_types = [ir.IntType(32), ir.IntType(8).as_pointer().as_pointer(), ir.IntType(32)]
        self.neko_argv_int = ir.Function(
            self.module, ir.FunctionType(ir.IntType(32), runtime_arg_types), name="neko_argv_int"
        )
        self.neko_argv_float = ir.Function(
            self.module, ir.FunctionType(ir.DoubleType(), runtime_arg_types), name="neko_argv_float"
        )
        self.neko_argv_char = ir.Function(
            self.module, ir.FunctionType(ir.IntType(8), runtime_arg_types), name="neko_argv_char"
        )
        self.neko_argv_bool = ir.Function(
            self.module, ir.FunctionType(ir.IntType(1), runtime_arg_types), name="neko_argv_bool"
        )
        self.neko_input_int = ir.Function(
            self.module, ir.FunctionType(ir.IntType(32), []), name="neko_input_int"
        )
        self.neko_input_float = ir.Function(
            self.module, ir.FunctionType(ir.DoubleType(), []), name="neko_input_float"
        )
        self.neko_input_char = ir.Function(
            self.module, ir.FunctionType(ir.IntType(8), []), name="neko_input_char"
        )
        self.neko_input_bool = ir.Function(
            self.module, ir.FunctionType(ir.IntType(1), []), name="neko_input_bool"
        )
        self.neko_rand_seed = ir.Function(
            self.module, ir.FunctionType(ir.VoidType(), [ir.IntType(32)]), name="neko_rand_seed"
        )
        self.neko_rand_range = ir.Function(
            self.module, ir.FunctionType(ir.IntType(32), [ir.IntType(32), ir.IntType(32)]), name="neko_rand_range"
        )
        char_ptr = ir.IntType(8).as_pointer()
        self.neko_read_int = ir.Function(
            self.module, ir.FunctionType(ir.IntType(32), [char_ptr]), name="neko_read_int"
        )
        self.neko_read_float = ir.Function(
            self.module, ir.FunctionType(ir.DoubleType(), [char_ptr]), name="neko_read_float"
        )
        self.neko_read_char = ir.Function(
            self.module, ir.FunctionType(ir.IntType(8), [char_ptr]), name="neko_read_char"
        )
        self.neko_read_bool = ir.Function(
            self.module, ir.FunctionType(ir.IntType(1), [char_ptr]), name="neko_read_bool"
        )
        self.neko_write_int = ir.Function(
            self.module, ir.FunctionType(ir.VoidType(), [char_ptr, ir.IntType(32)]), name="neko_write_int"
        )
        self.neko_write_float = ir.Function(
            self.module, ir.FunctionType(ir.VoidType(), [char_ptr, ir.DoubleType()]), name="neko_write_float"
        )
        self.neko_write_char = ir.Function(
            self.module, ir.FunctionType(ir.VoidType(), [char_ptr, ir.IntType(8)]), name="neko_write_char"
        )
        self.neko_write_bool = ir.Function(
            self.module, ir.FunctionType(ir.VoidType(), [char_ptr, ir.IntType(1)]), name="neko_write_bool"
        )
        # String operations
        self.neko_string_concat = ir.Function(
            self.module, ir.FunctionType(char_ptr, [char_ptr, char_ptr]), name="neko_string_concat"
        )
        self.neko_string_length = ir.Function(
            self.module, ir.FunctionType(ir.IntType(32), [char_ptr]), name="neko_string_length"
        )
        self.neko_string_at = ir.Function(
            self.module, ir.FunctionType(ir.IntType(8), [char_ptr, ir.IntType(32)]), name="neko_string_at"
        )
        self.neko_string_sub = ir.Function(
            self.module, ir.FunctionType(char_ptr, [char_ptr, ir.IntType(32), ir.IntType(32)]), name="neko_string_sub"
        )
        self.neko_string_cmp = ir.Function(
            self.module, ir.FunctionType(ir.IntType(32), [char_ptr, char_ptr]), name="neko_string_cmp"
        )
        self.neko_string_contains = ir.Function(
            self.module, ir.FunctionType(ir.IntType(1), [char_ptr, char_ptr]), name="neko_string_contains"
        )
        self.neko_int_to_string = ir.Function(
            self.module, ir.FunctionType(char_ptr, [ir.IntType(32)]), name="neko_int_to_string"
        )
        self.neko_string_to_int = ir.Function(
            self.module, ir.FunctionType(ir.IntType(32), [char_ptr]), name="neko_string_to_int"
        )
        self.neko_argv_string = ir.Function(
            self.module, ir.FunctionType(char_ptr, runtime_arg_types), name="neko_argv_string"
        )
        # Char operations
        self.neko_char_to_int = ir.Function(
            self.module, ir.FunctionType(ir.IntType(32), [ir.IntType(8)]), name="neko_char_to_int"
        )
        self.neko_int_to_char = ir.Function(
            self.module, ir.FunctionType(ir.IntType(8), [ir.IntType(32)]), name="neko_int_to_char"
        )
        self.neko_char_to_string = ir.Function(
            self.module, ir.FunctionType(char_ptr, [ir.IntType(8)]), name="neko_char_to_string"
        )
        self.neko_is_letter = ir.Function(
            self.module, ir.FunctionType(ir.IntType(1), [ir.IntType(8)]), name="neko_is_letter"
        )
        self.neko_is_digit = ir.Function(
            self.module, ir.FunctionType(ir.IntType(1), [ir.IntType(8)]), name="neko_is_digit"
        )
        self.neko_char_upcase = ir.Function(
            self.module, ir.FunctionType(ir.IntType(8), [ir.IntType(8)]), name="neko_char_upcase"
        )
        self.neko_char_downcase = ir.Function(
            self.module, ir.FunctionType(ir.IntType(8), [ir.IntType(8)]), name="neko_char_downcase"
        )

    def _collect_function_nodes(self, node: ASTNode) -> dict[str, FuncDefNode]:
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
                walk(stmt.then_branch)
                walk(stmt.else_branch)
            elif isinstance(stmt, WhileNode):
                walk(stmt.body)

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
                walk(stmt.then_branch)
                walk(stmt.else_branch)
            elif isinstance(stmt, WhileNode):
                walk(stmt.body)

        walk(node)
        return found

    def _declare_functions(self):
        for node in self.function_nodes.values():
            ret_ty = _llvm_type(node.return_type)
            param_tys = [_llvm_type(type_str) for _, type_str in node.params]
            func_ty = ir.FunctionType(ret_ty, param_tys)
            ir.Function(self.module, func_ty, name=self._function_symbol(node.name))

    def _declare_externs(self):
        for node in self.extern_nodes.values():
            if node.name in self.module.globals:
                continue
            ret_ty = _llvm_type(node.return_type)
            param_tys = [_llvm_type(type_str) for type_str in node.param_types]
            func_ty = ir.FunctionType(ret_ty, param_tys)
            ir.Function(self.module, func_ty, name=node.name)

    def _gen_functions(self):
        for node in self.function_nodes.values():
            self._gen_function(node)

    def _gen_function(self, node: FuncDefNode | LambdaDefNode):
        func = self.module.globals[self._function_symbol(node.name)]
        entry = func.append_basic_block(name="entry")
        saved_builder = self.builder
        saved_named_values = self.named_values
        saved_var_types = self.var_types
        saved_return_type = self.current_return_type

        self.builder = ir.IRBuilder(entry)
        self.named_values = {}
        self.var_types = {}
        self.current_return_type = node.return_type

        for arg, (name, type_str) in zip(func.args, node.params):
            arg.name = name
            alloca = self.builder.alloca(_llvm_type(type_str), name=name)
            self.builder.store(arg, alloca)
            self.named_values[name] = alloca
            self.var_types[name] = type_str

        self._gen_statement(node.body)

        if not self.builder.block.is_terminated:
            self.builder.ret(self._default_value(node.return_type))

        self.builder = saved_builder
        self.named_values = saved_named_values
        self.var_types = saved_var_types
        self.current_return_type = saved_return_type

    def _gen_program(self, node: ProgramNode):
        func_ty = ir.FunctionType(ir.IntType(32), [ir.IntType(32), ir.IntType(8).as_pointer().as_pointer()])
        main_func = ir.Function(self.module, func_ty, name="main")
        main_func.args[0].name = "argc"
        main_func.args[1].name = "argv"
        entry = main_func.append_basic_block(name="entry")
        self.builder = ir.IRBuilder(entry)
        self.named_values = {}
        self.var_types = {}
        self.argc_value = main_func.args[0]
        self.argv_value = main_func.args[1]
        self.current_return_type = "int"

        self._gen_block(node.block)
        self.builder.ret(ir.Constant(ir.IntType(32), 0))

    def _gen_block(self, node: BlockNode):
        for decl in node.var_decls:
            self._gen_var_decl(decl)
        self._gen_begin_block(node.body)

    def _gen_var_decl(self, node: VarDeclNode):
        for name, type_str in node.variables:
            llvm_ty = _llvm_type(type_str)
            alloca = self.builder.alloca(llvm_ty, name=name)
            if not isinstance(llvm_ty, ir.ArrayType):
                self.builder.store(self._default_value(type_str), alloca)
            self.named_values[name] = alloca
            self.var_types[name] = type_str

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
        val = self._gen_expression(node.value)
        alloca = self.named_values.get(node.target)
        if alloca is None:
            raise RuntimeError(f"Undefined variable: {node.target}")
        target_type = self.var_types.get(node.target, "int")
        self.builder.store(self._coerce_value(val, target_type), alloca)

    def _gen_if(self, node: IfNode):
        cond_val = self._coerce_to_condition(self._gen_expression(node.condition))
        func = self.builder.function
        then_bb = func.append_basic_block(name="if.then")
        else_bb = func.append_basic_block(name="if.else")
        end_bb = func.append_basic_block(name="if.end")

        self.builder.cbranch(cond_val, then_bb, else_bb)

        self.builder.position_at_start(then_bb)
        self._gen_statement(node.then_branch)
        if not self.builder.block.is_terminated:
            self.builder.branch(end_bb)

        self.builder.position_at_start(else_bb)
        self._gen_statement(node.else_branch)
        if not self.builder.block.is_terminated:
            self.builder.branch(end_bb)

        self.builder.position_at_start(end_bb)

    def _gen_while(self, node: WhileNode):
        func = self.builder.function
        loop_bb = func.append_basic_block(name="while.cond")
        body_bb = func.append_basic_block(name="while.body")
        end_bb = func.append_basic_block(name="while.end")

        self.builder.branch(loop_bb)

        self.builder.position_at_start(loop_bb)
        cond_val = self._coerce_to_condition(self._gen_expression(node.condition))
        self.builder.cbranch(cond_val, body_bb, end_bb)

        self.builder.position_at_start(body_bb)
        self._gen_statement(node.body)
        if not self.builder.block.is_terminated:
            self.builder.branch(loop_bb)

        self.builder.position_at_start(end_bb)

    def _gen_print(self, node: PrintNode):
        self._gen_print_value(self._gen_expression(node.value), self._infer_expression_type(node.value))

    def _gen_rand_seed(self, node: RandomSeedNode):
        seed = self._coerce_value(self._gen_expression(node.seed), "int")
        self.builder.call(self.neko_rand_seed, [seed])

    def _gen_print_value(self, val: ir.Value, value_type: str | None = None):
        if val.type == ir.DoubleType():
            self.builder.call(self.nekoprint_float, [val])
        elif val.type == ir.IntType(8).as_pointer():
            if value_type == "pointer":
                self.builder.call(self.nekoprint_pointer, [val])
            else:
                self.builder.call(self.nekoprint_string, [val])
        elif isinstance(val.type, ir.IntType) and val.type.width == 1:
            self.builder.call(self.nekoprint_bool, [val])
        elif isinstance(val.type, ir.IntType) and val.type.width == 8:
            self.builder.call(self.nekoprint_char, [val])
        else:
            if isinstance(val.type, ir.IntType) and val.type.width != 32:
                val = self.builder.zext(val, ir.IntType(32))
            self.builder.call(self.nekoprint_int, [val])

    def _gen_return(self, node: ReturnNode):
        if not self.current_return_type:
            raise RuntimeError("return used outside of function")
        value = self._coerce_value(self._gen_expression(node.value), self.current_return_type)
        self.builder.ret(value)

    def _gen_array_assign(self, node: ArrayAssignNode):
        alloca = self.named_values.get(node.name)
        if alloca is None:
            raise RuntimeError(f"Undefined array: {node.name}")
        idx = self._coerce_value(self._gen_expression(node.index), "int")
        val = self._gen_expression(node.value)
        elem_type = self._array_element_type(self.var_types.get(node.name, "(array int 1)"))
        zero = ir.Constant(ir.IntType(32), 0)
        ptr = self.builder.gep(alloca, [zero, idx], name=f"{node.name}.ptr")
        self.builder.store(self._coerce_value(val, elem_type), ptr)

    def _gen_array_print(self, node: ArrayPrintNode):
        alloca = self.named_values.get(node.name)
        if alloca is None:
            raise RuntimeError(f"Undefined array: {node.name}")
        idx = self._coerce_value(self._gen_expression(node.index), "int")
        zero = ir.Constant(ir.IntType(32), 0)
        ptr = self.builder.gep(alloca, [zero, idx], name=f"{node.name}.ptr")
        self._gen_print_value(self.builder.load(ptr, name=f"{node.name}.val"), self._array_element_type(self.var_types.get(node.name, "(array int 1)")))

    def _gen_file_write(self, node: FileWriteNode):
        path = self._coerce_string(self._gen_expression(node.path))
        value = self._coerce_value(self._gen_expression(node.value), node.value_type)
        writer = self._runtime_write_function(node.value_type)
        self.builder.call(writer, [path, value])

    def _gen_expression(self, node: ASTNode) -> ir.Value:
        if isinstance(node, IntLiteralNode):
            return ir.Constant(ir.IntType(32), node.value)
        if isinstance(node, FloatLiteralNode):
            return ir.Constant(ir.DoubleType(), node.value)
        if isinstance(node, BoolLiteralNode):
            return ir.Constant(ir.IntType(1), int(node.value))
        if isinstance(node, StringLiteralNode):
            return self._string_constant(node.value)
        if isinstance(node, CharLiteralNode):
            return ir.Constant(ir.IntType(8), ord(node.value))
        if isinstance(node, IdentifierNode):
            # Check if it's a function name used as a value
            if node.name in self.function_nodes:
                func = self.module.globals[self._function_symbol(node.name)]
                return self.builder.bitcast(func, ir.IntType(8).as_pointer())
            if node.name in self.extern_nodes:
                func = self.module.globals[node.name]
                return self.builder.bitcast(func, ir.IntType(8).as_pointer())
            alloca = self.named_values.get(node.name)
            if alloca is None:
                raise RuntimeError(f"Undefined variable: {node.name}")
            return self.builder.load(alloca, name=node.name)
        if isinstance(node, BinOpNode):
            return self._gen_binop(node)
        if isinstance(node, LambdaDefNode):
            func = self.module.globals.get(self._function_symbol(node.name))
            if func is None:
                raise RuntimeError(f"Undefined lambda: {node.name}")
            return self.builder.bitcast(func, ir.IntType(8).as_pointer())
        if isinstance(node, FuncCallNode):
            return self._gen_func_call(node)
        if isinstance(node, ArrayAccessNode):
            return self._gen_array_access(node)
        if isinstance(node, ArgcNode):
            if self.argc_value is None:
                raise RuntimeError("argc is not available in this context")
            return self.builder.sub(self.argc_value, ir.Constant(ir.IntType(32), 1), name="argc.user")
        if isinstance(node, ArgvNode):
            if self.argc_value is None or self.argv_value is None:
                raise RuntimeError("argv is not available in this context")
            index = self._coerce_value(self._gen_expression(node.index), "int")
            reader = self._runtime_argv_function(node.value_type)
            return self.builder.call(reader, [self.argc_value, self.argv_value, index], name="argtmp")
        if isinstance(node, InputNode):
            reader = self._runtime_input_function(node.value_type)
            return self.builder.call(reader, [], name="inputtmp")
        if isinstance(node, RandomRangeNode):
            low = self._coerce_value(self._gen_expression(node.low), "int")
            high = self._coerce_value(self._gen_expression(node.high), "int")
            return self.builder.call(self.neko_rand_range, [low, high], name="randtmp")
        if isinstance(node, FileReadNode):
            path = self._coerce_string(self._gen_expression(node.path))
            reader = self._runtime_read_function(node.value_type)
            return self.builder.call(reader, [path], name="readtmp")
        # String built-in operations
        if isinstance(node, StringLengthNode):
            s = self._coerce_string(self._gen_expression(node.string_expr))
            return self.builder.call(self.neko_string_length, [s], name="strlen.tmp")
        if isinstance(node, StringAtNode):
            s = self._coerce_string(self._gen_expression(node.string_expr))
            idx = self._coerce_value(self._gen_expression(node.index), "int")
            return self.builder.call(self.neko_string_at, [s, idx], name="strat.tmp")
        if isinstance(node, StringSubNode):
            s = self._coerce_string(self._gen_expression(node.string_expr))
            start = self._coerce_value(self._gen_expression(node.start), "int")
            length = self._coerce_value(self._gen_expression(node.length), "int")
            return self.builder.call(self.neko_string_sub, [s, start, length], name="strsub.tmp")
        if isinstance(node, StringCmpNode):
            left = self._coerce_string(self._gen_expression(node.left))
            right = self._coerce_string(self._gen_expression(node.right))
            return self.builder.call(self.neko_string_cmp, [left, right], name="strcmp.tmp")
        if isinstance(node, StringContainsNode):
            hay = self._coerce_string(self._gen_expression(node.haystack))
            needle = self._coerce_string(self._gen_expression(node.needle))
            return self.builder.call(self.neko_string_contains, [hay, needle], name="strcon.tmp")
        if isinstance(node, IntToStringNode):
            n = self._coerce_value(self._gen_expression(node.int_expr), "int")
            return self.builder.call(self.neko_int_to_string, [n], name="itos.tmp")
        if isinstance(node, StringToIntNode):
            s = self._coerce_string(self._gen_expression(node.string_expr))
            return self.builder.call(self.neko_string_to_int, [s], name="stoi.tmp")
        if isinstance(node, ArgvStringNode):
            if self.argc_value is None or self.argv_value is None:
                raise RuntimeError("argv is not available in this context")
            index = self._coerce_value(self._gen_expression(node.index), "int")
            return self.builder.call(self.neko_argv_string, [self.argc_value, self.argv_value, index], name="argvstr.tmp")
        # Char built-in operations
        if isinstance(node, CharToIntNode):
            c = self._coerce_value(self._gen_expression(node.char_expr), "char")
            return self.builder.call(self.neko_char_to_int, [c], name="c2i.tmp")
        if isinstance(node, IntToCharNode):
            n = self._coerce_value(self._gen_expression(node.int_expr), "int")
            return self.builder.call(self.neko_int_to_char, [n], name="i2c.tmp")
        if isinstance(node, CharToStringNode):
            c = self._coerce_value(self._gen_expression(node.char_expr), "char")
            return self.builder.call(self.neko_char_to_string, [c], name="c2s.tmp")
        if isinstance(node, IsLetterNode):
            c = self._coerce_value(self._gen_expression(node.char_expr), "char")
            return self.builder.call(self.neko_is_letter, [c], name="isletter.tmp")
        if isinstance(node, IsDigitNode):
            c = self._coerce_value(self._gen_expression(node.char_expr), "char")
            return self.builder.call(self.neko_is_digit, [c], name="isdigit.tmp")
        if isinstance(node, CharUpcaseNode):
            c = self._coerce_value(self._gen_expression(node.char_expr), "char")
            return self.builder.call(self.neko_char_upcase, [c], name="upcase.tmp")
        if isinstance(node, CharDowncaseNode):
            c = self._coerce_value(self._gen_expression(node.char_expr), "char")
            return self.builder.call(self.neko_char_downcase, [c], name="downcase.tmp")
        raise RuntimeError(f"Unknown expression type: {type(node).__name__}")

    def _gen_binop(self, node: BinOpNode) -> ir.Value:
        left_type_name = self._infer_expression_type(node.left)
        right_type_name = self._infer_expression_type(node.right)
        left = self._gen_expression(node.left)
        right = self._gen_expression(node.right)
        char_ptr = ir.IntType(8).as_pointer()

        # String operations
        left_is_str = left_type_name == "string"
        right_is_str = right_type_name == "string"
        left_is_ptr = left_type_name == "pointer"
        right_is_ptr = right_type_name == "pointer"

        if left_is_str or right_is_str:
            if node.op == "+":
                if left_is_str and right_is_str:
                    return self.builder.call(self.neko_string_concat, [left, right], name="strcat.tmp")
                raise RuntimeError("字符串拼接要求两侧都是 string 类型")
            if node.op in CMP_STR_OPS:
                if not (left_is_str and right_is_str):
                    raise RuntimeError("字符串比较要求两侧都是 string 类型")
                cmp_result = self.builder.call(self.neko_string_cmp, [left, right], name="strcmp.tmp")
                zero = ir.Constant(ir.IntType(32), 0)
                return self.builder.icmp_signed(CMP_STR_OPS[node.op], cmp_result, zero, name="cmp")
            raise RuntimeError(f"字符串不支持 {node.op} 运算，请使用 string-cmp")

        if left_is_ptr or right_is_ptr:
            if node.op not in CMP_OPS:
                raise RuntimeError("pointer 仅支持比较运算")
            if left.type != char_ptr:
                left = self._coerce_value(left, "pointer")
            if right.type != char_ptr:
                right = self._coerce_value(right, "pointer")
            int_pred, _ = CMP_OPS[node.op]
            return self.builder.icmp_unsigned(int_pred, left, right, name="ptrcmp")

        is_float = left.type == ir.DoubleType() or right.type == ir.DoubleType()
        if is_float:
            left = self._coerce_value(left, "float")
            right = self._coerce_value(right, "float")
        else:
            left_width = left.type.width if isinstance(left.type, ir.IntType) else 32
            right_width = right.type.width if isinstance(right.type, ir.IntType) else 32
            target_width = max(left_width, right_width, 32)
            target_type = ir.IntType(target_width)
            if left.type != target_type:
                left = self.builder.zext(left, target_type)
            if right.type != target_type:
                right = self.builder.zext(right, target_type)

        if node.op in CMP_OPS:
            int_pred, float_pred = CMP_OPS[node.op]
            if is_float:
                return self.builder.fcmp_ordered(float_pred, left, right, name="cmp")
            return self.builder.icmp_signed(int_pred, left, right, name="cmp")

        if node.op in ARITH_OPS:
            int_op, float_op = ARITH_OPS[node.op]
            if is_float:
                return getattr(self.builder, float_op)(left, right, name="tmp")
            return getattr(self.builder, int_op)(left, right, name="tmp")

        raise RuntimeError(f"Unknown operator: {node.op}")

    def _gen_func_call(self, node: FuncCallNode) -> ir.Value:
        func_node = self.function_nodes.get(node.name)
        extern_node = self.extern_nodes.get(node.name)
        if func_node is not None or extern_node is not None:
            if func_node is not None:
                func = self.module.globals[self._function_symbol(node.name)]
            else:
                func = self.module.globals[node.name]
            args = []
            if func_node is not None:
                param_types = [type_str for _, type_str in func_node.params]
            else:
                param_types = list(extern_node.param_types)
            for arg_value, type_str in zip((self._gen_expression(arg) for arg in node.args), param_types):
                args.append(self._coerce_value(arg_value, type_str))
            return self.builder.call(func, args, name="calltmp")

        # Indirect call: load function pointer from variable
        alloca = self.named_values.get(node.name)
        if alloca is None:
            raise RuntimeError(f"Undefined function: {node.name}")
        var_type = self.var_types.get(node.name, "")
        if not var_type.startswith("(func"):
            raise RuntimeError(f"Variable '{node.name}' is not a function pointer")

        param_types, ret_type = _parse_func_type_str(var_type)
        func_ptr = self.builder.load(alloca, name=f"{node.name}.fptr")
        ret_llvm_ty = _llvm_type(ret_type)
        param_llvm_tys = [_llvm_type(p) for p in param_types]
        concrete_func_ty = ir.FunctionType(ret_llvm_ty, param_llvm_tys)
        casted = self.builder.bitcast(func_ptr, concrete_func_ty.as_pointer())

        args = []
        for arg_value, expected_type in zip((self._gen_expression(arg) for arg in node.args), param_types):
            args.append(self._coerce_value(arg_value, expected_type))
        return self.builder.call(casted, args, name="calltmp")

    def _gen_array_access(self, node: ArrayAccessNode) -> ir.Value:
        alloca = self.named_values.get(node.name)
        if alloca is None:
            raise RuntimeError(f"Undefined array: {node.name}")
        idx = self._coerce_value(self._gen_expression(node.index), "int")
        zero = ir.Constant(ir.IntType(32), 0)
        ptr = self.builder.gep(alloca, [zero, idx], name=f"{node.name}.ptr")
        return self.builder.load(ptr, name=f"{node.name}.val")

    def _coerce_value(self, value: ir.Value, target_type_str: str) -> ir.Value:
        target_type = _llvm_type(target_type_str)
        if value.type == target_type:
            return value

        if target_type == ir.DoubleType():
            if isinstance(value.type, ir.IntType):
                return self.builder.sitofp(value, ir.DoubleType())

        if isinstance(target_type, ir.PointerType) and isinstance(value.type, ir.IntType):
            if target_type == ir.IntType(8).as_pointer():
                if value.type.width != 32:
                    raise RuntimeError(f"Cannot coerce {value.type} to {target_type}")
                if not isinstance(value, ir.Constant) or value.constant != 0:
                    raise RuntimeError("pointer 仅支持从字面量 0 转换")
            widened = value
            if value.type.width < 64:
                widened = self.builder.zext(value, ir.IntType(64))
            elif value.type.width > 64:
                widened = self.builder.trunc(value, ir.IntType(64))
            return self.builder.inttoptr(widened, target_type)

        if isinstance(target_type, ir.PointerType) and isinstance(value.type, ir.PointerType):
            return self.builder.bitcast(value, target_type)

        if isinstance(target_type, ir.IntType) and isinstance(value.type, ir.IntType):
            if target_type.width > value.type.width:
                return self.builder.zext(value, target_type)
            if target_type.width < value.type.width:
                return self.builder.trunc(value, target_type)

        if isinstance(target_type, ir.IntType) and target_type.width == 1 and isinstance(value.type, ir.IntType):
            zero = ir.Constant(value.type, 0)
            return self.builder.icmp_signed("!=", value, zero, name="boolcast")

        if isinstance(target_type, ir.IntType) and value.type == ir.DoubleType():
            return self.builder.fptosi(value, target_type)

        raise RuntimeError(f"Cannot coerce {value.type} to {target_type}")

    def _coerce_to_condition(self, value: ir.Value) -> ir.Value:
        if isinstance(value.type, ir.IntType) and value.type.width == 1:
            return value
        if value.type == ir.DoubleType():
            zero = ir.Constant(ir.DoubleType(), 0.0)
            return self.builder.fcmp_ordered("!=", value, zero, name="cond")
        if isinstance(value.type, ir.IntType):
            zero = ir.Constant(value.type, 0)
            return self.builder.icmp_signed("!=", value, zero, name="cond")
        raise RuntimeError(f"Cannot use {value.type} as condition")

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
                return self._array_element_type(entry_type)
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

    def _default_value(self, type_str: str) -> ir.Constant:
        llvm_type = _llvm_type(type_str)
        if llvm_type == ir.DoubleType():
            return ir.Constant(llvm_type, 0.0)
        if isinstance(llvm_type, ir.PointerType):
            return ir.Constant(llvm_type, None)
        return ir.Constant(llvm_type, 0)

    def _array_element_type(self, type_str: str) -> str:
        parts = type_str.rstrip(")").split()
        return parts[1] if len(parts) > 1 else "int"

    def _runtime_argv_function(self, value_type: str) -> ir.Function:
        return {
            "int": self.neko_argv_int,
            "float": self.neko_argv_float,
            "char": self.neko_argv_char,
            "bool": self.neko_argv_bool,
        }[value_type]

    def _runtime_read_function(self, value_type: str) -> ir.Function:
        return {
            "int": self.neko_read_int,
            "float": self.neko_read_float,
            "char": self.neko_read_char,
            "bool": self.neko_read_bool,
        }[value_type]

    def _runtime_input_function(self, value_type: str) -> ir.Function:
        return {
            "int": self.neko_input_int,
            "float": self.neko_input_float,
            "char": self.neko_input_char,
            "bool": self.neko_input_bool,
        }[value_type]

    def _runtime_write_function(self, value_type: str) -> ir.Function:
        return {
            "int": self.neko_write_int,
            "float": self.neko_write_float,
            "char": self.neko_write_char,
            "bool": self.neko_write_bool,
        }[value_type]

    def _string_constant(self, value: str) -> ir.Value:
        if value not in self.global_strings:
            raw = value.encode("utf-8") + b"\x00"
            string_type = ir.ArrayType(ir.IntType(8), len(raw))
            global_var = ir.GlobalVariable(self.module, string_type, name=f".str.{len(self.global_strings)}")
            global_var.linkage = "internal"
            global_var.global_constant = True
            global_var.initializer = ir.Constant(string_type, bytearray(raw))
            self.global_strings[value] = global_var
        zero = ir.Constant(ir.IntType(32), 0)
        return self.builder.gep(self.global_strings[value], [zero, zero], inbounds=True, name="strptr")

    def _coerce_string(self, value: ir.Value) -> ir.Value:
        if value.type == ir.IntType(8).as_pointer():
            return value
        raise RuntimeError(f"Cannot use {value.type} as file path")
