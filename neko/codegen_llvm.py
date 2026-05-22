"""
LLVM IR 代码生成器（后端之一）

编译原理角色：
  代码生成是编译器的最后阶段。它将 AST 翻译为目标代码。
  LLVM 后端使用 llvmlite 库（Python 的 LLVM IR 绑定）构建 LLVM IR 模块，
  生成的 IR 文本由 clang 编译并链接 runtime.c 为可执行文件。

LLVM IR 是什么？
  LLVM IR 是一种中间表示——类似汇编但更高级。
  它使用三地址码形式指令和无限"虚拟寄存器"（%1, %2, %3...）。
  LLVM 编译器基础设施负责把 IR 优化并翻译成目标机器汇编。

  例如 NekoLang 的 (:= x (+ 1 2)) 在 LLVM IR 中对应：
    %1 = add i32 1, 2        ; 虚拟寄存器 %1 保存 1+2 的结果
    store i32 %1, i32* %x    ; 把 %1 的值存到 x 变量的地址

本文件的设计：
  与 semantic.py 不同（遍历 AST 生成四元式），
  这里是直接遍历 AST 生成 LLVM IR 指令，绕过四元式。

生成流程（generate 方法）：
  1. _declare_runtime()    — 声明 C 运行时函数（print、input 等）
  2. _collect_function_nodes() — 收集所有函数定义
  3. _collect_extern_nodes()   — 收集所有 extern 声明
  4. _declare_functions()  — 在 LLVM 模块中声明函数签名
  5. _declare_externs()    — 声明 extern 函数
  6. _gen_functions()      — 生成所有函数体的 LLVM IR
  7. _gen_program()        — 生成 main 函数

llvmlite 核心对象：
  ir.Module         — 一个完整的 LLVM IR 模块（对应一个 .ll 文件）
  ir.Function       — 函数声明或定义
  ir.IRBuilder      — 指令构建器，在函数中插入指令
  ir.BasicBlock     — 基本块（顺序执行指令序列，以跳转结束）
  ir.Constant       — 常量值
  ir.GlobalVariable — 全局变量

IRBuilder 的使用模式：
  builder.add/store/load/call/branch 等方法在
  当前 basic block 末尾插入指令。
  每个函数的入口处创建 IRBuilder，绑定到 entry block。
"""

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


# ══════════════════════════════════════════════════════════════
# LLVM 类型映射
# ══════════════════════════════════════════════════════════════

# NekoLang 类型 → LLVM IR 类型
#   int    → i32 （32 位有符号整数）
#   float  → double （64 位双精度浮点）
#   char   → i8 （8 位整数，存 ASCII 码）
#   bool   → i1 （1 位整数，0=false, 1=true）
#   string → i8* （指向字符的指针，C 字符串）
#   pointer → i8* （不透明指针，对应 C 的 void*）
TYPE_MAP = {
    "int": ir.IntType(32),
    "float": ir.DoubleType(),
    "char": ir.IntType(8),
    "bool": ir.IntType(1),
    "string": ir.IntType(8).as_pointer(),
    "pointer": ir.IntType(8).as_pointer(),
}

# 比较运算映射：(有符号整数谓词, 浮点谓词)
# LLVM 整数比较用 icmp（如 icmp slt i32 %a, %b）
# 浮点比较用 fcmp（如 fcmp olt double %a, %b）
# 比较结果永远是 i1
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

# 算术运算映射：(整数指令名, 浮点指令名)
# LLVM 整数和浮点数的算术指令分开
ARITH_OPS = {
    "+": ("add", "fadd"),
    "-": ("sub", "fsub"),
    "*": ("mul", "fmul"),
    "/": ("sdiv", "fdiv"),
}


def _llvm_type(type_str: str) -> ir.Type:
    """NekoLang 类型字符串 → LLVM IR 类型。
       基本类型查 TYPE_MAP，复合类型解析后构造。"""
    if type_str in TYPE_MAP:
        return TYPE_MAP[type_str]
    if type_str.startswith("(array"):
        # (array int 10) → [10 x i32]
        parts = type_str.rstrip(")").split()
        elem_type = TYPE_MAP.get(parts[1], ir.IntType(32))
        count = int(parts[2])
        return ir.ArrayType(elem_type, count)
    if type_str.startswith("(func"):
        return ir.IntType(8).as_pointer()
    return ir.IntType(32)


def _parse_func_type_str(type_str: str) -> tuple[list[str], str]:
    """(func (int int) int) → (["int","int"], "int")"""
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


# ══════════════════════════════════════════════════════════════
# LLVM 代码生成器
# ══════════════════════════════════════════════════════════════

class LLVMCodegen:
    """
    LLVM IR 代码生成器——遍历 AST，使用 llvmlite.ir 构建 LLVM IR 模块。

    self.named_values 的作用：
      字典 {变量名 → alloca 指令}。NekoLang 的变量在 LLVM IR 中
      对应 alloca 指令创建的栈槽，读写通过 load/store。
      这称为"内存中的 SSA"（memory-to-SSA conversion），
      LLVM 的 mem2reg pass 会自动优化为真正的 SSA 寄存器。

    self.module 是最终产物，用 str(self.module) 输出 IR 文本。
    """

    def __init__(self):
        """初始化代码生成器，创建空的 LLVM IR 模块。"""
        self.module = ir.Module(name="neko")
        self.module.triple = llvm.get_default_triple()  # 目标平台
        self.builder: ir.IRBuilder | None = None
        self.named_values: dict[str, ir.NamedValue] = {}  # 变量名 → alloca
        self.var_types: dict[str, str] = {}                # 变量名 → NekoLang 类型
        self.function_nodes: dict[str, FuncDefNode | LambdaDefNode] = {}
        self.extern_nodes: dict[str, ExternDeclNode] = {}
        self.global_strings: dict[str, ir.GlobalVariable] = {}  # 字符串常量缓存
        # C 运行时函数引用
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
        """NekoLang 函数名 → LLVM IR 安全符号名（mangling）。"""
        return mangle_neko_function_name(name)

    def generate(self, ast: ProgramNode) -> str:
        """顶层入口：AST → LLVM IR 文本。"""
        self._declare_runtime()
        self.function_nodes = self._collect_function_nodes(ast.block.body)
        self.extern_nodes = self._collect_extern_nodes(ast.block.body)
        self._declare_functions()
        self._declare_externs()
        self._gen_functions()
        self._gen_program(ast)
        return str(self.module)

    # ── 运行时函数声明 ──────────────────────────────────────

    def _declare_runtime(self):
        """
        在 LLVM IR 模块中声明 C 运行时函数。
        这些函数的实现在 runtime.c 中，这里只声明签名，
        链接时由 clang 将实现链接进来。

        每条声明对应 LLVM IR 中的 declare 指令：
          declare void @nekoprint_int(i32)
        """
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

    # ── 函数/Extern 收集 ────────────────────────────────────

    def _collect_function_nodes(self, node: ASTNode) -> dict[str, FuncDefNode]:
        """递归遍历 AST，收集所有函数定义（含 lambda）。"""
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
        """递归遍历 AST，收集所有 extern 声明。"""
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

    # ── 函数声明 ────────────────────────────────────────────

    def _declare_functions(self):
        """在 LLVM 模块中声明所有函数（只签 name，不生成函数体）。"""
        for node in self.function_nodes.values():
            ret_ty = _llvm_type(node.return_type)
            param_tys = [_llvm_type(type_str) for _, type_str in node.params]
            func_ty = ir.FunctionType(ret_ty, param_tys)
            ir.Function(self.module, func_ty, name=self._function_symbol(node.name))

    def _declare_externs(self):
        """声明 extern 函数（函数名不 mangling，对应 C 运行时真实名）。"""
        for node in self.extern_nodes.values():
            if node.name in self.module.globals:
                continue
            ret_ty = _llvm_type(node.return_type)
            param_tys = [_llvm_type(type_str) for type_str in node.param_types]
            func_ty = ir.FunctionType(ret_ty, param_tys)
            ir.Function(self.module, func_ty, name=node.name)

    # ── 函数体生成 ──────────────────────────────────────────

    def _gen_functions(self):
        for node in self.function_nodes.values():
            self._gen_function(node)

    def _gen_function(self, node: FuncDefNode | LambdaDefNode):
        """
        生成函数的 LLVM IR 函数体。

        参数处理详解（为什么需要 alloca + store）：
          LLVM 使用 SSA（Static Single Assignment），每个变量只能被赋值一次。
          LLVM 函数的参数是 SSA 值（%a, %b 等"寄存器"），不能被 store 覆盖。

          但 NekoLang 中函数参数可以被赋值，例如：
            (function foo ((x int)) int (begin (:= x 10) (return x)))

          所以在函数入口处，每个参数需要：
            1. alloca 分配一个栈槽（得到一个指向该栈槽的指针 %x.addr = i32*）
            2. store 把参数的寄存器值存到这个栈槽
            3. 后续函数体中所有对 x 的读写都通过 load/store 访问这个栈槽

          这样处理之后，(:= x 10) 就是 store i32 10, i32* %x.addr，
          LLVM 的 mem2reg 优化 pass 会自动把所有 alloca/load/store
          提升为真正的 SSA 形式（ph id 节点处理不同路径的赋值）。

        上下文保存/恢复：
          save/restore 四个状态变量，用于支持嵌套函数的场景
          （一个函数体内部可以定义另一个函数，需要递归调用 _gen_function）。
        """
        # 取出之前声明好的 LLVM 函数对象
        func = self.module.globals[self._function_symbol(node.name)]
        # 为函数添加 entry 基本块——这是函数的第一个 basic block
        entry = func.append_basic_block(name="entry")

        # ── 保存调用者的上下文（嵌套函数递归时会覆盖这些变量） ──
        saved_builder = self.builder
        saved_named_values = self.named_values
        saved_var_types = self.var_types
        saved_return_type = self.current_return_type

        # ── 设置新函数的上下文 ──
        self.builder = ir.IRBuilder(entry)  # 新建 build er，绑定到 entry 块
        self.named_values = {}              # 清空变量表（新作用域）
        self.var_types = {}                 # 清空类型表
        self.current_return_type = node.return_type

        # ── 把函数参数 spill 到栈上 ──
        # func.args 是 LLVM 函数的参数（SSA 值）
        # node.params 是 NekoLang 的参数列表 [(name, type), ...]
        for arg, (name, type_str) in zip(func.args, node.params):
            arg.name = name  # LLVM 参数命名（IR 文本可读性）
            alloca = self.builder.alloca(_llvm_type(type_str), name=name)  # 分配栈槽
            self.builder.store(arg, alloca)   # 将 SSA 值存入栈槽
            self.named_values[name] = alloca  # 记录：变量 name 的栈槽
            self.var_types[name] = type_str   # 记录：变量 name 的类型

        # ── 生成函数体的 LLVM IR ──
        self._gen_statement(node.body)

        # ── 如果函数体没有以 ret 结尾（缺少 return），补一个默认返回值 ──
        if not self.builder.block.is_terminated:
            self.builder.ret(self._default_value(node.return_type))

        # ── 恢复调用者的上下文 ──
        self.builder = saved_builder
        self.named_values = saved_named_values
        self.var_types = saved_var_types
        self.current_return_type = saved_return_type

    def _gen_program(self, node: ProgramNode):
        """生成 main 函数（程序入口），保存 argc/argv 供后续引用。"""
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
        """变量声明：每个变量对应一条 alloca 指令 + 零初始化（数组除外）。"""
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

    # ── 语句生成 ────────────────────────────────────────────

    def _gen_statement(self, node: ASTNode):
        """语句分发器。FuncDefNode/LambdaDefNode 跳过（已由 _gen_functions 处理）。"""
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
        """赋值：计算右侧表达式，存入目标变量的 alloca 栈槽。"""
        val = self._gen_expression(node.value)
        alloca = self.named_values.get(node.target)
        if alloca is None:
            raise RuntimeError(f"Undefined variable: {node.target}")
        target_type = self.var_types.get(node.target, "int")
        self.builder.store(self._coerce_value(val, target_type), alloca)

    def _gen_if(self, node: IfNode):
        """
        if 语句翻译为 basic block + 条件跳转模式：
          %cond = icmp ...                  ; 计算条件表达式 → i1
          br i1 %cond, label %if.then, label %if.else  ; 条件分支
        if.then:
          ... then 分支的指令 ...
          br label %if.end                  ; 跳到结尾
        if.else:
          ... else 分支的指令 ...
          br label %if.end                  ; 跳到结尾
        if.end:
          ... 后续指令 ...                  ; 两条路径汇合后继续执行

        LLVM 中 basic block 必须以跳转指令结尾（terminator）。
        is_terminated 检查当前 block 是否已经有 ret/br 等结尾指令，
        如果没有才加 branch，防止重复添加 terminator。
        """
        # 1. 计算条件表达式，得到 i1 类型的值
        cond_val = self._coerce_to_condition(self._gen_expression(node.condition))
        # 2. 创建三个 basic block
        func = self.builder.function
        then_bb = func.append_basic_block(name="if.then")
        else_bb = func.append_basic_block(name="if.else")
        end_bb = func.append_basic_block(name="if.end")
        # 3. 条件分支跳转
        self.builder.cbranch(cond_val, then_bb, else_bb)
        # 4. 生成 then 分支（切换到 then_bb 中插入指令）
        self.builder.position_at_start(then_bb)
        self._gen_statement(node.then_branch)
        if not self.builder.block.is_terminated:
            self.builder.branch(end_bb)
        # 5. 生成 else 分支
        self.builder.position_at_start(else_bb)
        self._gen_statement(node.else_branch)
        if not self.builder.block.is_terminated:
            self.builder.branch(end_bb)
        # 6. 切换到 end_bb，后续代码在此生成
        self.builder.position_at_start(end_bb)

    def _gen_while(self, node: WhileNode):
        """
        while 循环翻译为 basic block + 前跳/回跳模式：
          br label %while.cond               ; 无条件跳到条件判断
        while.cond:
          %cond = ...                        ; 计算条件
          br i1 %cond, %while.body, %while.end  ; 条件分支
        while.body:
          ... 循环体的指令 ...
          br label %while.cond               ; 回跳到条件判断（回边）
        while.end:
          ... 后续指令 ...                   ; 循环出口

        与 if 的核心区别：while.body 的末尾有一条"回边"，
        跳回 while.cond 重新判断条件，形成循环。
        """
        func = self.builder.function
        loop_bb = func.append_basic_block(name="while.cond")
        body_bb = func.append_basic_block(name="while.body")
        end_bb = func.append_basic_block(name="while.end")

        self.builder.branch(loop_bb)  # 跳到条件判断

        self.builder.position_at_start(loop_bb)
        cond_val = self._coerce_to_condition(self._gen_expression(node.condition))
        self.builder.cbranch(cond_val, body_bb, end_bb)

        self.builder.position_at_start(body_bb)
        self._gen_statement(node.body)
        if not self.builder.block.is_terminated:
            self.builder.branch(loop_bb)  # 回边：跳回条件判断

        self.builder.position_at_start(end_bb)

    def _gen_print(self, node: PrintNode):
        self._gen_print_value(self._gen_expression(node.value), self._infer_expression_type(node.value))

    def _gen_rand_seed(self, node: RandomSeedNode):
        seed = self._coerce_value(self._gen_expression(node.seed), "int")
        self.builder.call(self.neko_rand_seed, [seed])

    def _gen_print_value(self, val: ir.Value, value_type: str | None = None):
        """根据 LLVM 类型选择对应的打印函数（用类型模式匹配）。"""
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
        """数组元素赋值：用 getelementptr 计算地址，store 存值。"""
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
        self._gen_print_value(
            self.builder.load(ptr, name=f"{node.name}.val"),
            self._array_element_type(self.var_types.get(node.name, "(array int 1)"))
        )

    def _gen_file_write(self, node: FileWriteNode):
        path = self._coerce_string(self._gen_expression(node.path))
        value = self._coerce_value(self._gen_expression(node.value), node.value_type)
        writer = self._runtime_write_function(node.value_type)
        self.builder.call(writer, [path, value])

    # ── 表达式生成 ──────────────────────────────────────────

    def _gen_expression(self, node: ASTNode) -> ir.Value:
        """
        生成表达式的 LLVM IR。返回 ir.Value，可直接作为其他指令的操作数。

        字面量 → ir.Constant
        变量 → builder.load(alloca)
        二元运算 → _gen_binop
        函数调用 → _gen_func_call
        内建操作 → builder.call(运行时函数)
        """
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
        # 字符串内建操作——调用 C 运行时函数
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
        # 字符内建操作
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
        """二元运算：字符串拼接、数值运算、比较运算的 LLVM IR 生成。"""
        left_type_name = self._infer_expression_type(node.left)
        right_type_name = self._infer_expression_type(node.right)
        left = self._gen_expression(node.left)
        right = self._gen_expression(node.right)
        char_ptr = ir.IntType(8).as_pointer()

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
        """
        函数调用。分两种情况：

        1. 直接调用——函数名在 function_nodes 或 extern_nodes 中。
           已知 callee，直接生成 call 指令：
             %calltmp = call i32 @neko_fn_add(i32 %arg1, i32 %arg2)
           直接调用时，LLVM 的 call 指令后跟 "@符号名"。

        2. 间接调用——通过变量中存储的函数指针调用。
           例如 (var ((f (func (int) int)))) (:= f (lambda ((x int)) int ...)) (print (f 5))
           变量 f 中存的是 i8*（不透明函数指针）。
           间接调用需要：
             a. load 出 i8* 函数指针
             b. bitcast 回具体的函数指针类型（如 i32(i32)*）
             c. call 该指针
           对应 LLVM IR：
             %f.fptr = load i8*, i8** %f         ; 从变量取出 i8*
             %casted = bitcast i8* to i32(i32)*   ; 转为具体函数类型
             %result = call i32 %casted(i32 %x)    ; 间接调用
        """
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
        """
        类型转换器——确保 LLVM IR 值的类型匹配目标类型。

        LLVM IR 是强类型语言，每个操作都要求操作数的位宽、符号性和类别
        完全符合指令的要求。例如：
          %x = add i32 %a, %b          ← 必须两个操作数都是 i32
          store i32 %val, i32* %ptr    ← 值的类型和指针的目标类型必须匹配

        NekoLang 的类型系统相对宽松（char 可当 int 用、int 可当 bool 用），
        这些隐式转换由本方法自动插入对应的 LLVM 指令实现。

        转换规则速查：
          char → int        无需转换（char 在 w0 中已经是 32 位，CPU 寄存器无位宽）
          int  → float      sitofp（有符号整数转浮点）
          float → int       fptosi（浮点转有符号整数）
          int  → bool       icmp != 0（非零即真）
          float → bool      fcmp != 0.0（非零即真）
          int  → char       trunc i32 to i8（截断到 8 位）
          int 0 → pointer   inttoptr（零指针：字面量 0 转换为空指针）
          i8  → i32         zext（零扩展，无符号）
          i64 → i32         trunc（截断）
          i8* → i8*         bitcast（指针类型间转换）
          bool → int        zext i1 to i32（零扩展）
        """
        target_type = _llvm_type(target_type_str)
        # 类型已经匹配，无需转换
        if value.type == target_type:
            return value
        """
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
        """将任意值转换为 i1（条件分支需要的类型）。"""
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
        """推断表达式类型（同 semantic.py 对应方法）。"""
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
        """返回 NekoLang 类型的零值。"""
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
        """
        创建字符串全局常量。
        字符串作为 LLVM 全局变量（internal constant）存储，
        取指针时用 getelementptr [N x i8]* 到 i8*。
        """
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
