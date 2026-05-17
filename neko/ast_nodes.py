"""
抽象语法树节点定义（AST Nodes）

编译原理角色：
  语法分析器（Parser）的输出产物是抽象语法树（Abstract Syntax Tree, AST）。
  AST 是源代码的树状中间表示，去掉了 Token 序列中与语法结构无关的细节
  （如括号、分隔符等），只保留"程序的结构"。

  例如，源码 (program hello (begin (print "hi"))) 对应的 AST：
    ProgramNode("hello")
      └── BlockNode
            └── BeginBlockNode
                  └── PrintNode
                        └── StringLiteralNode("hi")

  每一类 AST 节点代表一种语法结构：
    - 程序结构：ProgramNode, BlockNode, BeginBlockNode
    - 声明：VarDeclNode, FuncDefNode, ExternDeclNode
    - 语句：AssignNode, IfNode, WhileNode, PrintNode, ReturnNode
    - 表达式：BinOpNode, FuncCallNode, 各类字面量节点
    - 内建操作：ArgvNode, InputNode, FileReadNode, 字符串/字符操作节点

  后续流水线：
    语义分析器从 AST 遍历并生成三地址码（四元式），不直接操作 Token。
    所以 AST 是"语法分析 → 语义分析"的接口契约（contract）。

实现方式：
  所有节点继承自 ASTNode 基类，使用 Python @dataclass 自动生成 __init__ 和 __repr__。
  每个节点存储自身需要的语义字段 + 源码位置（line, column）用于报错定位。

  dump_ast() 函数用于将 AST 树格式化为可读的文本输出，
  对应 uv run neko ast <file.neko> 命令。
"""

from dataclasses import dataclass, field


# ── 基类 ────────────────────────────────────────────────────

class ASTNode:
    """
    AST 节点的基类。

    所有节点都包含 line 和 column 两个位置属性，
    指向源码中对应结构的起始位置。
    当语义分析或代码生成报错时，用这两个字段定位到具体行列。

    注意：这不是 @dataclass，子类各自用 @dataclass 定义自己的字段。
    但基类的 line/column 被子类继承，
    所以每个子类仍需要显式声明 line/column 字段覆盖基类默认值。
    """
    line: int = 0
    column: int = 0


# ══════════════════════════════════════════════════════════════
# 顶层结构
# ══════════════════════════════════════════════════════════════

@dataclass
class ImportNode(ASTNode):
    """
    导入语句节点。

    对应源码：(import 模块名)
    示例：(import math-utils)

    语义分析阶段，build_utils.py 会递归解析被导入的文件，
    将其中的函数定义合并到当前程序的 AST 中。
    """
    path: str = ""             # 模块路径，如 "math-utils"
    line: int = 0
    column: int = 0


@dataclass
class ProgramNode(ASTNode):
    """
    程序根节点。一棵 AST 的根永远是这个类型。

    对应源码：(program 程序名 (var ...) (begin ...))

    imports 在 (program ...) 之前出现：
      (import a)
      (import b)
      (program main ...)

    parser.parse() 会先收集 imports，
    再解析 (program ...) 的主体，最后组装成 ProgramNode。
    """
    name: str = ""                    # 程序名，如 "hello"
    block: 'BlockNode' = field(default_factory=lambda: BlockNode())   # 变量声明 + begin 块
    imports: list['ImportNode'] = field(default_factory=list)         # 导入列表
    line: int = 0
    column: int = 0


# ══════════════════════════════════════════════════════════════
# 块结构（作用域相关）
# ══════════════════════════════════════════════════════════════

@dataclass
class BlockNode(ASTNode):
    """
    块节点：变量声明 + begin 块。

    一个块中变量声明（var）必须先出现，然后是一个 begin 复合块。
    BlockNode 起到"作用域容器"的作用：
    语义分析时，BlockNode 中的变量属于当前作用域。

    对应源码结构：
      (var (x int) (y float))   ← var_decls
      (begin                     ← body
        (:= x 10)
        (print y)
      )
    """
    var_decls: list['VarDeclNode'] = field(default_factory=list)   # 变量声明列表（可空）
    body: 'BeginBlockNode' = field(default_factory=lambda: BeginBlockNode())  # begin 复合块
    line: int = 0
    column: int = 0


@dataclass
class VarDeclNode(ASTNode):
    """
    变量声明节点。

    对应源码：(var (变量名1 类型1) (变量名2 类型2) ...)
    示例：(var (x int) (y float))

    variables 是 (名称, 类型) 对列表。
    类型可以是基本类型（int, float, char, bool, string）
    或复合类型（(array int 10), (func (int) bool)）。
    """
    variables: list[tuple[str, str]] = field(default_factory=list)  # [(name, type), ...]
    line: int = 0
    column: int = 0


@dataclass
class BeginBlockNode(ASTNode):
    """
    复合语句块节点。

    对应源码：(begin 语句1 语句2 ...)
    示例：(begin (print 1) (print 2) (:= x 10))

    begin 块内的语句按顺序逐个执行。
    if/while 的分支体也是通过 _parse_statement() 返回的，
    所以 statements 可以包含任意类型的语句节点（赋值、if、while 等）。
    """
    statements: list[ASTNode] = field(default_factory=list)  # 子语句列表
    line: int = 0
    column: int = 0


# ══════════════════════════════════════════════════════════════
# 语句类节点
# ══════════════════════════════════════════════════════════════

@dataclass
class AssignNode(ASTNode):
    """
    赋值语句节点。

    对应源码：(:= 变量名 表达式)
    示例：(:= x 10), (:= y (+ x 1))

    注意 NekoLang 中 := 是语句级别的操作，不是表达式。
    赋值不能嵌套在表达式中（这一点和 C 不同）。
    """
    target: str = ""           # 变量名
    value: ASTNode = field(default_factory=ASTNode)   # 右侧表达式的 AST
    line: int = 0
    column: int = 0


@dataclass
class IfNode(ASTNode):
    """
    条件分支语句节点。

    对应源码：(if 条件 真分支 假分支)
    示例：(if (> x 0) (print "正数") (print "非正数"))

    then_branch 和 else_branch 都是 ASTNode，
    可以是任意语句类型（包括另一个 if，形成嵌套分支）。
    """
    condition: ASTNode = field(default_factory=ASTNode)    # 条件表达式
    then_branch: ASTNode = field(default_factory=ASTNode)  # 真分支
    else_branch: ASTNode = field(default_factory=ASTNode)  # 假分支
    line: int = 0
    column: int = 0


@dataclass
class WhileNode(ASTNode):
    """
    循环语句节点。

    对应源码：(while 条件 循环体)
    示例：(while (< i 10) (begin (print i) (:= i (+ i 1))))
    """
    condition: ASTNode = field(default_factory=ASTNode)  # 循环条件表达式
    body: ASTNode = field(default_factory=ASTNode)       # 循环体语句
    line: int = 0
    column: int = 0


@dataclass
class PrintNode(ASTNode):
    """
    打印语句节点。

    对应源码：(print 表达式)
    示例：(print (+ 1 2)), (print "hello")
    """
    value: ASTNode = field(default_factory=ASTNode)  # 要打印的表达式
    line: int = 0
    column: int = 0


@dataclass
class ReturnNode(ASTNode):
    """
    函数返回语句节点。

    对应源码：(return 表达式)
    示例：(return 42), (return (+ x y))
    """
    value: ASTNode = field(default_factory=ASTNode)  # 返回值表达式
    line: int = 0
    column: int = 0


# ══════════════════════════════════════════════════════════════
# 表达式类节点
# ══════════════════════════════════════════════════════════════

@dataclass
class BinOpNode(ASTNode):
    """
    二元运算符表达式节点。

    对应源码：(操作符 左操作数 右操作数)
    示例：(+ 1 2), (< x 10), (= result 0)

    这里的 op 是操作符的字符串形式（"+", "-", "<", "=", "and" 等）。
    语义分析时根据 op 字符串决定进行哪种运算。
    """
    op: str = ""                    # 操作符："+", "-", "*", "/", "=", "<", ">", "and", "or"...
    left: ASTNode = field(default_factory=ASTNode)    # 左操作数表达式
    right: ASTNode = field(default_factory=ASTNode)   # 右操作数表达式
    line: int = 0
    column: int = 0


@dataclass
class IdentifierNode(ASTNode):
    """
    标识符引用节点（变量引用或函数名引用）。

    对应源码：变量名（无括号包裹，独立出现）
    示例：x, factorial, my-var

    这个节点表示"使用一个变量或函数的名字"。
    语义分析时，会到符号表中查找这个名字对应的地址。
    """
    name: str = ""      # 变量名/函数名
    line: int = 0
    column: int = 0


# ── 字面量节点 ──────────────────────────────────────────────

@dataclass
class IntLiteralNode(ASTNode):
    """
    整数字面量节点。

    对应源码：一个整数字面量
    示例：42, 0, -3（-3 在 AST 中是 BinOpNode('-', 0, 3)，不是 IntLiteralNode(-3)）
    """
    value: int = 0
    line: int = 0
    column: int = 0


@dataclass
class FloatLiteralNode(ASTNode):
    """
    浮点数字面量节点。

    对应源码：一个浮点数字面量
    示例：3.14, 0.5
    """
    value: float = 0.0
    line: int = 0
    column: int = 0


@dataclass
class BoolLiteralNode(ASTNode):
    """
    布尔字面量节点。

    对应源码：true 或 false
    """
    value: bool = False
    line: int = 0
    column: int = 0


@dataclass
class StringLiteralNode(ASTNode):
    """
    字符串字面量节点。

    对应源码："双引号包起来的字符序列"
    示例："hello", "你好"
    """
    value: str = ""
    line: int = 0
    column: int = 0


@dataclass
class CharLiteralNode(ASTNode):
    """
    字符字面量节点。

    对应源码：'单个字符' 或 '转义序列'
    示例：'a', '\n'
    """
    value: str = ""      # 字符值（解析后的内容，如换行符 \n 已转为实际字符）
    line: int = 0
    column: int = 0


# ══════════════════════════════════════════════════════════════
# 函数相关节点
# ══════════════════════════════════════════════════════════════

@dataclass
class FuncDefNode(ASTNode):
    """
    函数定义节点。

    对应源码：(function 函数名 ((参数名 类型)...) 返回类型 函数体)
    示例：(function factorial ((n int)) int
           (if (= n 1) 1 (* n (factorial (- n 1)))))

    语义分析时：
      1. 先收集所有函数签名（第一遍遍历）
      2. 再逐个分析函数体（第二遍遍历）
      这样同文件内的函数可以互相前向调用。
    """
    name: str = ""                            # 函数名
    params: list[tuple[str, str]] = field(default_factory=list)  # [(参数名, 类型), ...]
    return_type: str = ""                     # 返回类型，如 "int", "float"
    body: ASTNode = field(default_factory=ASTNode)  # 函数体（一个语句节点）
    line: int = 0
    column: int = 0


@dataclass
class ExternDeclNode(ASTNode):
    """
    外部函数声明节点。

    对应源码：(extern 函数名 (参数类型...) 返回类型)
    示例：(extern printf (string) int)

    类似 C 语言的函数声明（函数原型），告诉编译器：
    这个函数在运行时存在（由 runtime.c 或其他库提供），
    不需要生成函数体，只需要知道它的签名用于类型检查和代码生成。
    """
    name: str = ""                            # 外部函数名（对应 C 函数名）
    param_types: list[str] = field(default_factory=list)  # 参数类型列表
    return_type: str = ""                     # 返回类型
    line: int = 0
    column: int = 0


@dataclass
class LambdaDefNode(ASTNode):
    """
    Lambda（匿名函数）定义节点。

    对应源码：(lambda (参数列表) 返回类型 函数体)
    示例：(lambda ((x int) (y int)) int (+ x y))

    lambda 和 function 的区别：
      - function 有名字，放在顶层，是具名函数定义
      - lambda 没有名字，可以作为表达式出现在任何地方，创建函数对象
        （在 NekoLang 中本质是函数指针）

    name 字段：语义分析阶段可能会为 lambda 自动生成一个内部名称
    （如 "__lambda_1"），用于代码生成时的符号标识。
    """
    name: str = ""                            # 语义分析时自动生成的内部名称（初始为空）
    params: list[tuple[str, str]] = field(default_factory=list)  # [(参数名, 类型), ...]
    return_type: str = ""                     # 返回类型
    body: ASTNode = field(default_factory=ASTNode)  # lambda 体
    line: int = 0
    column: int = 0


@dataclass
class FuncCallNode(ASTNode):
    """
    函数调用表达式节点。

    对应源码：(函数名 参数1 参数2 ...)
    示例：(factorial 5), (+ 1 2)

    注意：在 NekoLang 中，二元运算符如 (+ 1 2) 有两种可能：
      - 如果 + 被当作普通标识符 → FuncCallNode("+", [1, 2])
      - 如果 + 被当作操作符    → BinOpNode("+", 1, 2)
    在 parser._parse_expression() 中：
      IDENTIFIER 类型的 Token → FuncCallNode
      其他类型（PLUS, MINUS...）→ BinOpNode
    实际上 + 等在 tokens.py 中定义了自己的 TokenType，不是 IDENTIFIER，
    所以 (+ 1 2) 会被解析为 BinOpNode。
    """
    name: str = ""                    # 函数名
    args: list[ASTNode] = field(default_factory=list)  # 函数参数表达式列表
    line: int = 0
    column: int = 0


# ══════════════════════════════════════════════════════════════
# 数组操作节点
# ══════════════════════════════════════════════════════════════

@dataclass
class ArrayAccessNode(ASTNode):
    """
    数组元素访问节点（表达式层面）。

    对应源码：数组名[下标]
    在 NekoLang 中数组访问用指针语法：(arr + offset) 或类似方式。

    注意：ArrayAccessNode 在某些实现中由表达式解析产生，
    NekoLang 当前版本的实际使用在语义分析中处理。
    """
    name: str = ""                     # 数组变量名
    index: ASTNode = field(default_factory=ASTNode)  # 下标表达式
    line: int = 0
    column: int = 0


@dataclass
class ArrayAssignNode(ASTNode):
    """
    数组元素赋值语句节点。

    对应源码：(array-set 数组名 下标 值)
    示例：(array-set arr 3 42)  将 arr[3] 赋值为 42
    """
    name: str = ""                     # 数组变量名
    index: ASTNode = field(default_factory=ASTNode)  # 下标表达式
    value: ASTNode = field(default_factory=ASTNode)  # 要赋的值表达式
    line: int = 0
    column: int = 0


@dataclass
class ArrayPrintNode(ASTNode):
    """
    数组元素打印语句节点。

    对应源码：(array-print 数组名 下标)
    示例：(array-print arr 3)  打印 arr[3]
    """
    name: str = ""                     # 数组变量名
    index: ASTNode = field(default_factory=ASTNode)  # 下标表达式
    line: int = 0
    column: int = 0


# ══════════════════════════════════════════════════════════════
# 命令行参数与输入/输出节点
# ══════════════════════════════════════════════════════════════

@dataclass
class ArgcNode(ASTNode):
    """
    命令行参数个数节点（argc）。

    对应源码：(argc)
    返回程序启动时传入的命令行参数数量（类似 C 的 argc）。
    """
    line: int = 0
    column: int = 0


@dataclass
class ArgvNode(ASTNode):
    """
    命令行参数值节点（argv，按类型分类）。

    对应源码：(argv-int 下标), (argv-float 下标), (argv-bool 下标), (argv-char 下标)
    示例：(argv-int 1)  读取第二个命令行参数，解释为整数

    value_type 表明以什么类型来解析参数字符串：
      "int"   → 将参数字符串解析为整数
      "float" → 将参数字符串解析为浮点数
      "bool"  → 将参数字符串解析为布尔值
      "char"  → 取参数字符串的第一个字符
    """
    value_type: str = "int"                    # 解析类型
    index: ASTNode = field(default_factory=ASTNode)  # 下标表达式
    line: int = 0
    column: int = 0


@dataclass
class InputNode(ASTNode):
    """
    用户输入节点（从标准输入读取）。

    对应源码：(input-int), (input-float), (input-char), (input-bool)
    读取用户输入的一行，按指定类型解析。

    value_type 同 ArgvNode.value_type，决定输入字符串如何解析。
    """
    value_type: str = "int"                    # 解析类型（int/float/char/bool）
    line: int = 0
    column: int = 0


@dataclass
class RandomSeedNode(ASTNode):
    """
    随机数种子设置语句节点。

    对应源码：(rand-seed 种子值)
    示例：(rand-seed 42)

    为随机数生成器设置种子，使得程序每次运行产生相同的随机序列。
    """
    seed: ASTNode = field(default_factory=ASTNode)  # 种子值表达式
    line: int = 0
    column: int = 0


@dataclass
class RandomRangeNode(ASTNode):
    """
    随机数范围生成表达式节点。

    对应源码：(rand-range 下界 上界)
    示例：(rand-range 1 100)  在 [1, 100] 范围内生成随机整数
    """
    low: ASTNode = field(default_factory=ASTNode)   # 下界表达式
    high: ASTNode = field(default_factory=ASTNode)  # 上界表达式
    line: int = 0
    column: int = 0


@dataclass
class FileReadNode(ASTNode):
    """
    文件读取表达式节点。

    对应源码：(read-int 路径), (read-float 路径)
    示例：(read-int "data.txt")  从 data.txt 读取一个整数

    value_type 决定从文件读取后的解析类型。
    ```
    """
    value_type: str = "int"                    # 读取值的类型
    path: ASTNode = field(default_factory=ASTNode)  # 文件路径表达式
    line: int = 0
    column: int = 0


@dataclass
class FileWriteNode(ASTNode):
    """
    文件写入语句节点。

    对应源码：(write-int 路径 值), (write-float 路径 值)
    示例：(write-int "data.txt" 42)  将整数 42 写入 data.txt

    value_type 决定写入值的类型，路径和值都是运行时计算的表达式。
    """
    value_type: str = "int"                    # 写入值的类型
    path: ASTNode = field(default_factory=ASTNode)  # 文件路径表达式
    value: ASTNode = field(default_factory=ASTNode)  # 要写入的值表达式
    line: int = 0
    column: int = 0


# ══════════════════════════════════════════════════════════════
# 字符串内建操作节点
# ══════════════════════════════════════════════════════════════

@dataclass
class StringLengthNode(ASTNode):
    """(string-length 字符串) → 返回字符串长度"""
    string_expr: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class StringAtNode(ASTNode):
    """(string-at 字符串 下标) → 返回字符串指定位置的字符"""
    string_expr: ASTNode = field(default_factory=ASTNode)
    index: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class StringSubNode(ASTNode):
    """(string-sub 字符串 起始位置 长度) → 返回子串"""
    string_expr: ASTNode = field(default_factory=ASTNode)
    start: ASTNode = field(default_factory=ASTNode)
    length: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class StringCmpNode(ASTNode):
    """(string-cmp 字符串1 字符串2) → 比较两个字符串，返回 -1/0/1"""
    left: ASTNode = field(default_factory=ASTNode)
    right: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class StringContainsNode(ASTNode):
    """(string-contains 字符串 子串) → 判断字符串是否包含子串，返回 bool"""
    haystack: ASTNode = field(default_factory=ASTNode)  # 被搜索的字符串
    needle: ASTNode = field(default_factory=ASTNode)    # 要查找的子串
    line: int = 0
    column: int = 0


@dataclass
class IntToStringNode(ASTNode):
    """(int-to-string 整数) → 将整数转换为字符串"""
    int_expr: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class StringToIntNode(ASTNode):
    """(string-to-int 字符串) → 将字符串解析为整数"""
    string_expr: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class ArgvStringNode(ASTNode):
    """(argv-string 下标) → 获取命令行参数的原始字符串值（不做类型解析）"""
    index: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


# ══════════════════════════════════════════════════════════════
# 字符内建操作节点
# ══════════════════════════════════════════════════════════════

@dataclass
class CharToIntNode(ASTNode):
    """(char-to-int 字符) → 将字符转换为对应的 ASCII 码整数"""
    char_expr: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class IntToCharNode(ASTNode):
    """(int-to-char 整数) → 将 ASCII 码整数转换为对应的字符"""
    int_expr: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class CharToStringNode(ASTNode):
    """(char-to-string 字符) → 将单个字符转换为长度为 1 的字符串"""
    char_expr: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class IsLetterNode(ASTNode):
    """(is-letter 字符) → 判断字符是否为字母，返回 bool"""
    char_expr: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class IsDigitNode(ASTNode):
    """(is-digit 字符) → 判断字符是否为数字，返回 bool"""
    char_expr: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class CharUpcaseNode(ASTNode):
    """(char-upcase 字符) → 将小写字母转换为大写，非字母原样返回"""
    char_expr: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


@dataclass
class CharDowncaseNode(ASTNode):
    """(char-downcase 字符) → 将大写字母转换为小写，非字母原样返回"""
    char_expr: ASTNode = field(default_factory=ASTNode)
    line: int = 0
    column: int = 0


# ══════════════════════════════════════════════════════════════
# AST 可视化输出
# ══════════════════════════════════════════════════════════════

def dump_ast(node: ASTNode, indent: int = 0) -> str:
    """
    将 AST 树格式化为可读的文本树状结构（用于调试和 `uv run neko ast` 命令）。

    参数：
      node   — 要输出的 AST 根节点
      indent — 当前缩进层级（递归时递增）

    返回：
      格式化的树状字符串，每个节点一行，缩进表示嵌套层级。

    例如对于：
      (program hello
        (begin
          (print (+ 1 2))))

    输出：
      Program(hello)
        BeginBlock
          Print
            BinOp(+)
              Int(1)
              Int(2)

    实现方式：
      对每类节点用 isinstance 判断类型，
      然后按照子节点结构递归输出。
      叶子节点（字面量、标识符）直接输出一行不递归。
    """
    prefix = "  " * indent
    if isinstance(node, ProgramNode):
        result = f"{prefix}Program({node.name})\n"
        for imp in node.imports:
            result += dump_ast(imp, indent + 1)
        result += dump_ast(node.block, indent + 1)
        return result
    elif isinstance(node, ImportNode):
        return f"{prefix}Import({node.path})\n"
    elif isinstance(node, BlockNode):
        result = f"{prefix}Block\n"
        for decl in node.var_decls:
            result += dump_ast(decl, indent + 1)
        result += dump_ast(node.body, indent + 1)
        return result
    elif isinstance(node, VarDeclNode):
        vars_str = ", ".join(f"({n}:{t})" for n, t in node.variables)
        return f"{prefix}VarDecl[{vars_str}]\n"
    elif isinstance(node, BeginBlockNode):
        result = f"{prefix}BeginBlock\n"
        for stmt in node.statements:
            result += dump_ast(stmt, indent + 1)
        return result
    elif isinstance(node, AssignNode):
        result = f"{prefix}Assign({node.target})\n"
        result += dump_ast(node.value, indent + 1)
        return result
    elif isinstance(node, IfNode):
        result = f"{prefix}If\n"
        result += f"{prefix}  Condition:\n"
        result += dump_ast(node.condition, indent + 2)
        result += f"{prefix}  Then:\n"
        result += dump_ast(node.then_branch, indent + 2)
        result += f"{prefix}  Else:\n"
        result += dump_ast(node.else_branch, indent + 2)
        return result
    elif isinstance(node, WhileNode):
        result = f"{prefix}While\n"
        result += f"{prefix}  Condition:\n"
        result += dump_ast(node.condition, indent + 2)
        result += f"{prefix}  Body:\n"
        result += dump_ast(node.body, indent + 2)
        return result
    elif isinstance(node, PrintNode):
        result = f"{prefix}Print\n"
        result += dump_ast(node.value, indent + 1)
        return result
    elif isinstance(node, BinOpNode):
        result = f"{prefix}BinOp({node.op})\n"
        result += dump_ast(node.left, indent + 1)
        result += dump_ast(node.right, indent + 1)
        return result
    elif isinstance(node, IdentifierNode):
        return f"{prefix}Ident({node.name})\n"
    elif isinstance(node, IntLiteralNode):
        return f"{prefix}Int({node.value})\n"
    elif isinstance(node, FloatLiteralNode):
        return f"{prefix}Float({node.value})\n"
    elif isinstance(node, BoolLiteralNode):
        return f"{prefix}Bool({node.value})\n"
    elif isinstance(node, StringLiteralNode):
        return f'{prefix}String("{node.value}")\n'
    elif isinstance(node, CharLiteralNode):
        return f"{prefix}Char('{node.value}')\n"
    elif isinstance(node, FuncDefNode):
        params_str = ", ".join(f"({n}:{t})" for n, t in node.params)
        result = f"{prefix}FuncDef({node.name}, [{params_str}], {node.return_type})\n"
        result += dump_ast(node.body, indent + 1)
        return result
    elif isinstance(node, ExternDeclNode):
        params_str = ", ".join(node.param_types)
        return f"{prefix}ExternDecl({node.name}, [{params_str}], {node.return_type})\n"
    elif isinstance(node, LambdaDefNode):
        params_str = ", ".join(f"({n}:{t})" for n, t in node.params)
        result = f"{prefix}Lambda({node.name}, [{params_str}], {node.return_type})\n"
        result += dump_ast(node.body, indent + 1)
        return result
    elif isinstance(node, FuncCallNode):
        result = f"{prefix}FuncCall({node.name})\n"
        for arg in node.args:
            result += dump_ast(arg, indent + 1)
        return result
    elif isinstance(node, ReturnNode):
        result = f"{prefix}Return\n"
        result += dump_ast(node.value, indent + 1)
        return result
    elif isinstance(node, ArrayAccessNode):
        result = f"{prefix}ArrayAccess({node.name})\n"
        result += dump_ast(node.index, indent + 1)
        return result
    elif isinstance(node, ArrayAssignNode):
        result = f"{prefix}ArrayAssign({node.name})\n"
        result += dump_ast(node.index, indent + 1)
        result += dump_ast(node.value, indent + 1)
        return result
    elif isinstance(node, ArrayPrintNode):
        result = f"{prefix}ArrayPrint({node.name})\n"
        result += dump_ast(node.index, indent + 1)
        return result
    elif isinstance(node, ArgcNode):
        return f"{prefix}Argc\n"
    elif isinstance(node, ArgvNode):
        result = f"{prefix}Argv({node.value_type})\n"
        result += dump_ast(node.index, indent + 1)
        return result
    elif isinstance(node, InputNode):
        return f"{prefix}Input({node.value_type})\n"
    elif isinstance(node, RandomSeedNode):
        result = f"{prefix}RandomSeed\n"
        result += dump_ast(node.seed, indent + 1)
        return result
    elif isinstance(node, RandomRangeNode):
        result = f"{prefix}RandomRange\n"
        result += dump_ast(node.low, indent + 1)
        result += dump_ast(node.high, indent + 1)
        return result
    elif isinstance(node, FileReadNode):
        result = f"{prefix}FileRead({node.value_type})\n"
        result += dump_ast(node.path, indent + 1)
        return result
    elif isinstance(node, FileWriteNode):
        result = f"{prefix}FileWrite({node.value_type})\n"
        result += dump_ast(node.path, indent + 1)
        result += dump_ast(node.value, indent + 1)
        return result
    elif isinstance(node, StringLengthNode):
        result = f"{prefix}StringLength\n"
        result += dump_ast(node.string_expr, indent + 1)
        return result
    elif isinstance(node, StringAtNode):
        result = f"{prefix}StringAt\n"
        result += dump_ast(node.string_expr, indent + 1)
        result += dump_ast(node.index, indent + 1)
        return result
    elif isinstance(node, StringSubNode):
        result = f"{prefix}StringSub\n"
        result += dump_ast(node.string_expr, indent + 1)
        result += dump_ast(node.start, indent + 1)
        result += dump_ast(node.length, indent + 1)
        return result
    elif isinstance(node, StringCmpNode):
        result = f"{prefix}StringCmp\n"
        result += dump_ast(node.left, indent + 1)
        result += dump_ast(node.right, indent + 1)
        return result
    elif isinstance(node, StringContainsNode):
        result = f"{prefix}StringContains\n"
        result += dump_ast(node.haystack, indent + 1)
        result += dump_ast(node.needle, indent + 1)
        return result
    elif isinstance(node, IntToStringNode):
        result = f"{prefix}IntToString\n"
        result += dump_ast(node.int_expr, indent + 1)
        return result
    elif isinstance(node, StringToIntNode):
        result = f"{prefix}StringToInt\n"
        result += dump_ast(node.string_expr, indent + 1)
        return result
    elif isinstance(node, ArgvStringNode):
        result = f"{prefix}ArgvString\n"
        result += dump_ast(node.index, indent + 1)
        return result
    elif isinstance(node, CharToIntNode):
        result = f"{prefix}CharToInt\n"
        result += dump_ast(node.char_expr, indent + 1)
        return result
    elif isinstance(node, IntToCharNode):
        result = f"{prefix}IntToChar\n"
        result += dump_ast(node.int_expr, indent + 1)
        return result
    elif isinstance(node, CharToStringNode):
        result = f"{prefix}CharToString\n"
        result += dump_ast(node.char_expr, indent + 1)
        return result
    elif isinstance(node, IsLetterNode):
        result = f"{prefix}IsLetter\n"
        result += dump_ast(node.char_expr, indent + 1)
        return result
    elif isinstance(node, IsDigitNode):
        result = f"{prefix}IsDigit\n"
        result += dump_ast(node.char_expr, indent + 1)
        return result
    elif isinstance(node, CharUpcaseNode):
        result = f"{prefix}CharUpcase\n"
        result += dump_ast(node.char_expr, indent + 1)
        return result
    elif isinstance(node, CharDowncaseNode):
        result = f"{prefix}CharDowncase\n"
        result += dump_ast(node.char_expr, indent + 1)
        return result
    else:
        return f"{prefix}Unknown({type(node).__name__})\n"
