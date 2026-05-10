"""LLVM IR code generator for NekoLang. Walks the AST and emits LLVM IR."""

import llvmlite.ir as ir
import llvmlite.binding as llvm

from .ast_nodes import (
    ASTNode, ProgramNode, BlockNode, VarDeclNode, BeginBlockNode,
    AssignNode, IfNode, WhileNode, PrintNode, BinOpNode,
    IdentifierNode, IntLiteralNode, FloatLiteralNode,
    FuncDefNode, FuncCallNode, ArrayAccessNode, ArrayAssignNode, ArrayPrintNode,
)
from .tokens import TYPE_SIZES


# NekoLang type string -> LLVM IR type
TYPE_MAP = {
    "int": ir.IntType(32),
    "float": ir.DoubleType(),
    "char": ir.IntType(8),
}

# Comparison operators -> (int predicate string, float predicate string)
CMP_OPS = {
    "<":  ("<", "olt"),
    ">":  (">", "ogt"),
    "=":  ("==", "oeq"),
    "<=": ("<=", "ole"),
    ">=": (">=", "oge"),
    "!=": ("!=", "one"),
}

# Arithmetic operators -> (int instruction, float instruction)
ARITH_OPS = {
    "+":  ("add",  "fadd"),
    "-":  ("sub",  "fsub"),
    "*":  ("mul",  "fmul"),
    "/":  ("sdiv", "fdiv"),
}


def _llvm_type(type_str: str) -> ir.Type:
    """Convert a NekoLang type string to an LLVM IR type."""
    if type_str in TYPE_MAP:
        return TYPE_MAP[type_str]
    # Parse array type: "(array int 10)"
    if type_str.startswith("(array"):
        parts = type_str.rstrip(")").split()
        elem_type = TYPE_MAP.get(parts[1], ir.IntType(32))
        count = int(parts[2])
        return ir.ArrayType(elem_type, count)
    return ir.IntType(32)  # default


def _is_float_type(type_str: str) -> bool:
    return type_str == "float"


class LLVMCodegen:
    """Generate LLVM IR from a NekoLang AST."""

    def __init__(self):
        self.module = ir.Module(name="neko")
        self.module.triple = "arm64-apple-macosx15.0.0"
        self.builder: ir.IRBuilder | None = None
        self.named_values: dict[str, ir.NamedValue] = {}  # name -> alloca
        self.var_types: dict[str, str] = {}                # name -> neko type string
        self.printf: ir.Function | None = None
        self.nekoprint_int: ir.Function | None = None
        self.nekoprint_float: ir.Function | None = None
        self.nekoprint_char: ir.Function | None = None
        self._fmt_cache: dict[str, ir.GlobalVariable] = {}

    def generate(self, ast: ProgramNode) -> str:
        """Generate LLVM IR from AST, return IR text."""
        self._declare_runtime()
        self._gen_program(ast)
        return str(self.module)

    def _declare_runtime(self):
        """Declare external runtime functions (printf wrappers)."""
        # printf
        void_ptr = ir.IntType(8).as_pointer()
        printf_ty = ir.FunctionType(ir.IntType(32), [void_ptr], var_arg=True)
        self.printf = ir.Function(self.module, printf_ty, name="printf")

        # nekoprint_int
        ty = ir.FunctionType(ir.VoidType(), [ir.IntType(32)])
        self.nekoprint_int = ir.Function(self.module, ty, name="nekoprint_int")

        # nekoprint_float
        ty = ir.FunctionType(ir.VoidType(), [ir.DoubleType()])
        self.nekoprint_float = ir.Function(self.module, ty, name="nekoprint_float")

        # nekoprint_char
        ty = ir.FunctionType(ir.VoidType(), [ir.IntType(8)])
        self.nekoprint_char = ir.Function(self.module, ty, name="nekoprint_char")

    def _get_fmt_const(self, fmt_str: str, name: str) -> ir.GlobalVariable:
        """Get or create a global format string constant."""
        if name in self._fmt_cache:
            return self._fmt_cache[name]
        data = bytearray((fmt_str + "\0").encode("utf-8"))
        ty = ir.ArrayType(ir.IntType(8), len(data))
        global_fmt = ir.GlobalVariable(self.module, ty, name=name)
        global_fmt.global_constant = True
        global_fmt.initializer = ir.Constant(ty, data)
        self._fmt_cache[name] = global_fmt
        return global_fmt

    def _fmt_ptr(self, fmt_name: str) -> ir.Value:
        """Get a pointer to the first byte of a format string constant."""
        gv = self._get_fmt_const(
            {"fmt_int": "%d\n", "fmt_float": "%lf\n", "fmt_char": "%c\n"}[fmt_name],
            fmt_name
        )
        zero = ir.Constant(ir.IntType(32), 0)
        return self.builder.gep(gv, [zero, zero], inbounds=True, name=fmt_name + ".ptr")

    def _gen_program(self, node: ProgramNode):
        # Create main function
        func_ty = ir.FunctionType(ir.IntType(32), [])
        main_func = ir.Function(self.module, func_ty, name="main")
        entry = main_func.append_basic_block(name="entry")
        self.builder = ir.IRBuilder(entry)

        self._gen_block(node.block)

        # Return 0
        self.builder.ret(ir.Constant(ir.IntType(32), 0))

    def _gen_block(self, node: BlockNode):
        for decl in node.var_decls:
            self._gen_var_decl(decl)
        self._gen_begin_block(node.body)

    def _gen_var_decl(self, node: VarDeclNode):
        for name, type_str in node.variables:
            llvm_ty = _llvm_type(type_str)
            alloca = self.builder.alloca(llvm_ty, name=name)
            # Zero-initialize
            if isinstance(llvm_ty, ir.ArrayType):
                # Arrays are left uninitialized (or zero by default on most systems)
                pass
            else:
                self.builder.store(ir.Constant(llvm_ty, 0), alloca)
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
        elif isinstance(node, ArrayAssignNode):
            self._gen_array_assign(node)
        elif isinstance(node, ArrayPrintNode):
            self._gen_array_print(node)

    def _gen_assign(self, node: AssignNode):
        val = self._gen_expression(node.value)
        alloca = self.named_values.get(node.target)
        if alloca is None:
            raise RuntimeError(f"Undefined variable: {node.target}")
        self.builder.store(val, alloca)

    def _gen_if(self, node: IfNode):
        cond_val = self._gen_expression(node.condition)

        # Ensure condition is i1 (boolean)
        if cond_val.type == ir.IntType(32):
            zero = ir.Constant(ir.IntType(32), 0)
            cond_val = self.builder.icmp_signed("!=", cond_val, zero, name="cond")

        func = self.builder.function
        then_bb = func.append_basic_block(name="if.then")
        else_bb = func.append_basic_block(name="if.else")
        end_bb = func.append_basic_block(name="if.end")

        self.builder.cbranch(cond_val, then_bb, else_bb)

        # Then block
        self.builder.position_at_start(then_bb)
        self._gen_statement(node.then_branch)
        if not self.builder.block.is_terminated:
            self.builder.branch(end_bb)

        # Else block
        self.builder.position_at_start(else_bb)
        self._gen_statement(node.else_branch)
        if not self.builder.block.is_terminated:
            self.builder.branch(end_bb)

        # Continue at end
        self.builder.position_at_start(end_bb)

    def _gen_while(self, node: WhileNode):
        func = self.builder.function
        loop_bb = func.append_basic_block(name="while.cond")
        body_bb = func.append_basic_block(name="while.body")
        end_bb = func.append_basic_block(name="while.end")

        # Jump to condition
        self.builder.branch(loop_bb)

        # Condition block
        self.builder.position_at_start(loop_bb)
        cond_val = self._gen_expression(node.condition)
        if cond_val.type == ir.IntType(32):
            zero = ir.Constant(ir.IntType(32), 0)
            cond_val = self.builder.icmp_signed("!=", cond_val, zero, name="while.cond")
        self.builder.cbranch(cond_val, body_bb, end_bb)

        # Body block
        self.builder.position_at_start(body_bb)
        self._gen_statement(node.body)
        if not self.builder.block.is_terminated:
            self.builder.branch(loop_bb)

        # End block
        self.builder.position_at_start(end_bb)

    def _gen_print(self, node: PrintNode):
        val = self._gen_expression(node.value)
        if val.type == ir.IntType(32):
            self.builder.call(self.nekoprint_int, [val])
        elif val.type == ir.DoubleType():
            self.builder.call(self.nekoprint_float, [val])
        elif val.type == ir.IntType(8):
            self.builder.call(self.nekoprint_char, [val])
        else:
            # Fallback: treat as int
            self.builder.call(self.nekoprint_int, [val])

    def _gen_array_assign(self, node: ArrayAssignNode):
        alloca = self.named_values.get(node.name)
        if alloca is None:
            raise RuntimeError(f"Undefined array: {node.name}")
        idx = self._gen_expression(node.index)
        val = self._gen_expression(node.value)
        zero = ir.Constant(ir.IntType(32), 0)
        ptr = self.builder.gep(alloca, [zero, idx], name=f"{node.name}.ptr")
        self.builder.store(val, ptr)

    def _gen_array_print(self, node: ArrayPrintNode):
        alloca = self.named_values.get(node.name)
        if alloca is None:
            raise RuntimeError(f"Undefined array: {node.name}")
        idx = self._gen_expression(node.index)
        zero = ir.Constant(ir.IntType(32), 0)
        ptr = self.builder.gep(alloca, [zero, idx], name=f"{node.name}.ptr")
        val = self.builder.load(ptr, name=f"{node.name}.val")
        self._gen_print_value(val, self.var_types.get(node.name, "int"))

    def _gen_print_value(self, val: ir.Value, type_str: str):
        """Print a value of the given type."""
        # Determine element type for arrays
        elem_type = type_str
        if type_str.startswith("(array"):
            elem_type = type_str.split()[1]

        if elem_type == "float":
            self.builder.call(self.nekoprint_float, [val])
        elif elem_type == "char":
            self.builder.call(self.nekoprint_char, [val])
        else:
            self.builder.call(self.nekoprint_int, [val])

    def _gen_expression(self, node: ASTNode) -> ir.Value:
        if isinstance(node, IntLiteralNode):
            return ir.Constant(ir.IntType(32), node.value)
        elif isinstance(node, FloatLiteralNode):
            return ir.Constant(ir.DoubleType(), node.value)
        elif isinstance(node, IdentifierNode):
            alloca = self.named_values.get(node.name)
            if alloca is None:
                raise RuntimeError(f"Undefined variable: {node.name}")
            return self.builder.load(alloca, name=node.name)
        elif isinstance(node, BinOpNode):
            return self._gen_binop(node)
        elif isinstance(node, FuncCallNode):
            return self._gen_func_call(node)
        elif isinstance(node, ArrayAccessNode):
            return self._gen_array_access(node)
        else:
            raise RuntimeError(f"Unknown expression type: {type(node).__name__}")

    def _gen_binop(self, node: BinOpNode) -> ir.Value:
        left = self._gen_expression(node.left)
        right = self._gen_expression(node.right)

        is_float = left.type == ir.DoubleType() or right.type == ir.DoubleType()

        # Promote int to float if mixed
        if is_float:
            if left.type == ir.IntType(32):
                left = self.builder.sitofp(left, ir.DoubleType())
            if right.type == ir.IntType(32):
                right = self.builder.sitofp(right, ir.DoubleType())

        op = node.op

        # Comparison
        if op in CMP_OPS:
            int_pred, float_pred = CMP_OPS[op]
            if is_float:
                return self.builder.fcmp_ordered(float_pred, left, right, name="cmp")
            else:
                return self.builder.icmp_signed(int_pred, left, right, name="cmp")

        # Arithmetic
        if op in ARITH_OPS:
            int_op, float_op = ARITH_OPS[op]
            if is_float:
                return getattr(self.builder, float_op)(left, right, name="tmp")
            else:
                return getattr(self.builder, int_op)(left, right, name="tmp")

        raise RuntimeError(f"Unknown operator: {op}")

    def _gen_func_call(self, node: FuncCallNode) -> ir.Value:
        func = self.module.globals.get(node.name)
        if func is None:
            raise RuntimeError(f"Undefined function: {node.name}")
        args = [self._gen_expression(arg) for arg in node.args]
        return self.builder.call(func, args, name="calltmp")

    def _gen_array_access(self, node: ArrayAccessNode) -> ir.Value:
        alloca = self.named_values.get(node.name)
        if alloca is None:
            raise RuntimeError(f"Undefined array: {node.name}")
        idx = self._gen_expression(node.index)
        zero = ir.Constant(ir.IntType(32), 0)
        ptr = self.builder.gep(alloca, [zero, idx], name=f"{node.name}.ptr")
        return self.builder.load(ptr, name=f"{node.name}.val")
