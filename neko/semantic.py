"""
语义分析器（Semantic Analyzer）

编译原理角色：
  语义分析是编译器的第三阶段。它接收语法分析产出的 AST，
  在确认程序语法正确之后，进一步检查程序的**语义正确性**：
    1. 类型检查（Type Checking）—— 操作数类型是否匹配操作符的要求
    2. 作用域管理（Scope Management）—— 变量是否声明，函数是否定义
    3. 控制流检查 —— return 语句是否在函数体内、是否有返回值

  更重要的是，语义分析器**生成中间代码**（Intermediate Representation, IR），
  为后续的代码生成阶段铺路。

NekoLang 的语义分析输出：三地址码（Three-Address Code / 四元式 Quadruple）
  每条指令的形式是 (op, ob1, ob2, t)：
    :=      赋值         (:=, addr, _, target)
    +/-*/   算术运算     (+, left_addr, right_addr, temp)
    if_false 条件跳转    (if_false, cond_addr, _, label)
    goto    无条件跳转   (goto, _, _, label)
    label   标签定义     (label, label_name, _, _)
    print   输出         (print, addr, _, _)
    param   传参         (param, arg_addr, _, _)
    call    函数调用     (call, func_name, arg_count, temp)
    return  函数返回     (return, addr, _, _)
    ...

两遍遍历设计：
  第一遍 _collect_function_definitions() —— 收集所有函数签名（解决前向引用）
  第二遍 _analyze_block() —— 真正的语义分析 + 四元式生成

关键状态：
  symbol_table  — 符号表，管理多层作用域和变量地址
  quadruples    — 四元式列表，是语义分析的核心产出
  function_signatures — 函数签名表，用于函数调用的类型检查
"""

from dataclasses import dataclass

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
from .symbol_table import SymbolTable
from .errors import SemanticError


# ══════════════════════════════════════════════════════════════
# 辅助数据结构
# ══════════════════════════════════════════════════════════════

@dataclass
class Quadruple:
    """
    四元式（Quadruple / 三地址码指令）。

    这是语义分析的核心产出。每条四元式代表一条"三地址"指令：
      (操作符, 操作数1, 操作数2, 目标)

    三地址码中每条指令最多有三个操作数（两个源操作数 + 一个目标），
    因此得名"三地址码"。

    常见四元式形式：
      (:=, I1, _, I2)        → I2 := I1（赋值）
      (+, T1, T2, T3)        → T3 := T1 + T2（算术运算）
      (if_false, T1, _, L1)  → if T1 is false goto L1（条件跳转）
      (goto, _, _, L2)        → goto L2（无条件跳转）
      (label, L1, _, _)      → L1:（标签定义）
      (print, I1, _, _)      → print I1（输出）
      (param, I1, _, _)      → push param I1（函数传参）
      (call, "func", "2", T3)→ T3 = func(arg1, arg2)（函数调用）
      (return, T1, _, _)     → return T1（函数返回）

    地址命名规则（由 SymbolTable 统一管理）：
      I{n} — 变量/参数（如 I1, I2）
      C{n} — 常量（如 C1_42, C2_3.14）
      T{n} — 临时变量（如 T1, T2）
      L{n} — 标签（如 L1, L2）
    """
    op: str           # 操作符（:=, +, -, *, /, if_false, goto, call 等）
    ob1: str = "_"    # 第一操作数地址
    ob2: str = "_"    # 第二操作数地址（不参与置 "_"）
    t: str = "_"      # 目标地址或返回值地址

    def __str__(self):
        return f"({self.op}, {self.ob1}, {self.ob2}, {self.t})"


@dataclass
class FunctionSignature:
    """
    函数签名——记录函数的参数类型和返回类型。

    用于函数调用的类型检查：
      调用时，检查实参的类型和数量是否与签名匹配。

    也用于函数指针变量的类型推断：
      将变量声明为 (func (int int) int) 类型时，
      可以通过这个签名判断间接调用的类型正确性。
    """
    param_types: list[str]   # 参数类型列表，如 ["int", "int"]
    return_type: str         # 返回类型，如 "int"


class LabelManager:
    """
    标签管理器——负责生成唯一的跳转标签名。

    在翻译 if/while 控制流时，需要生成标签（如 L1, L2...）
    作为条件跳转（if_false）和无条件跳转（goto）的目标。

    例如翻译 (if cond then else) 需要三个标签：
      if_false cond_addr → L1（条件不满足跳 else）
      goto → L2（then 做完跳结尾）
      label L1（else 分支）
      label L2（if 结束）

    每个 if/while 都从 LabelManager 获得新的、不重复的标签名。
    """
    def __init__(self):
        self.counter = 0

    def new_label(self) -> str:
        """返回一个新标签名，格式为 L1, L2, L3..."""
        self.counter += 1
        return f"L{self.counter}"


# ══════════════════════════════════════════════════════════════
# 语义分析器主类
# ══════════════════════════════════════════════════════════════

class SemanticAnalyzer:
    """
    语义分析器主类。

    职责细分：
      1. 建立符号表（登记变量、函数、参数）
      2. 类型推断与类型检查（操作数类型是否匹配）
      3. 生成四元式序列（中间代码）

    两遍遍历策略：
      第一遍：_collect_function_definitions()
        只遍历 AST 中的函数定义，登记函数名和签名，
        不分析函数体，不生成四元式。
        目的是解决前向引用——允许函数 A 调用后面定义的函数 B。

      第二遍：_analyze_block() → ... → _analyze_statement()
        真正做语义分析：类型检查 + 四元式生成。
        此时所有函数名已在符号表中，可以自由调用。

    核心调用模式：
      _analyze_expression(node) → str
        分析一个表达式节点，生成求值指令，返回存放结果的地址字符串。
        例如分析 IntLiteralNode(42) → 返回 "C1_42"（常量地址）
        分析 BinOpNode("+", left, right) → 生成加法指令，返回 "T1"（临时变量地址）

      _infer_expression_type(node) → str | None
        推断表达式的 NekoLang 类型（如 "int", "float", "bool", "string"），
        不生成四元式。用于赋值和参数传递前的类型兼容性检查。

    符号表状态管理：
      push_scope() / pop_scope() —— 进入/退出函数时切换作用域
      enter(name, type, cat)     —— 登记新符号
      lookup(name)               —— 查找符号（沿作用域链向上）
      get_var_addr(name)         —— 获取变量地址字符串
      alloc_temp()               —— 分配临时变量的地址
      get_const_addr(value)      —— 分配或复用常量地址
    """

    def __init__(self):
        """初始化语义分析器，清空所有状态。"""
        self.symbol_table = SymbolTable()                    # 符号表
        self.labels = LabelManager()                         # 标签管理器
        self.quadruples: list[Quadruple] = []                # 四元式列表（产出）
        self.errors: list[SemanticError] = []                # 语义错误列表
        self.source_lines: list[str] = []                    # 源码行列表（用于报错显示）
        self.function_signatures: dict[str, FunctionSignature] = {}  # 函数签名表
        self.current_function_name: str | None = None        # 当前所在函数名（分析函数体时设置）
        self.current_function_return_type: str | None = None # 当前函数返回类型
        self.current_function_has_return = False             # 当前函数是否已有 return 语句
        self.lambda_counter: int = 0                         # lambda 编号生成器

    def set_source(self, source: str):
        """设置源码文本（用于错误信息中的行显示）。
           和 parser.set_source() 类似，语义分析器本质只需要 AST，
           但有了源码才能显示代码行和 ^ 标记。"""
        self.source_lines = source.splitlines()

    def _emit(self, op: str, ob1: str = "_", ob2: str = "_", t: str = "_"):
        """发射一条四元式——添加到 quadruples 列表末尾。
           这是语义分析器的核心输出动作。
           每调用一次 _emit，就产生一条三地址码指令。"""
        self.quadruples.append(Quadruple(op=op, ob1=ob1, ob2=ob2, t=t))

    def _get_src(self, node: ASTNode) -> str:
        """根据 AST 节点记录的行号，返回对应的源代码行。"""
        if 0 < node.line <= len(self.source_lines):
            return self.source_lines[node.line - 1]
        return ""

    def _error(self, node: ASTNode, message: str, suggestion_key: str = ""):
        """记录一条语义错误。不立即抛出异常，而是收集到 errors 列表。
           这样可以在一次运行中发现所有错误，而不是发现一个就停下。"""
        self.errors.append(
            SemanticError(
                message,
                line=node.line,
                column=node.column,
                source_line=self._get_src(node),
                suggestion_key=suggestion_key,
            )
        )

    def _is_null_pointer_literal(self, node: ASTNode) -> bool:
        """判断 AST 节点是否代表空指针字面量（即整数 0）。
           NekoLang 中 0 可被隐式转换为空指针。"""
        return isinstance(node, IntLiteralNode) and node.value == 0

    # ── 顶层调度 ──────────────────────────────────────────────

    def analyze(self, node: ASTNode) -> list[Quadruple]:
        """
        语义分析的唯一入口。

        参数：
          node — 语法分析器产出的 AST 根节点（ProgramNode）

        返回：
          四元式列表（全部中间代码）

        语义分析器不修改 AST，只读取 AST 节点信息，
        最终产出是 self.quadruples（四元式列表）。
        """
        if isinstance(node, ProgramNode):
            self._analyze_program(node)
        return self.quadruples

    def _analyze_program(self, node: ProgramNode):
        """
        分析整个程序。

        流程：
          1. 在符号表中登记"program"程序的入口地址
          2. 发射 program 标记指令（标识程序开始）
          3. 第一遍：收集所有函数定义（只登记签名，不分析函数体）
          4. 第二遍：分析程序主体（变量声明 + begin 块 + 四元式生成）
          5. 发射 end 标记指令（标识程序结束）
        """
        prog_addr = self.symbol_table.enter(node.name, "program", "program")
        self._emit("program", prog_addr, "_", "_")
        # 第一遍：只收集函数定义，登记到符号表和 function_signatures
        self._collect_function_definitions(node.block.body)
        # 第二遍：真正的语义分析（类型检查 + 四元式生成）
        self._analyze_block(node.block)
        self._emit("end", prog_addr, "_", "_")

    def _function_type(self, params: list[tuple[str, str]], return_type: str) -> str:
        """
        从参数列表和返回类型构造 NekoLang 函数类型字符串。
        例如：_function_type([("a","int"), ("b","int")], "int")
        返回："(func (int int) int)"
        """
        return f"(func ({' '.join(type_ for _, type_ in params)}) {return_type})"

    # ── 第一遍：函数定义收集 ──────────────────────────────────

    def _collect_function_definitions(self, node: ASTNode):
        """
        第一遍遍历：收集所有函数定义/声明的签名。

        这是解决"前向引用"问题的关键方法。
        在真正分析函数体之前，先递归遍历整个 AST，
        找到所有的 FuncDefNode、ExternDeclNode 和 LambdaDefNode，
        把它们的名字和签名登记到符号表和 function_signatures。

        这样，在第二遍分析函数体时，
        即使函数 A 内部调用了后面才定义的函数 B，
        B 的签名已经在符号表中，可以正常检查类型。

        递归规则：
          - FuncDefNode → 登记签名，递归到 body 内部（允许嵌套函数）
          - ExternDeclNode → 登记签名，不递归（extern 没有函数体）
          - LambdaDefNode → 分配名称，登记签名，递归到 body
          - BeginBlockNode/AssignNode/IfNode/WhileNode → 继续递归查找子节点
        """
        if isinstance(node, FuncDefNode):
            # 函数定义：检查重名、登记签名、递归到函数体内部收集嵌套函数
            if self.symbol_table.lookup_current(node.name):
                self._error(node, f"函数 '{node.name}' 已经声明过了", "duplicate_var")
            else:
                self.symbol_table.enter(node.name, self._function_type(node.params, node.return_type), "f")
                self.function_signatures[node.name] = FunctionSignature(
                    param_types=[type_ for _, type_ in node.params],
                    return_type=node.return_type,
                )
            self._collect_function_definitions(node.body)  # 继续到函数体内部查找
            return  # 函数体处理完毕，不继续走后面的递归（防止重复处理）

        if isinstance(node, ExternDeclNode):
            # 外部函数声明：登记签名，并验证参数/返回类型是否支持
            if self.symbol_table.lookup_current(node.name):
                self._error(node, f"函数 '{node.name}' 已经声明过了", "duplicate_var")
            else:
                func_type = f"(func ({' '.join(node.param_types)}) {node.return_type})"
                self.symbol_table.enter(node.name, func_type, "f")
                self.function_signatures[node.name] = FunctionSignature(
                    param_types=list(node.param_types),
                    return_type=node.return_type,
                )
                self._validate_extern_signature(node)
            return  # extern 没有函数体，直接返回

        if isinstance(node, LambdaDefNode):
            # lambda 匿名函数：自动生成内部名称，登记签名，递归函数体
            self.lambda_counter += 1
            node.name = f"__lambda_{self.lambda_counter}"  # 改写节点本身的 name 字段
            self.symbol_table.enter(node.name, self._function_type(node.params, node.return_type), "f")
            self.function_signatures[node.name] = FunctionSignature(
                param_types=[type_ for _, type_ in node.params],
                return_type=node.return_type,
            )
            self._collect_function_definitions(node.body)  # 递归到 lambda 体
            return

        # 非函数节点：继续递归到子节点中查找嵌套的函数定义
        if isinstance(node, BeginBlockNode):
            for stmt in node.statements:
                self._collect_function_definitions(stmt)
        elif isinstance(node, AssignNode):
            self._collect_function_definitions(node.value)
        elif isinstance(node, IfNode):
            self._collect_function_definitions(node.then_branch)
            self._collect_function_definitions(node.else_branch)
        elif isinstance(node, WhileNode):
            self._collect_function_definitions(node.body)

    # ── 第二遍：块分析 ────────────────────────────────────────

    def _analyze_block(self, node: BlockNode):
        """
        分析一个块：先分析变量声明（登记到符号表），再分析 begin 主体。

        对应 AST 结构：
          BlockNode
            ├── var_decls: [VarDeclNode, ...]
            └── body: BeginBlockNode
        """
        for decl in node.var_decls:
            self._analyze_var_decl(decl)
        self._analyze_begin_block(node.body)

    def _analyze_var_decl(self, node: VarDeclNode):
        """
        分析变量声明——将变量名和类型登记到符号表。

        重复声明检查：如果当前作用域已有同名变量，报错。
        注意这里用的是 lookup_current()（仅在当前层查找）
        而不是 lookup()（沿作用域链向上查找），
        因为不同作用域可以重名（函数内的变量覆盖全局变量）。"""
        for name, type_ in node.variables:
            if self.symbol_table.lookup_current(name):
                self._error(node, f"变量 '{name}' 已经声明过了", "duplicate_var")
            else:
                self.symbol_table.enter(name, type_, "v")  # "v" 表示变量

    def _analyze_begin_block(self, node: BeginBlockNode):
        """分析 begin 块：按顺序分析每条语句，生成对应的四元式。"""
        for stmt in node.statements:
            self._analyze_statement(stmt)

    # ── 第二遍：语句分析 ──────────────────────────────────────

    def _analyze_statement(self, node: ASTNode):
        """
        语句分发器——根据 AST 节点类型调用对应的分析方法。

        这是语义分析阶段的"语句中枢"，和语法分析阶段的 _parse_statement() 对应。
          parser._parse_statement()     → 创建语句节点
          semantic._analyze_statement() → 分析语句节点并生成四元式
        """
        if isinstance(node, AssignNode):
            self._analyze_assign(node)
        elif isinstance(node, IfNode):
            self._analyze_if(node)
        elif isinstance(node, WhileNode):
            self._analyze_while(node)
        elif isinstance(node, PrintNode):
            self._analyze_print(node)
        elif isinstance(node, BeginBlockNode):
            self._analyze_begin_block(node)
        elif isinstance(node, FuncDefNode):
            self._analyze_func_def(node)       # 函数定义在第一遍已收集签名，这里分析函数体
        elif isinstance(node, ExternDeclNode):
            return                              # extern 已在第一遍处理，无需再动
        elif isinstance(node, ReturnNode):
            self._analyze_return(node)
        elif isinstance(node, ArrayAssignNode):
            self._analyze_array_assign(node)
        elif isinstance(node, ArrayPrintNode):
            self._analyze_array_print(node)
        elif isinstance(node, FileWriteNode):
            self._analyze_file_write(node)
        elif isinstance(node, RandomSeedNode):
            self._analyze_rand_seed(node)

    def _analyze_assign(self, node: AssignNode):
        """
        分析赋值语句——生成 := 四元式。

        流程：
          1. 查符号表确认变量已声明
          2. 类型检查：右侧表达式类型能否赋给左侧变量
          3. 生成右侧表达式的求值指令（可能产生多条四元式）
          4. 发射一条 := 四元式

        类型兼容规则：见 _assignment_compatible 和 _types_compatible
          float 可以接受 int 和 char
          int 可以接受 char
          pointer 可以接受字面量 0
        """
        entry = self.symbol_table.lookup(node.target)
        if not entry:
            self._error(node, f"未定义的变量 '{node.target}'", "undefined_var")
            return

        expr_type = self._infer_expression_type(node.value)
        if expr_type and not self._assignment_compatible(entry.type, node.value, expr_type):
            self._error(
                node,
                f"无法将 {expr_type} 赋给 {entry.type} 类型的变量 '{node.target}'",
                "type_mismatch",
            )
            return

        addr = self._analyze_expression(node.value)
        var_addr = self.symbol_table.get_var_addr(node.target)
        self._emit(":=", addr, "_", var_addr)

    def _analyze_if(self, node: IfNode):
        """
        分析 if 条件分支语句——翻译为条件跳转 + 标签的四元式序列。

        NekoLang 源码：           生成的四元式序列：
          (if cond                if_false cond_addr → L_else  ; 条件不成立跳 else
            then-branch           ... then 分支的指令 ...
            else-branch           goto → L_end                 ; then 做完跳结尾
          )                       label L_else                 ; else 分支开始
                                  ... else 分支的指令 ...
                                  label L_end                  ; if 结束

        控制流翻译的核心模式：
          条件跳转（if_false）+"绕过真分支"的无条件跳转（goto）+ 两个标签。
          这种模式是编译器中 if 语句的通用翻译方式。
        """
        # 类型检查：条件表达式必须是可判定的类型
        cond_type = self._infer_expression_type(node.condition)
        if cond_type and not self._is_condition_type(cond_type):
            self._error(node.condition, f"if 条件不能使用 {cond_type} 类型", "type_mismatch")

        cond_addr = self._analyze_expression(node.condition)
        else_label = self.labels.new_label()     # else 标签（条件为假跳转目标）
        end_label = self.labels.new_label()      # if 结束标签（then 分支结束后跳转）
        self._emit("if_false", cond_addr, "_", else_label)  # 条件为假 → goto else_label
        self._analyze_statement(node.then_branch)            # 真分支
        self._emit("goto", "_", "_", end_label)              # 真分支结束 → 跳过 else
        self._emit("label", else_label, "_", "_")            # else 分支入口
        self._analyze_statement(node.else_branch)            # 假分支
        self._emit("label", end_label, "_", "_")             # if 结束

    def _analyze_while(self, node: WhileNode):
        """
        分析 while 循环语句——翻译为条件跳转 + 回跳的四元式序列。

        NekoLang 源码：           生成的四元式序列：
          (while cond             label L_start               ; 循环开始
            body                  ... 计算 cond ...
                                  if_false cond_addr → L_end  ; 条件不成立退出循环
                                  ... body 指令 ...
                                  goto → L_start              ; 回到开始处重新判断
                                ) label L_end                 ; 循环出口

        循环和条件分支的核心区别：
          条件分支：向前跳，"绕过程序的某个部分"
          循环：向后跳，"回到程序的前面部分"
        """
        cond_type = self._infer_expression_type(node.condition)
        if cond_type and not self._is_condition_type(cond_type):
            self._error(node.condition, f"while 条件不能使用 {cond_type} 类型", "type_mismatch")

        start_label = self.labels.new_label()
        end_label = self.labels.new_label()
        self._emit("label", start_label, "_", "_")            # 循环条件判断入口
        cond_addr = self._analyze_expression(node.condition)
        self._emit("if_false", cond_addr, "_", end_label)     # 条件不成立 → 退出
        self._analyze_statement(node.body)                    # 循环体
        self._emit("goto", "_", "_", start_label)             # 回到条件判断
        self._emit("label", end_label, "_", "_")              # 循环出口

    def _analyze_print(self, node: PrintNode):
        """分析 print 语句：计算表达式值，然后发射 print 四元式。"""
        addr = self._analyze_expression(node.value)
        self._emit("print", addr, "_", "_")

    def _analyze_rand_seed(self, node: RandomSeedNode):
        """分析 rand-seed 语句：检查种子类型，生成设置随机种子的四元式。"""
        seed_type = self._infer_expression_type(node.seed)
        if seed_type and seed_type != "int":
            self._error(node.seed, "rand-seed 需要 int 类型的种子", "type_mismatch")
            return
        seed_addr = self._analyze_expression(node.seed)
        self._emit("rand-seed", seed_addr, "_", "_")

    def _parse_func_type(self, type_str: str) -> FunctionSignature | None:
        # 硬编码的格式解析 函数的参数类型和返回类型
        """
        从 NekoLang 函数类型字符串解析出 FunctionSignature。

        输入："(func (int int) int)"
        输出：FunctionSignature(param_types=["int", "int"], return_type="int")

        用于检查 extern 参数类型是否支持，
        以及从函数指针变量类型还原签名以进行间接调用。
        """
        if not type_str.startswith("(func"):
            return None
        inner = type_str[len("(func "):-1]  # 截去 "(func " 和结尾 ")"
        paren_start = inner.index("(")
        paren_end = inner.index(")")
        param_str = inner[paren_start + 1:paren_end].strip()
        param_types = param_str.split() if param_str else []
        ret_type = inner[paren_end + 1:].strip()
        return FunctionSignature(param_types=param_types, return_type=ret_type)

    def _analyze_lambda_def(self, node: LambdaDefNode) -> str:
        """
        分析 lambda 匿名函数定义。

        lambda 和 function 的区别：
          - function 在收集阶段就登记了签名，函数体在 _analyze_func_def 中分析
          - lambda 出现在表达式位置，它的分析是"内联"的（在 _analyze_expression 中被调用）

        分析过程：
          1. 保存当前函数上下文（允许 lambda 嵌套在函数中）
          2. 推入新的作用域（lambda:{name}）
          3. 登记参数
          4. 分析 lambda 体
          5. 弹出作用域，恢复函数上下文
        """
        previous_name = self.current_function_name
        previous_return_type = self.current_function_return_type
        previous_has_return = self.current_function_has_return

        self.current_function_name = node.name
        self.current_function_return_type = node.return_type
        self.current_function_has_return = False
        self.symbol_table.push_scope(f"lambda:{node.name}")

        for param_name, param_type in node.params:
            if self.symbol_table.lookup_current(param_name):
                self._error(node, f"参数 '{param_name}' 已经声明过了", "duplicate_var")
            else:
                self.symbol_table.enter(param_name, param_type, "p")  # "p" = 参数

        self._analyze_statement(node.body)

        if not self.current_function_has_return:
            self._error(node, f"lambda 缺少 return 语句")

        self.symbol_table.pop_scope()
        self.current_function_name = previous_name
        self.current_function_return_type = previous_return_type
        self.current_function_has_return = previous_has_return
        return node.name

    def _analyze_func_def(self, node: FuncDefNode):
        """
        分析函数定义——在第二遍遍历时分析函数体。

        函数体分析在逻辑上需要完成四件事：
          A. 建立函数自己的作用域——函数内声明的变量和参数不能污染外层
          B. 登记参数到当前作用域——让函数体可以引用参数
          C. 分析函数体中的语句——类型检查 + 四元式生成
          D. 检查 return 完整性——有返回值的函数必须有 return

        第一遍 _collect_function_definitions 已登记了函数签名，
        所以这里只分析函数体，不再重复登记函数名。

        作用域管理详解（面向符号表）：
          进入函数时 push_scope("function:{name}")
            符号表从:
              全局层: x → I1(int)
            变成:
              全局层: x → I1(int)
              function:foo 层:  ← 新推入的空层

          登记参数后:
              全局层: x → I1(int)
              function:foo 层: n → I2(int)
                                |
                            参数 n 存在这一层，
                            不干扰全局的 x。
                            lookup("n") 在当前层找到；
                            lookup("x") 向上找到全局层。

          退出时 pop_scope()
            符号表回到进入前的状态，function:foo 层所有变量消失。

        上下文保存/恢复（current_function_name 等）：
          三个实例变量 current_function_name / return_type / has_return
          标识"当前正在分析哪个函数"。
          需要保存恢复是因为函数可以嵌套：
            (function outer ((a int)) int        ← 设置 ctx = outer
              (function inner ((b int)) int      ← 递归进入 inner，ctx 变为 inner
                (return (+ b a))
              )                                   ← inner 分析完毕
              (return (inner 10))
            )                                     ← 恢复 ctx = outer
          如果不恢复，分析完 inner 后 ctx 还停留在 "inner"，
          后续的 return 检查会以为是 inner 的 return。
        """
        # ── 保存外部函数上下文（用于嵌套函数的场合） ──
        previous_name = self.current_function_name
        previous_return_type = self.current_function_return_type
        previous_has_return = self.current_function_has_return

        # ── 设置当前函数上下文 ──
        self.current_function_name = node.name
        self.current_function_return_type = node.return_type
        self.current_function_has_return = False

        # ── 推入新作用域，让函数内变量不污染外部 ──
        self.symbol_table.push_scope(f"function:{node.name}")

        # ── 登记参数到当前作用域 ──
        # 参数类型标为 "p"，和变量 "v" 区分
        for param_name, param_type in node.params:
            if self.symbol_table.lookup_current(param_name):
                self._error(node, f"参数 '{param_name}' 已经声明过了", "duplicate_var")
            else:
                self.symbol_table.enter(param_name, param_type, "p")

        # ── 分析函数体（产生函数体内的四元式） ──
        self._analyze_statement(node.body)

        # ── 检查函数是否包含 return 语句 ──
        # 如果函数应有返回值（void 类型由语言定义决定）
        # 但 body 中没有出现 return，报缺少 return
        if not self.current_function_has_return:
            self._error(node, f"函数 '{node.name}' 缺少 return 语句")

        # ── 弹出函数作用域，恢复到外层函数状态 ──
        self.symbol_table.pop_scope()
        self.current_function_name = previous_name
        self.current_function_return_type = previous_return_type
        self.current_function_has_return = previous_has_return

    def _analyze_return(self, node: ReturnNode):
        """
        分析 return 语句。

        流程：
          1. 确认当前在函数体内（不能在顶层使用 return）
          2. 检查返回值类型是否与函数声明一致
          3. 生成返回值的求值指令
          4. 发射 return 四元式
          5. 标记当前函数已有 return（用于检测缺少 return）
        """
        # 确认当前在函数体内 （current_function_name 和 current_function_return_type 已设置）
        if not self.current_function_name or not self.current_function_return_type:
            self._error(node, "return 只能出现在函数体内")
            return

        # 检查return表达式类型是否与函数返回类型兼容
        value_type = self._infer_expression_type(node.value)
        if value_type and not self._assignment_compatible(self.current_function_return_type, node.value, value_type):
            self._error(
                node,
                f"函数 '{self.current_function_name}' 应返回 {self.current_function_return_type}，"
                f"但得到 {value_type}",
                "type_mismatch",
            )
            return

        # 生成返回值的求值指令，并发射 return 四元式
        addr = self._analyze_expression(node.value)
        self._emit("return", addr, "_", "_")
        # 标记当前函数已有 return 语句，供缺少 return 检测使用
        self.current_function_has_return = True

    # ── 数组操作分析 ──────────────────────────────────────────
    def _analyze_array_assign(self, node: ArrayAssignNode):
        """
        分析数组元素赋值 (array-set name index value)。

        四元式生成模式（地址计算过程）：
          目标：arr[i] = val

          NekoLang 中数组是一段连续内存，每个元素大小固定。
          要计算 arr[i] 的地址，需要：
            1. 计算偏移量 = 下标 × 元素字节大小
            2. 计算目标地址 = 数组基址 + 偏移量
            3. 存值到目标地址

          生成的四元式：
            (*, index_addr, size_addr, T1)       → T1 = index * elem_size
            (+, base_addr, T1, T2)               → T2 = base + offset
            (:=, value_addr, _, (T2))            → *(T2) = value  （间接赋值）

        注意第三行的 (T2) 带括号——括号表示"间接访问"（指针解引用），
        不是直接赋值给 T2 变量，而是赋值到 T2 指向的内存位置。
        """
        # 在符号表中寻找数组变量，检查存在且类型正确
        entry = self.symbol_table.lookup(node.name)
        if not entry:
            self._error(node, f"未定义的数组 '{node.name}'", "undefined_var")
            return
        if not entry.type.startswith("(array"):
            self._error(node, f"'{node.name}' 不是数组类型", "type_mismatch")
            return

        # 下标类型检查
        index_type = self._infer_expression_type(node.index)
        if index_type and index_type != "int":
            self._error(node.index, "数组下标必须是 int 类型", "type_mismatch")

        # 值类型检查 处理异常赋值
        elem_type = self._array_element_type(entry.type)
        value_type = self._infer_expression_type(node.value)
        if value_type and not self._assignment_compatible(elem_type, node.value, value_type):
            self._error(
                node.value,
                f"无法将 {value_type} 赋给 {elem_type} 类型的数组元素",
                "type_mismatch",
            )
            return

        # 地址计算四元式序列
        index_addr = self._analyze_expression(node.index)
        value_addr = self._analyze_expression(node.value)
        elem_size = self._array_element_size(entry.type)
        size_addr = self.symbol_table.get_const_addr(elem_size)
        temp1 = self.symbol_table.alloc_temp()
        self._emit("*", index_addr, size_addr, temp1)          # T1 = index * elem_size ，这个是offset
        base_addr = self.symbol_table.get_var_addr(node.name)
        temp2 = self.symbol_table.alloc_temp()
        self._emit("+", base_addr, temp1, temp2)               # T2 = base + offset
        self._emit(":=", value_addr, "_", f"({temp2})")        # *(T2) = value

    def _analyze_array_print(self, node: ArrayPrintNode):
        """
        分析数组元素打印 (array-print name index)。

        地址计算方式与 array-set 相同，
        只是最后发射的是 print 而非 :=。"""
        entry = self.symbol_table.lookup(node.name)
        if not entry:
            self._error(node, f"未定义的数组 '{node.name}'", "undefined_var")
            return
        if not entry.type.startswith("(array"):
            self._error(node, f"'{node.name}' 不是数组类型", "type_mismatch")
            return

        index_type = self._infer_expression_type(node.index)
        if index_type and index_type != "int":
            self._error(node.index, "数组下标必须是 int 类型", "type_mismatch")

        index_addr = self._analyze_expression(node.index)
        elem_size = self._array_element_size(entry.type)
        size_addr = self.symbol_table.get_const_addr(elem_size)
        temp1 = self.symbol_table.alloc_temp()
        self._emit("*", index_addr, size_addr, temp1)
        base_addr = self.symbol_table.get_var_addr(node.name)
        temp2 = self.symbol_table.alloc_temp()
        self._emit("+", base_addr, temp1, temp2)
        self._emit("print", f"({temp2})", "_", "_") # 打印 *(T2) 位置的值，这是主要区别与 array-set 的地方

    def _analyze_file_write(self, node: FileWriteNode):
        """
        分析文件写入语句 (write-类型 路径 值)。

        需要检查：
          - 路径必须是字符串
          - 值的类型必须与 write-int/float/char/bool 匹配
        """
        # 检查路径是否为字符串字面量（或能隐式转换为字符串的类型）
        path_type = self._infer_expression_type(node.path)
        if path_type != "string":
            self._error(node.path, "文件路径必须是字符串字面量", "type_mismatch")
            return

        # 检查赋值类型是否与 write-指令要求的类型兼容
        value_type = self._infer_expression_type(node.value)
        if value_type and not self._assignment_compatible(node.value_type, node.value, value_type):
            self._error(
                node.value,
                f"write-{node.value_type} 需要 {node.value_type} 类型的值，但得到 {value_type}",
                "type_mismatch",
            )
            return

        path_addr = self._analyze_expression(node.path)
        value_addr = self._analyze_expression(node.value)
        self._emit(f"write-{node.value_type}", path_addr, value_addr, "_") # 生成写文件的四元式

    def _validate_extern_signature(self, node: ExternDeclNode):
        """
        验证 extern 声明中的参数类型和返回类型是否被后端支持。

        当前支持的类型：
          基本类型：int, float, char, bool, string, pointer
          函数指针类型：(func (...))，且函数指针内部的参数类型也需支持
        不支持的类型：void、可变参数、数组参数
        """
        # 检查每个 参数类型 是否被支持
        for index, type_name in enumerate(node.param_types, start=1):
            if not self._is_supported_extern_type(type_name):
                self._error(
                    node,
                    f"extern '{node.name}' 的第 {index} 个参数类型 '{type_name}' 暂不支持",
                    "type_mismatch",
                )
        # 检查 返回类型 是否被支持
        if not self._is_supported_extern_type(node.return_type):
            self._error(
                node,
                f"extern '{node.name}' 的返回类型 '{node.return_type}' 暂不支持",
                "type_mismatch",
            )

    def _is_supported_extern_type(self, type_name: str) -> bool:
        """检查一个类型是否被 extern 支持（即能否在 C 函数签名中使用）。"""
        if type_name in {"int", "float", "char", "bool", "string", "pointer"}:
            return True
        # 函数指针类型需要递归检查其参数和返回类型是否支持
        if type_name.startswith("(func"):  # 函数指针类型需要递归检查
            signature = self._parse_func_type(type_name) # 从类型字符串解析出 FunctionSignature 包括 参数类型 和 返回类型
            if signature is None:
                return False # 这个if是为了防止 _parse_func_type 解析失败返回 None 的情况，虽然理论上只要 type_name.startswith("(func") 就应该能成功解析，但加个保险
            return all(self._is_supported_extern_type(param) for param in signature.param_types) and (
                self._is_supported_extern_type(signature.return_type) # 递归检查函数，因为这里extern可以嵌套
            )
        return False

    # ── 表达式分析 ──────────────────────────────────────────────

    def _analyze_expression(self, node: ASTNode) -> str:
        """
        分析一个表达式节点——生成求值指令，返回存放结果的地址。

        这是语义分析中最核心的方法之一。
        和 _infer_expression_type 不同（只推断类型），
        这个方法**真正生成四元式指令**来计算表达式的值。

        返回值是一个地址字符串，可以是：
          "I1"     — 变量地址
          "C1_42"  — 常量地址
          "T1"     — 临时变量地址（存放中间计算结果）
          "(T2)"   — 带括号的间接地址（数组元素或指针解引用）

        对于字面量和标识符，不产生新指令，直接返回地址。
        对于运算和函数调用，产生指令并返回结果临时变量的地址。

        举例：
          IntLiteralNode(42)   → 不产生指令，返回 "C1_42"
          IdentifierNode("x")  → 不产生指令，返回 "I1"
          BinOpNode("+", l, r) → 产生 (+, l_addr, r_addr, T1)，返回 "T1"
          FuncCallNode(f, a)   → 产生多条 param + call，返回 "T3"
        """
        # ── 字面量节点（不需要产生指令） ──
        if isinstance(node, IntLiteralNode):
            return self.symbol_table.get_const_addr(node.value)
        if isinstance(node, FloatLiteralNode):
            return self.symbol_table.get_const_addr(node.value)
        if isinstance(node, BoolLiteralNode):
            return self.symbol_table.get_const_addr(str(node.value).lower())
        if isinstance(node, StringLiteralNode):
            return self.symbol_table.get_const_addr(f'"{node.value}"')
        if isinstance(node, CharLiteralNode):
            return self.symbol_table.get_const_addr(f"'{node.value}'")

        # ── 标识符（变量引用） ──
        if isinstance(node, IdentifierNode):
            entry = self.symbol_table.lookup(node.name)
            if not entry:
                self._error(node, f"未定义的变量 '{node.name}'", "undefined_var")
                return "_"
            return self.symbol_table.get_var_addr(node.name) # 返回变量地址，例如 "I1"

        # ── 二元运算 (op left right) ──
        if isinstance(node, BinOpNode):
            left_addr = self._analyze_expression(node.left)
            right_addr = self._analyze_expression(node.right)
            temp = self.symbol_table.alloc_temp()
            self._emit(node.op, left_addr, right_addr, temp) # 需要生成四元式
            return temp # 返回存放结果的临时变量地址，例如 "T1"

        # ── Lambda 定义（作为表达式） ──
        if isinstance(node, LambdaDefNode):
            self._analyze_lambda_def(node)
            temp = self.symbol_table.alloc_temp() # 为 lambda 引用分配一个临时变量地址，例如 "T2"
            self._emit("lambda_ref", node.name, "_", temp)  # 发射 lambda 引用
            return temp # 返回 lambda 引用的地址

        # ── 函数调用 ──
        if isinstance(node, FuncCallNode):
            # 先查函数签名表
            signature = self.function_signatures.get(node.name)

            # 间接调用：函数名不在签名表中，但在符号表中是 (func ...) 类型 的变量，说明是函数指针变量
            if not signature:
                entry = self.symbol_table.lookup(node.name)
                if entry and entry.type.startswith("(func"):
                    sig = self._parse_func_type(entry.type)
                    if sig:
                        signature = sig

            if not signature:
                self._error(node, f"未定义的函数 '{node.name}'", "undefined_var")
                return "_"

            # 参数数量检查
            if len(node.args) != len(signature.param_types):
                self._error(
                    node,
                    f"函数 '{node.name}' 期望 {len(signature.param_types)} 个参数，"
                    f"但得到 {len(node.args)} 个",
                )
                return "_"

            # 每个参数的类型检查
            for index, (arg, expected_type) in enumerate(zip(node.args, signature.param_types), start=1):
                actual_type = self._infer_expression_type(arg)
                if actual_type and not self._assignment_compatible(expected_type, arg, actual_type):
                    self._error(
                        arg,
                        f"函数 '{node.name}' 的第 {index} 个参数应为 {expected_type}，"
                        f"但得到 {actual_type}",
                        "type_mismatch",
                    )
                    return "_"

            # 生成函数调用的四元式序列：先 param 传参，再 call 调用
            for arg in node.args:
                arg_addr = self._analyze_expression(arg)
                self._emit("param", arg_addr, "_", "_")       # 每个参数一条 param

            temp = self.symbol_table.alloc_temp()
            self._emit("call", node.name, str(len(node.args)), temp)  # 函数调用
            return temp

        # ── 数组访问（作为表达式） ──
        if isinstance(node, ArrayAccessNode):
            entry = self.symbol_table.lookup(node.name)
            # 先检查数组变量存在且类型正确
            if not entry:
                self._error(node, f"未定义的数组 '{node.name}'", "undefined_var")
                return "_"
            index_addr = self._analyze_expression(node.index)
            elem_size = self._array_element_size(entry.type)
            size_addr = self.symbol_table.get_const_addr(elem_size)
            temp1 = self.symbol_table.alloc_temp() # 计算偏移量的临时变量地址，例如 "T3"
            self._emit("*", index_addr, size_addr, temp1)
            base_addr = self.symbol_table.get_var_addr(node.name)
            temp2 = self.symbol_table.alloc_temp() # 计算目标地址的临时变量地址，例如 "T4"
            self._emit("+", base_addr, temp1, temp2)
            return f"({temp2})"  # 返回间接地址

        # ── 内建操作：命令行参数 ──
        if isinstance(node, ArgcNode):
            temp = self.symbol_table.alloc_temp()
            self._emit("argc", "_", "_", temp) # 生成获取 argc 的四元式，argc 返回的是命令行参数的总个数
            return temp
        if isinstance(node, ArgvNode):
            index_type = self._infer_expression_type(node.index)
            if index_type and index_type != "int": # argv-int/float/char/bool/string 是按指定类型解析某个具体的命令行参数值，所以下标必须是 int 类型
                self._error(node.index, "命令行参数下标必须是 int 类型", "type_mismatch")
                return "_"
            index_addr = self._analyze_expression(node.index)
            temp = self.symbol_table.alloc_temp()
            self._emit(f"argv-{node.value_type}", index_addr, "_", temp)
            return temp

        # ── 内建操作：用户输入 ──
        if isinstance(node, InputNode):
            temp = self.symbol_table.alloc_temp()
            self._emit(f"input-{node.value_type}", "_", "_", temp)
            return temp

        # ── 内建操作：随机数 ──
        if isinstance(node, RandomRangeNode):
            low_type = self._infer_expression_type(node.low)
            high_type = self._infer_expression_type(node.high)
            # 检查下界和上界的类型必须是 int，因为 rand-range 生成整数随机数，范围边界必须是整数
            if low_type and low_type != "int":
                self._error(node.low, "rand-range 的下界必须是 int 类型", "type_mismatch")
                return "_"
            if high_type and high_type != "int":
                self._error(node.high, "rand-range 的上界必须是 int 类型", "type_mismatch")
                return "_"
            low_addr = self._analyze_expression(node.low)
            high_addr = self._analyze_expression(node.high)
            temp = self.symbol_table.alloc_temp()
            self._emit("rand-range", low_addr, high_addr, temp)
            return temp

        # ── 内建操作：文件读取 ──
        if isinstance(node, FileReadNode):
            path_type = self._infer_expression_type(node.path)
            if path_type != "string":
                self._error(node.path, "文件路径必须是字符串字面量", "type_mismatch")
                return "_"
            path_addr = self._analyze_expression(node.path)
            temp = self.symbol_table.alloc_temp()
            self._emit(f"read-{node.value_type}", path_addr, "_", temp)
            return temp

        # ════════════════════════════════════════════════════════
        # 内建操作：字符串操作
        # ════════════════════════════════════════════════════════
        #
        # 这些操作的共同模式：
        #   1. 类型检查——确认操作数的类型是 string 或 int（视具体操作而定）
        #   2. str_addr / left_addr / right_addr — 用 _analyze_expression 计算操作数，
        #      返回存放该操作数值的寄存器/地址字符串（如 "I1" 或 "T1"）
        #   3. temp — 用 alloc_temp() 分配一个临时变量地址（如 "T5"），
        #      用于存放这个操作的**结果**
        #   4. _emit("操作名", ...) — 发射一条四元式，
        #      运行时就会调用 C 运行时中对应的函数执行实际操作
        #   5. return temp — 返回结果地址，供上层（赋值/打印/传参）使用
        #
        # 以 (string-length "hello") 为例：
        #   str_addr = "C1_"hello""  ← "hello" 这个字符串常量的地址
        #   temp     = "T5"          ← 存放结果的临时变量
        #   发射: (string-length, C1_"hello", _, T5)
        #   运行时效果: T5 = strlen("hello") → 5
        # ──

        if isinstance(node, StringLengthNode):
            self._check_expr_type(node, node.string_expr, "string", "string-length")
            str_addr = self._analyze_expression(node.string_expr) # 源字符串的地址
            temp = self.symbol_table.alloc_temp()                 # 分配临时变量存放结果（int 类型）
            self._emit("string-length", str_addr, "_", temp)
            return temp

        if isinstance(node, StringAtNode):
            self._check_expr_type(node, node.string_expr, "string", "string-at")
            self._check_expr_type(node, node.index, "int", "string-at")
            str_addr = self._analyze_expression(node.string_expr) # 源字符串的地址
            idx_addr = self._analyze_expression(node.index)       # 下标表达式的地址（int）
            temp = self.symbol_table.alloc_temp()                 # 存放结果的临时变量（char 类型）
            self._emit("string-at", str_addr, idx_addr, temp)
            return temp

        if isinstance(node, StringSubNode):
            self._check_expr_type(node, node.string_expr, "string", "string-sub")
            self._check_expr_type(node, node.start, "int", "string-sub")
            self._check_expr_type(node, node.length, "int", "string-sub")
            str_addr = self._analyze_expression(node.string_expr)   # 源字符串的地址
            start_addr = self._analyze_expression(node.start)       # 起始位置的地址（int）
            len_addr = self._analyze_expression(node.length)        # 子串长度的地址（int）
            temp = self.symbol_table.alloc_temp()                  # 存放结果的临时变量（string 类型）
            self._emit("string-sub", str_addr, f"{start_addr},{len_addr}", temp)
            return temp

        if isinstance(node, StringCmpNode):
            self._check_expr_type(node, node.left, "string", "string-cmp")
            self._check_expr_type(node, node.right, "string", "string-cmp")
            left_addr = self._analyze_expression(node.left)   # 左比较字符串的地址
            right_addr = self._analyze_expression(node.right) # 右比较字符串的地址
            temp = self.symbol_table.alloc_temp()             # 存放比较结果（int：-1/0/1）
            self._emit("string-cmp", left_addr, right_addr, temp)
            return temp

        if isinstance(node, StringContainsNode):
            self._check_expr_type(node, node.haystack, "string", "string-contains")
            self._check_expr_type(node, node.needle, "string", "string-contains")
            hay_addr = self._analyze_expression(node.haystack)    # 被搜索的字符串地址
            needle_addr = self._analyze_expression(node.needle)   # 要查找的子串地址
            temp = self.symbol_table.alloc_temp()                 # 存放结果（bool：true/false）
            self._emit("string-contains", hay_addr, needle_addr, temp)
            return temp

        if isinstance(node, IntToStringNode):
            self._check_expr_type(node, node.int_expr, "int", "int-to-string")
            int_addr = self._analyze_expression(node.int_expr) # 要转换的整数的值地址
            temp = self.symbol_table.alloc_temp()              # 存放结果字符串地址（string 类型）
            self._emit("int-to-string", int_addr, "_", temp)
            return temp

        if isinstance(node, StringToIntNode):
            self._check_expr_type(node, node.string_expr, "string", "string-to-int")
            str_addr = self._analyze_expression(node.string_expr) # 要解析的字符串地址
            temp = self.symbol_table.alloc_temp()                 # 存放解析结果（int 类型）
            self._emit("string-to-int", str_addr, "_", temp)
            return temp

        if isinstance(node, ArgvStringNode):
            self._check_expr_type(node, node.index, "int", "argv-string")
            index_addr = self._analyze_expression(node.index) # 命令行参数的下标地址
            temp = self.symbol_table.alloc_temp()             # 存放参数字符串（string 类型）
            self._emit("argv-string", index_addr, "_", temp)
            return temp

        # ════════════════════════════════════════════════════════
        # 内建操作：字符操作
        # ════════════════════════════════════════════════════════
        #
        # 字符操作的共同模式和字符串操作完全一样：
        #   char_addr — 字符操作数的地址
        #   int_addr  — 整数操作数的地址
        #   temp      — 存放结果的临时变量
        #   发射一条四元式 → 运行时调用 C 函数
        # ──

        if isinstance(node, CharToIntNode):
            self._check_expr_type(node, node.char_expr, "char", "char-to-int")
            char_addr = self._analyze_expression(node.char_expr) # 源字符的地址
            temp = self.symbol_table.alloc_temp()                # 存放 ASCII 码结果（int）
            self._emit("char-to-int", char_addr, "_", temp)
            return temp

        if isinstance(node, IntToCharNode):
            self._check_expr_type(node, node.int_expr, "int", "int-to-char")
            int_addr = self._analyze_expression(node.int_expr)   # ASCII 码整数的地址
            temp = self.symbol_table.alloc_temp()                # 存放转换后的字符（char）
            self._emit("int-to-char", int_addr, "_", temp)
            return temp

        if isinstance(node, CharToStringNode):
            self._check_expr_type(node, node.char_expr, "char", "char-to-string")
            char_addr = self._analyze_expression(node.char_expr) # 源字符的地址
            temp = self.symbol_table.alloc_temp()                # 存放结果字符串（string，长度为1）
            self._emit("char-to-string", char_addr, "_", temp)
            return temp

        if isinstance(node, IsLetterNode):
            self._check_expr_type(node, node.char_expr, "char", "is-letter")
            char_addr = self._analyze_expression(node.char_expr) # 要判断的字符地址
            temp = self.symbol_table.alloc_temp()                # 存放判断结果（bool）
            self._emit("is-letter", char_addr, "_", temp)
            return temp

        if isinstance(node, IsDigitNode):
            self._check_expr_type(node, node.char_expr, "char", "is-digit")
            char_addr = self._analyze_expression(node.char_expr) # 要判断的字符地址
            temp = self.symbol_table.alloc_temp()                # 存放判断结果（bool）
            self._emit("is-digit", char_addr, "_", temp)
            return temp

        if isinstance(node, CharUpcaseNode):
            self._check_expr_type(node, node.char_expr, "char", "char-upcase")
            char_addr = self._analyze_expression(node.char_expr) # 源字符地址
            temp = self.symbol_table.alloc_temp()                # 存放转换后的字符（char）
            self._emit("char-upcase", char_addr, "_", temp)
            return temp

        if isinstance(node, CharDowncaseNode):
            self._check_expr_type(node, node.char_expr, "char", "char-downcase")
            char_addr = self._analyze_expression(node.char_expr) # 源字符地址
            temp = self.symbol_table.alloc_temp()                # 存放转换后的字符（char）
            self._emit("char-downcase", char_addr, "_", temp)
            return temp

        return "_"

    # ── 类型推断 ──────────────────────────────────────────────

    def _infer_expression_type(self, node: ASTNode) -> str | None:
        """
        推断 AST 表达式的 NekoLang 类型。

        这个方法不生成四元式，**只做类型推断**。
        用于赋值的类型兼容性检查和函数参数类型检查。

        对于大多数节点，类型是确定的：
          IntLiteralNode    → "int"
          FloatLiteralNode  → "float"
          BoolLiteralNode   → "bool"
          BinOpNode(+)      → 根据操作数类型：两 int → int，有 float → float，两 string → string
          BinOpNode(<)      → "bool"
          FuncCallNode      → 从函数签名表的 return_type 获取
          ...

        对于标识符节点，需要查符号表获取其声明类型。
        如果是函数名（cat == "f"），返回其函数类型 (func (...)...)。
        """
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
            entry = self.symbol_table.lookup(node.name) # 先查符号表获取标识符的声明信息
            if entry:
                if entry.cat == "f" and entry.name in self.function_signatures:
                    #如果获取到f,并且这个f在函数签名表里有记录，就从函数签名表里获取这个函数的参数类型和返回类型，
                    # 构造出一个字符串形式的函数类型返回，例如 (func (int float) string) 
                    sig = self.function_signatures[entry.name] 
                    return f"(func ({' '.join(sig.param_types)}) {sig.return_type})"
                return entry.type
            return None
        # 对于lambda定义节点，构造一个字符串形式的函数类型返回，例如 (func (int float) string)，
        if isinstance(node, LambdaDefNode):
            return f"(func ({' '.join(t for _, t in node.params)}) {node.return_type})"
        # 对于函数调用节点，先查函数签名表获取返回类型，如果找不到，再检查是否是函数指针变量（符号表中类型为 (func ...)），从中解析出返回类型
        if isinstance(node, FuncCallNode):
            signature = self.function_signatures.get(node.name)
            if signature:
                return signature.return_type # 直接调用：从函数签名表获取返回类型
            # 间接调用：从变量类型恢复返回类型
            entry = self.symbol_table.lookup(node.name)
            if entry and entry.type.startswith("(func"):
                sig = self._parse_func_type(entry.type)
                if sig:
                    return sig.return_type
            return None
        # 对于数组访问节点，返回数组元素的类型，例如 int、float、char 等
        if isinstance(node, ArrayAccessNode):
            entry = self.symbol_table.lookup(node.name)
            if entry and entry.type.startswith("(array"):
                return self._array_element_type(entry.type)
            return None
        # 内建操作的类型是固定的
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
        # ── 二元运算的类型推断 ──
        if isinstance(node, BinOpNode):
            # 先推断左右表达式的类型
            left_type = self._infer_expression_type(node.left)
            right_type = self._infer_expression_type(node.right)
            if not left_type or not right_type:
                return None

            # 比较运算（<, >, =, <=, >=, !=）总是返回 bool
            if node.op in {"<", ">", "=", "<=", ">=", "!="}:
                # pointer 比较的特殊处理
                if left_type == "pointer" or right_type == "pointer":
                    if left_type == "pointer" and right_type == "pointer":
                        return "bool"
                    if left_type == "pointer" and right_type == "int" and self._is_null_pointer_literal(node.right):
                        return "bool"
                    if right_type == "pointer" and left_type == "int" and self._is_null_pointer_literal(node.left):
                        return "bool"
                    self._error(node, f"pointer 只能与 pointer 或字面量 0 比较，但得到 {left_type} 与 {right_type}", "type_mismatch")
                    return "bool"
                # 字符串比较只能使用 = 和 !=，不支持 < > 等
                if left_type == "string" or right_type == "string":
                    if node.op not in {"=", "!="}:
                        self._error(node, f"字符串只能用 = 和 != 比较，不能用 {node.op}，请使用 string-cmp", "type_mismatch")
                    elif left_type != "string" or right_type != "string":
                        self._error(node, f"无法比较 {left_type} 与 {right_type}", "type_mismatch")
                    return "bool"
                if self._types_compatible(left_type, right_type) or self._types_compatible(right_type, left_type):
                    return "bool"
                self._error(node, f"无法比较 {left_type} 与 {right_type}", "type_mismatch")
                return "bool"

            # 算术运算（+, -, *, /）
            if node.op in {"+", "-", "*", "/"}:
                # 字符串拼接（+ 操作左右都是 string 时返回 string）
                if node.op == "+" and (left_type == "string" or right_type == "string"):
                    if left_type == "string" and right_type == "string":
                        return "string"
                    self._error(node, f"字符串拼接要求两侧都是 string，但得到 {left_type} 与 {right_type}", "type_mismatch")
                    return "string"
                # 有一方是 float → 结果为 float
                if left_type == "float" or right_type == "float":
                    return "float"
                # 两方都是 int → 结果为 int
                if left_type == "int" and right_type == "int":
                    return "int"
                self._error(node, f"算术运算不支持 {left_type} 与 {right_type}", "type_mismatch")
                return None

        return None

    # ── 类型系统（类型兼容性检查） ────────────────────────────
    def _types_compatible(self, expected: str, actual: str) -> bool:
        """
        检查两种类型是否兼容（用于二元运算的操作数类型匹配）。

        兼容规则：
          - 相同类型自然兼容
          - float 可以接受 int 和 char（自动提升类型）
          - int 可以接受 char（自动提升类型）
          - 其他不兼容（bool 不能和 int 混用等）

        在 NekoLang 中，类型提升是隐式的，
        不需要程序员手动写类型转换（区别于更严格的类型系统）。
        """
        # 这里actual是实际类型，expected是期望类型，判断实际类型能否隐式转换为期望类型
        if expected == actual:
            return True
        if expected == "float" and actual in ("int", "char"):
            return True
        if expected == "int" and actual == "char":
            return True
        return False

    def _assignment_compatible(self, expected: str, node: ASTNode, actual: str) -> bool:
        """
        检查赋值操作的类型兼容性。

        在 _types_compatible 的基础上增加了一条规则：
          pointer 类型可以从整数 0 赋值（空指针）。
          这允许 (:= p 0) 将指针变量设为 NULL。

        其他规则与 _types_compatible 相同。
        """
        if expected == "pointer" and actual == "int":
            return self._is_null_pointer_literal(node)
        return self._types_compatible(expected, actual)

    def _is_condition_type(self, type_name: str) -> bool:
        """
        判断一个类型是否可以用作 if/while 的条件表达式。

        允许的条件类型：bool, int, float, char
        （在 C 的语义中，非零值视为真，零视为假）

        不允许的条件类型：string, pointer, (func ...), (array ...)
        """
        if (
            type_name.startswith("(func")
            or type_name.startswith("(array")
            or type_name in {"string", "pointer"}
        ):
            return False
        return type_name in {"bool", "int", "float", "char"}

    def _check_expr_type(self, node: ASTNode, expr: ASTNode, expected: str, op_name: str) -> bool:
        """
        检查表达式 expr 的类型是否与 expected 匹配。
        用于内建操作（string-length、char-to-int 等）的参数类型检查。

        参数：
          node     — 内建操作节点（用于报错定位）
          expr     — 要检查类型的表达式子节点
          expected — 期望的类型
          op_name  — 操作名（用于报错信息）

        返回：
          True  — 类型匹配或无法推断（不阻塞后续检查）
          False — 类型不匹配
        """
        actual = self._infer_expression_type(expr)
        if actual and not self._types_compatible(expected, actual):
            # 对于不兼容的类型，报告错误，但继续分析（返回 False）以便发现更多错误，而不是因为一个错误就停止检查
            self._error(expr, f"{op_name} 需要 {expected} 类型，但得到 {actual}", "type_mismatch")
            return False
        return True

    def _array_element_type(self, type_name: str) -> str:
        """从数组类型字符串中提取元素类型。
           例如 "(array int 10)" → "int" """
        parts = type_name.rstrip(")").split()
        return parts[1] if len(parts) > 1 else "int"

    def _array_element_size(self, type_name: str) -> int:
        """计算数组元素类型的字节大小。
           例如 "(array int 10)" → 4（int 是 4 字节） """
        from .tokens import TYPE_SIZES

        return TYPE_SIZES.get(self._array_element_type(type_name), 4)

    def dump_quadruples(self) -> str:
        """
        将四元式列表格式化为可读的文本形式。
        对应 uv run neko check <file.neko> 命令的输出。
        每行格式：序号: (op, ob1, ob2, t)
        """
        lines = []
        for i, q in enumerate(self.quadruples, 1):
            lines.append(f"{i:3}: {q}")
        return "\n".join(lines)
