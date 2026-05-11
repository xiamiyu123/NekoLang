"""LLVM IR code generator for NekoLang. Walks the AST and emits LLVM IR."""

import llvmlite.ir as ir
from llvmlite import binding as llvm

from .ast_nodes import (
    ASTNode, ProgramNode, BlockNode, VarDeclNode, BeginBlockNode,
    AssignNode, IfNode, WhileNode, PrintNode, BinOpNode,
    IdentifierNode, IntLiteralNode, FloatLiteralNode, BoolLiteralNode, StringLiteralNode,
    FuncDefNode, LambdaDefNode, FuncCallNode, ReturnNode,
    ArrayAccessNode, ArrayAssignNode, ArrayPrintNode,
    ArgcNode, ArgvNode, InputNode, RandomSeedNode, RandomRangeNode, FileReadNode, FileWriteNode,
)


TYPE_MAP = {
    "int": ir.IntType(32),
    "float": ir.DoubleType(),
    "char": ir.IntType(8),
    "bool": ir.IntType(1),
}

CMP_OPS = {
    "<": ("<", "olt"),
    ">": (">", "ogt"),
    "=": ("==", "oeq"),
    "<=": ("<=", "ole"),
    ">=": (">=", "oge"),
    "!=": ("!=", "one"),
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


class LLVMCodegen:
    """Generate LLVM IR from a NekoLang AST."""

    def __init__(self):
        self.module = ir.Module(name="neko")
        self.module.triple = llvm.get_default_triple()
        self.builder: ir.IRBuilder | None = None
        self.named_values: dict[str, ir.NamedValue] = {}
        self.var_types: dict[str, str] = {}
        self.function_nodes: dict[str, FuncDefNode] = {}
        self.global_strings: dict[str, ir.GlobalVariable] = {}
        self.nekoprint_int: ir.Function | None = None
        self.nekoprint_float: ir.Function | None = None
        self.nekoprint_char: ir.Function | None = None
        self.nekoprint_bool: ir.Function | None = None
        self.nekoprint_string: ir.Function | None = None
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
        self.argc_value: ir.Value | None = None
        self.argv_value: ir.Value | None = None
        self.current_return_type: str | None = None

    def generate(self, ast: ProgramNode) -> str:
        self._declare_runtime()
        self.function_nodes = self._collect_function_nodes(ast.block.body)
        self._declare_functions()
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

    def _collect_function_nodes(self, node: ASTNode) -> dict[str, FuncDefNode]:
        found: dict[str, FuncDefNode] = {}

        def walk(stmt: ASTNode):
            if isinstance(stmt, FuncDefNode):
                found.setdefault(stmt.name, stmt)
                walk(stmt.body)
            elif isinstance(stmt, LambdaDefNode):
                found.setdefault(stmt.name, stmt)
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
            ir.Function(self.module, func_ty, name=node.name)

    def _gen_functions(self):
        for node in self.function_nodes.values():
            self._gen_function(node)

    def _gen_function(self, node: FuncDefNode | LambdaDefNode):
        func = self.module.globals[node.name]
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
        self._gen_print_value(self._gen_expression(node.value))

    def _gen_rand_seed(self, node: RandomSeedNode):
        seed = self._coerce_value(self._gen_expression(node.seed), "int")
        self.builder.call(self.neko_rand_seed, [seed])

    def _gen_print_value(self, val: ir.Value):
        if val.type == ir.DoubleType():
            self.builder.call(self.nekoprint_float, [val])
        elif val.type == ir.IntType(8).as_pointer():
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
        self._gen_print_value(self.builder.load(ptr, name=f"{node.name}.val"))

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
        if isinstance(node, IdentifierNode):
            # Check if it's a function name used as a value
            if node.name in self.module.globals:
                func = self.module.globals[node.name]
                return self.builder.bitcast(func, ir.IntType(8).as_pointer())
            alloca = self.named_values.get(node.name)
            if alloca is None:
                raise RuntimeError(f"Undefined variable: {node.name}")
            return self.builder.load(alloca, name=node.name)
        if isinstance(node, BinOpNode):
            return self._gen_binop(node)
        if isinstance(node, LambdaDefNode):
            func = self.module.globals.get(node.name)
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
        raise RuntimeError(f"Unknown expression type: {type(node).__name__}")

    def _gen_binop(self, node: BinOpNode) -> ir.Value:
        left = self._gen_expression(node.left)
        right = self._gen_expression(node.right)

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
        func = self.module.globals.get(node.name)
        if func is not None:
            # Direct call
            func_node = self.function_nodes.get(node.name)
            args = []
            for arg_value, (_, type_str) in zip((self._gen_expression(arg) for arg in node.args), func_node.params):
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
