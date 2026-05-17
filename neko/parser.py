"""
语法分析器（Parser / 解析器）

编译原理角色：
  语法分析是编译器的第二阶段。它接收词法分析器产出的 Token 序列，
  按照语言的语法规则（上下文无关文法）将其组织成抽象语法树（AST）。

  NekoLang 使用 S-表达式语法（类似 Lisp/Scheme 家族）：
    - 每条语句/表达式都被括号包裹
    - 括号内的第一个元素决定结构类型
    - 例如：(program main ...) 表示程序入口
           (if cond then else)    表示条件分支
           (+ a b)                表示加法运算
           (func-name arg1 arg2)  表示函数调用

实现方式：递归下降解析（Recursive Descent Parsing）
  每个语法结构对应一个独立的解析方法（_parse_xxx），
  方法之间通过相互调用来处理嵌套结构。
  这种实现方式直接、清晰，与文法规则一一对应。
"""

import sys

from .tokens import Token, TokenType
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
    ImportNode,
)
from .errors import ParseError


class Parser:
    """
    递归下降语法分析器主类。

    核心思路：
      在 Token 列表上维护位置指针 self.pos。
      每次调用 _parse_xxx 方法，从当前位置开始，
      按照对应的语法规则消费 Token，构建出一个 AST 节点，
      然后返回该节点，指针停留在已消费 Token 的下一个位置。

    三个底层操作（与 lexer.py 类似但作用在 Token 上而非字符上）：
      _current() —— 返回当前位置的 Token，不消费
      _advance() —— 消费当前位置的 Token，指针前移
      _expect()  —— 检查当前 Token 类型是否符合预期，
                    如果符合则消费（= _advance），否则报错
      _match()   —— 尝试匹配，符合则消费并返回 True，不符合不消费返回 False

    NekoLang 的 S-表达式语法让解析变得很自然：
      (keyword ...) 中的 keyword 决定了这个结构是什么。
      解析器每次遇到 '(' 就看后面的关键字，然后进入对应的 _parse_xxx。
    """

    def __init__(self, tokens: list[Token]):
        """
        初始化语法分析器。

        参数:
          tokens — 词法分析器产出的完整 Token 列表

        维护的状态：
          pos          当前读取位置，tokens 列表的索引
          source_lines 源码的行列表，用于在报错时显示源码上下文
        """
        self.tokens = tokens
        self.pos = 0
        self.source_lines: list[str] = []

    def set_source(self, source: str):
        """
        设置源码文本（用于错误信息中的行显示）。
        解析器本身不需要源码内容（已经通过 tokens 携带了行号列号），
        但有了源码可以在报错时显示具体的代码行和 ^ 标记，方便定位。
        """
        self.source_lines = source.splitlines()

    def _current(self) -> Token:
        """
        返回当前位置的 Token，但不消费它。
        如果所有 Token 都已消费完，返回一个 EOF 假 Token。
        """
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token(TokenType.EOF, "", 0, 0)

    def _advance(self) -> Token:
        """
        消费当前 Token（取回它并把指针移到下一个）。
        这是"读入"操作，每次调用就从 Token 流里拿掉一个。
        """
        tok = self._current()
        self.pos += 1
        return tok

    def _expect(self, tok_type: TokenType) -> Token:
        """
        断言当前 Token 的类型是预期的类型。
          是 → 消费它并返回
          否 → 抛出 ParseError

        这是递归下降解析中最常用的检查模式。
        例如解析 (program name ...) 时，读完 '(' 后，
        下一个必须是 PROGRAM 关键字，用 _expect 确认。
        如果不是，说明程序语法有错误。

        对比 _match：
          _expect —— 不匹配就报错（硬性要求）
          _match  —— 不匹配就算了，不报错（可选结构）
        """
        tok = self._current()
        if tok.type != tok_type:
            src = self.source_lines[tok.line - 1] if 0 < tok.line <= len(self.source_lines) else ""
            raise ParseError(
                f"期望 {tok_type.value}，但得到 {tok.value!r} ({tok.type.value})",
                line=tok.line, column=tok.column,
                source_line=src
            )
        return self._advance()

    def _match(self, tok_type: TokenType) -> bool:
        """
        尝试匹配当前 Token 的类型。
          匹配 → 消费它，返回 True
          不匹配 → 不消费，返回 False

        用于可选结构。例如某个语句可能是赋值也可能不是，
        先 _match(TokenType.ASSIGN) 看看，匹配了就走赋值分支。
        """
        if self._current().type == tok_type:
            self._advance()
            return True
        return False

    # ── 顶层解析 ──────────────────────────────────────────────

    def parse(self) -> ProgramNode:
        """
        解析一个完整的 NekoLang 程序。

        顶层文法：
          program ::= imports? '(' 'program' IDENTIFIER block ')'

        解析顺序：
          1. 先解析可能存在的 import 语句（_parse_imports）
          2. 然后匹配 (program <name> ...) 结构
          3. 解析中间的变量声明和 begin 块
          4. 检查根括号已关闭以及 EOF

        对应的 NekoLang 源码示例：
          (import math-utils)
          (program hello
            (var (x int) (y float))
            (begin
              (:= x 10)
              (print x)
            )
          )
        """
        imports = self._parse_imports()
        self._expect(TokenType.LPAREN)       # 程序开头的 (
        self._expect(TokenType.PROGRAM)      # program 关键字
        name_tok = self._expect(TokenType.IDENTIFIER)  # 程序名
        block = self._parse_block()          # 变量声明 + begin 块
        self._expect(TokenType.RPAREN)       # 关闭 program 的 )
        self._expect(TokenType.EOF)          # 确保没有多余内容
        return ProgramNode(name=name_tok.value, block=block, imports=imports,
                           line=name_tok.line, column=name_tok.column)

    # ── 导入解析 ──────────────────────────────────────────────

    def _parse_imports(self) -> list[ImportNode]:
        """
        解析开头的所有 import 语句。

        NekoLang 中 import 必须在程序最前面：
          (import module-name)
          (import ./relative-path)

        这里使用"尝试-回退"方法：
          先假设遇到的是 import，前进看看；
          如果不是 import，把位置退回去，结束导入解析。
        这种模式在递归下降中很常见，用于需要前看多个 Token 的场景。
        """
        imports = []
        while self._current().type == TokenType.LPAREN:
            saved = self.pos            # 保存当前位置
            self._advance()              # 吃掉 (
            if self._current().type == TokenType.IMPORT:
                imports.append(self._parse_import())
            else:
                self.pos = saved        # 不是 import，退回
                break
        return imports

    def _parse_import(self) -> ImportNode:
        """
        解析单条 import 语句。

        文法：(import 模块名)
        示例：(import math-utils)
        """
        tok = self._advance()  # 吃掉 'import' 关键字
        path_tok = self._expect(TokenType.IDENTIFIER)  # 模块路径
        self._expect(TokenType.RPAREN)   # 关闭括号
        return ImportNode(path=path_tok.value, line=tok.line, column=tok.column)

    # ── 定义文件解析（用于导入系统） ──────────────────────────

    def parse_definition_file(self) -> tuple[list[ImportNode], list[ASTNode]]:
        """
        解析一个被导入的定义文件。

        和 parse() 不同：不要求有 (program ...)，
        只从文件中提取顶层 function/extern 定义和 import。
        这样导入文件可以是一个纯定义集合（类似 C 的头文件概念）。

        在这个模式下，文件顶层只能出现：
          - (import ...)   → 导入其他模块
          - (function ...) → 函数定义，收集到 definitions 列表
          - (extern ...)   → 外部函数声明，收集到 definitions 列表
          - (program ...)  → 跳过并警告（不应该出现在导入文件中）

        返回值：(imports, definitions)
          imports      — 这个文件自身的 import 依赖
          definitions  — 这个文件中定义的所有函数和 extern 声明
        """
        imports: list[ImportNode] = []
        definitions: list[ASTNode] = []
        while self._current().type != TokenType.EOF:
            self._expect(TokenType.LPAREN)   # 每个顶层定义以 ( 开头
            tok = self._current()
            if tok.type == TokenType.FUNCTION:
                definitions.append(self._parse_func_def())
            elif tok.type == TokenType.EXTERN:
                definitions.append(self._parse_extern_decl())
            elif tok.type == TokenType.IMPORT:
                imports.append(self._parse_import())
            elif tok.type == TokenType.PROGRAM:
                print(f"警告: 导入文件中的 (program ...) 块被跳过 (行 {tok.line})", file=sys.stderr)
                self._advance()
                self._expect(TokenType.IDENTIFIER)
                self._parse_block()
                self._expect(TokenType.RPAREN)
            else:
                src = self.source_lines[tok.line - 1] if 0 < tok.line <= len(self.source_lines) else ""
                raise ParseError(
                    f"顶层只允许 import、function、extern 或 program，但得到 {tok.value!r}",
                    line=tok.line, column=tok.column,
                    source_line=src,
                )
        return imports, definitions

    # ── 块解析（变量声明 + begin 块） ─────────────────────────

    def _parse_block(self) -> BlockNode:
        """
        解析一个块：可选的变量声明 + 一个 begin 块。

        文法：
          block ::= (var ...)* begin-block

        变量声明必须先于 begin。但 (var ...) 是可选的，
        所以需要先"试探"一下是不是 var 声明。

        为了不向前看太多 Token，采用"先试探再退回"策略：
          1. 看到 ( 先前进
          2. 如果里面是 var → 退回，走 _parse_var_decl
          3. 否则退回，结束变量声明，进入 begin 块
        """
        var_decls = []
        while self._current().type == TokenType.LPAREN:
            # 先吃掉 '('，看一眼是不是 var
            saved = self.pos
            self._advance()  # 吃掉 (
            if self._current().type == TokenType.VAR:
                self.pos = saved  # 退回去，让 _parse_var_decl 重新处理
                var_decls.append(self._parse_var_decl())
            else:
                self.pos = saved  # 退回去，结束变量声明处理
                break
        body = self._parse_begin_block()
        return BlockNode(var_decls=var_decls, body=body)

    # ── 类型解析 ──────────────────────────────────────────────

    def _parse_type(self) -> str:
        """
        解析一个类型声明。

        NekoLang 的类型可以是：
          基本类型：int, float, char, bool, string, pointer
          数组类型：(array 元素类型 长度)  如 (array int 10)
          函数指针类型：(func (参数类型...) 返回类型)  如 (func (int int) int)

        基本类型直接返回类型名字符串（如 "int"）。
        复合类型（数组、函数指针）用括号包裹，递归解析内部。
        """
        tok = self._current()
        if tok.type == TokenType.LPAREN:
            # 复合类型：以 ( 开头
            self._advance()  # 吃掉 (
            kw = self._current()
            if kw.type == TokenType.ARRAY:
                # 数组类型：(array 元素类型 长度)
                # 例如：(array int 10) 表示长度为 10 的整型数组
                self._advance()
                elem_type = self._advance().value
                size_tok = self._expect(TokenType.INTEGER)
                self._expect(TokenType.RPAREN)
                return f"(array {elem_type} {size_tok.value})"
            elif kw.type == TokenType.LAMBDA or kw.value == "func":
                # 函数指针类型：(func (参数类型...) 返回类型)
                # 例如：(func (int int) int) 表示"两个 int 参数返回 int 的函数"
                self._advance()
                self._expect(TokenType.LPAREN)  # 参数列表的 (
                param_types = []
                while self._current().type != TokenType.RPAREN:
                    param_types.append(self._parse_type())  # 递归解析每个参数类型
                self._expect(TokenType.RPAREN)  # 关闭参数列表
                ret_type = self._parse_type()
                self._expect(TokenType.RPAREN)  # 关闭 (func ...)
                params_str = " ".join(param_types)
                return f"(func ({params_str}) {ret_type})"
            else:
                src = self.source_lines[tok.line - 1] if 0 < tok.line <= len(self.source_lines) else ""
                raise ParseError(
                    f"未知的类型括号: {kw.value!r}",
                    line=kw.line, column=kw.column,
                    source_line=src
                )
        else:
            # 基本类型：直接返回 Token 的值
            return self._advance().value

    # ── 变量声明解析 ──────────────────────────────────────────

    def _parse_var_decl(self) -> VarDeclNode:
        """
        解析变量声明。

        文法：(var (变量名 类型) (变量名 类型) ...)
        示例：(var (x int) (y float) (name string))

        可以在一个 var 中声明多个变量：
          (var
            (x int)
            (y float)
            (flag bool)
          )
        """
        tok = self._current()
        self._expect(TokenType.LPAREN)       # var 的 (
        self._expect(TokenType.VAR)          # var 关键字
        self._expect(TokenType.LPAREN)       # 外层列表 ( 开始

        variables = []
        while self._current().type == TokenType.LPAREN:
            # 每个变量由 (名称 类型) 组成
            self._advance()  # 吃掉内层 (
            name_tok = self._expect(TokenType.IDENTIFIER)
            type_name = self._parse_type()
            self._expect(TokenType.RPAREN)   # 关闭内层 )
            variables.append((name_tok.value, type_name))

        self._expect(TokenType.RPAREN)       # 关闭外层列表 )
        self._expect(TokenType.RPAREN)       # 关闭 var )
        return VarDeclNode(variables=variables, line=tok.line, column=tok.column)

    # ── begin 块解析 ──────────────────────────────────────────

    def _parse_begin_block(self, paren_consumed: bool = False) -> BeginBlockNode:
        """
        解析 begin...end 复合语句块。

        文法：(begin 语句1 语句2 ...)
        示例：(begin (print 1) (print 2) (:= x 10))

        参数 paren_consumed:
          通常调用时还没有吃掉 '(', 方法自己吃。
          但 _parse_statement 中已经为所有语句统一吃过 '(' 了，
          遇到 begin 时传入 paren_consumed=True 避免重复。
        """
        tok = self._current()
        if not paren_consumed:
            self._expect(TokenType.LPAREN)   # begin 的 (
        self._expect(TokenType.BEGIN)        # begin 关键字
        statements = []
        while self._current().type != TokenType.RPAREN:
            # 在遇到 ) 之前，反复解析语句
            statements.append(self._parse_statement())
        self._expect(TokenType.RPAREN)       # 关闭 begin 的 )
        return BeginBlockNode(statements=statements, line=tok.line, column=tok.column)

    # ── 语句分发 ──────────────────────────────────────────────

    def _parse_statement(self) -> ASTNode:
        """
        解析一条语句。

        所有 NekoLang 的语句都以 (关键字 ...) 的形式出现。
        先吃掉 '('，然后看后面的关键字来决定分支。

        语句类型：
          (:= 变量 表达式)          → 赋值
          (if 条件 then else)       → 条件分支
          (while 条件 体)           → 循环
          (print 表达式)            → 打印
          (return 表达式)           → 函数返回
          (begin 语句...)           → 复合语句块
          (function ...)            → 函数定义
          (extern ...)              → 外部函数声明
          (array-set 数组 下标 值)  → 数组元素赋值
          (array-print 数组 下标)   → 打印数组元素
          (write-int/float/... 路径 值) → 文件写入
          (rand-seed 种子)          → 随机数种子
        """
        self._expect(TokenType.LPAREN)       # 所有语句都以 ( 开头
        tok = self._current()

        if tok.type == TokenType.ASSIGN:
            return self._parse_assign()
        elif tok.type == TokenType.IF:
            return self._parse_if()
        elif tok.type == TokenType.WHILE:
            return self._parse_while()
        elif tok.type == TokenType.PRINT:
            return self._parse_print()
        elif tok.type == TokenType.RETURN:
            return self._parse_return()
        elif tok.type == TokenType.BEGIN:
            return self._parse_begin_block(paren_consumed=True)  # ( 已消费
        elif tok.type == TokenType.FUNCTION:
            return self._parse_func_def()
        elif tok.type == TokenType.EXTERN:
            return self._parse_extern_decl()
        elif tok.type == TokenType.ARRAY_SET:
            return self._parse_array_assign()
        elif tok.type == TokenType.ARRAY_PRINT:
            return self._parse_array_print()
        elif tok.type in {
            TokenType.WRITE_INT,
            TokenType.WRITE_FLOAT,
            TokenType.WRITE_CHAR,
            TokenType.WRITE_BOOL,
        }:
            return self._parse_file_write()
        elif tok.type == TokenType.RAND_SEED:
            return self._parse_rand_seed()
        else:
            src = self.source_lines[tok.line - 1] if 0 < tok.line <= len(self.source_lines) else ""
            raise ParseError(
                f"未知的语句关键字: {tok.value!r}",
                line=tok.line, column=tok.column,
                source_line=src
            )

    # ── 各类语句的解析方法 ────────────────────────────────────

    def _parse_assign(self) -> AssignNode:
        """
        解析赋值语句。

        文法：(:= 变量名 表达式)
        示例：(:= x 10), (:= y (+ x 1))

        注意 NekoLang 中 := 是统一的操作符，
        不是像 C 语言那样 = 出现在表达式里。
        """
        tok = self._advance()  # 吃掉 :=
        target_tok = self._expect(TokenType.IDENTIFIER)  # 变量名
        value = self._parse_expression()  # 右侧表达式的值
        self._expect(TokenType.RPAREN)    # 关闭 )
        return AssignNode(target=target_tok.value, value=value,
                          line=tok.line, column=tok.column)

    def _parse_if(self) -> IfNode:
        """
        解析 if 条件分支语句。

        文法：(if 条件 真分支 假分支)
        示例：(if (> x 0) (print "正数") (print "非正数"))

        if 必须有 then 和 else 两个分支，没有"else if"语法。
        但 else 分支本身可以是另一个 if 语句来实现嵌套：
          (if (> x 0)
            (print "正数")
            (if (< x 0)
              (print "负数")
              (print "零")
            )
          )
        """
        tok = self._advance()  # 吃掉 if
        condition = self._parse_expression()  # 条件表达式
        then_branch = self._parse_statement()  # 条件为真时执行
        else_branch = self._parse_statement()  # 条件为假时执行
        self._expect(TokenType.RPAREN)
        return IfNode(condition=condition, then_branch=then_branch,
                      else_branch=else_branch, line=tok.line, column=tok.column)

    def _parse_while(self) -> WhileNode:
        """
        解析 while 循环语句。

        文法：(while 条件 循环体)
        示例：(while (< i 10) (begin (print i) (:= i (+ i 1))))

        每次迭代前先检查条件，条件为真才执行循环体。
        """
        tok = self._advance()  # 吃掉 while
        condition = self._parse_expression()  # 循环条件
        body = self._parse_statement()        # 循环体
        self._expect(TokenType.RPAREN)
        return WhileNode(condition=condition, body=body,
                         line=tok.line, column=tok.column)

    def _parse_print(self) -> PrintNode:
        """
        解析打印语句。

        文法：(print 表达式)
        示例：(print "hello"), (print (+ 1 2))
        """
        tok = self._advance()  # 吃掉 print
        value = self._parse_expression()
        self._expect(TokenType.RPAREN)
        return PrintNode(value=value, line=tok.line, column=tok.column)

    def _parse_func_def(self) -> FuncDefNode:
        """
        解析函数定义。

        文法：(function 函数名 (参数列表) 返回类型 函数体)
        示例：(function factorial ((n int)) int
               (if (= n 1) 1 (* n (factorial (- n 1)))))

        参数列表是可嵌套的，每个参数是 (参数名 类型) 对。
        """
        tok = self._advance()  # 吃掉 function
        name_tok = self._expect(TokenType.IDENTIFIER)  # 函数名
        self._expect(TokenType.LPAREN)  # 参数列表的 (
        params = []
        while self._current().type == TokenType.LPAREN:
            self._advance()
            p_name = self._expect(TokenType.IDENTIFIER).value
            p_type = self._parse_type()
            self._expect(TokenType.RPAREN)
            params.append((p_name, p_type))
        self._expect(TokenType.RPAREN)  # 关闭参数列表
        return_type = self._parse_type() # 返回类型
        body = self._parse_statement() # 函数体
        self._expect(TokenType.RPAREN)  # 关闭 function 的 )
        return FuncDefNode(name=name_tok.value, params=params,
                           return_type=return_type, body=body,
                           line=tok.line, column=tok.column)

    def _parse_extern_decl(self) -> ExternDeclNode:
        """
        解析外部函数声明。

        文法：(extern 函数名 (参数类型...) 返回类型)
        示例：(extern printf (string) int)

        extern 告诉编译器这个函数在 C 运行时中已经存在，
        不需要生成函数体，只需要声明它的签名供类型检查和代码生成。
        """
        tok = self._advance()  # 吃掉 extern
        name_tok = self._expect(TokenType.IDENTIFIER)  # 函数名（对应 C 函数名）
        self._expect(TokenType.LPAREN)
        param_types = []
        while self._current().type != TokenType.RPAREN:
            param_types.append(self._parse_type())
        self._expect(TokenType.RPAREN)  # 关闭参数类型列表
        return_type = self._parse_type()
        self._expect(TokenType.RPAREN)  # 关闭 extern 的 )
        return ExternDeclNode(
            name=name_tok.value,
            param_types=param_types,
            return_type=return_type,
            line=tok.line,
            column=tok.column,
        )

    def _parse_return(self) -> ReturnNode:
        """
        解析 return 语句。

        文法：(return 表达式)
        示例：(return 42), (return (+ x y))
        """
        tok = self._advance()  # 吃掉 return
        value = self._parse_expression()
        self._expect(TokenType.RPAREN)
        return ReturnNode(value=value, line=tok.line, column=tok.column)

    def _parse_array_assign(self) -> ArrayAssignNode:
        """
        解析数组元素赋值。

        文法：(array-set 数组名 下标 值)
        示例：(array-set arr 3 42)  将 arr[3] 设为 42
        """
        tok = self._advance()  # 吃掉 array-set
        name_tok = self._expect(TokenType.IDENTIFIER)
        index = self._parse_expression()
        value = self._parse_expression()
        self._expect(TokenType.RPAREN)
        return ArrayAssignNode(name=name_tok.value, index=index, value=value,
                               line=tok.line, column=tok.column)

    def _parse_array_print(self) -> ArrayPrintNode:
        """
        解析数组元素打印。

        文法：(array-print 数组名 下标)
        示例：(array-print arr 3)  打印 arr[3]
        """
        tok = self._advance()  # 吃掉 array-print
        name_tok = self._expect(TokenType.IDENTIFIER)
        index = self._parse_expression()
        self._expect(TokenType.RPAREN)
        return ArrayPrintNode(name=name_tok.value, index=index,
                              line=tok.line, column=tok.column)

    def _parse_file_write(self) -> FileWriteNode:
        """
        解析文件写入语句。

        文法：(write-类型 文件路径 值)
        示例：(write-int "data.txt" 42)

        具体的关键字决定写入值的类型（int/float/char/bool）。
        路径和值都是表达式，运行时计算。
        """
        tok = self._advance()  # 吃掉 write-int/float/char/bool
        path = self._parse_expression()   # 文件路径表达式
        value = self._parse_expression()  # 要写入的值
        self._expect(TokenType.RPAREN)
        return FileWriteNode(
            value_type=self._builtin_value_type(tok.type),
            path=path,
            value=value,
            line=tok.line,
            column=tok.column,
        )

    def _parse_rand_seed(self) -> RandomSeedNode:
        """
        解析随机数种子设置。

        文法：(rand-seed 种子值)
        示例：(rand-seed 42)
        """
        tok = self._advance()
        seed = self._parse_expression()
        self._expect(TokenType.RPAREN)
        return RandomSeedNode(seed=seed, line=tok.line, column=tok.column)

    def _parse_lambda(self) -> LambdaDefNode:
        """
        解析 lambda 表达式（匿名函数）。

        文法：(lambda (参数列表) 返回类型 函数体)
        示例：(lambda ((x int) (y int)) int (+ x y))

        lambda 和 function 的区别：
          - function 有名字，是顶层定义
          - lambda 没有名字（或自动生成名字），可作为表达式值传递
        """
        tok = self._advance()  # 吃掉 lambda
        self._expect(TokenType.LPAREN)  # 参数列表的 (
        params = []
        while self._current().type == TokenType.LPAREN:
            self._advance()
            p_name = self._expect(TokenType.IDENTIFIER).value
            p_type = self._parse_type()
            self._expect(TokenType.RPAREN)
            params.append((p_name, p_type))
        self._expect(TokenType.RPAREN)  # 关闭参数列表
        return_type = self._parse_type()
        body = self._parse_statement()
        self._expect(TokenType.RPAREN)  # 关闭 lambda 的 )
        return LambdaDefNode(params=params, return_type=return_type, body=body,
                             line=tok.line, column=tok.column)

    # ── 表达式解析 ────────────────────────────────────────────

    def _parse_expression(self) -> ASTNode:
        """
        解析一个表达式。

        这是语法分析中最复杂的部分。NekoLang 中表达式可以是：

        1. ( ... ) 形式——括号表达式：
           a. (lambda ...)                         — lambda 匿名函数
           b. (argc)                               — 命令行参数个数
           c. (argv-int/float/char/bool 下标)       — 命令行参数值
           d. (input-int/float/char/bool)           — 用户输入
           e. (rand-range 下界 上界)               — 随机数
           f. (read-int/float/char/bool 路径)       — 文件读取
           g. (string-length/string-at/...)         — 字符串操作
           h. (char-to-int/int-to-char/...)         — 字符操作
           i. (函数名 参数...)                       — 函数调用
           j. (操作符 左操作数 右操作数)            — 二元运算

        2. 原子表达式（无括号）：
           a. IDENTIFIER — 变量名/函数名引用
           b. INTEGER    — 整数字面量（42）
           c. FLOAT      — 浮点数字面量（3.14）
           d. BOOLEAN    — 布尔字面量（true/false）
           e. CHAR       — 字符字面量（'a'）
           f. STRING     — 字符串字面量（"hello"）

        核心判断逻辑：
          遇到 '(' 就先吃进去，看后面的第一个 Token 是什么：
            - lambda → lambda 表达式
            - 内建操作（argc/argv/input/rand/read/字符串/字符）→ 各自对应的节点
            - IDENTIFIER → 函数调用
            - 其他（+ - * / < > = 等）→ 二元运算符表达式
          没遇到 '(' 就按字面量或标识符处理。
        """
        tok = self._current()
        if tok.type == TokenType.LPAREN:
            # ── 括号表达式 ──
            self._advance()  # 吃掉 (
            op_tok = self._current()

            # lambda 表达式
            if op_tok.type == TokenType.LAMBDA:
                return self._parse_lambda()

            # 命令行参数个数：(argc)
            if op_tok.type == TokenType.ARGC:
                self._advance()
                self._expect(TokenType.RPAREN)
                return ArgcNode(line=op_tok.line, column=op_tok.column)

            # 命令行参数值（按类型）：(argv-int 3), (argv-float 0)
            if op_tok.type in {
                TokenType.ARGV_INT,
                TokenType.ARGV_FLOAT,
                TokenType.ARGV_CHAR,
                TokenType.ARGV_BOOL,
            }:
                self._advance()
                index = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return ArgvNode(
                    value_type=self._builtin_value_type(op_tok.type),
                    index=index,
                    line=op_tok.line,
                    column=op_tok.column,
                )

            # 用户输入（按类型）：(input-int), (input-float)
            if op_tok.type in {
                TokenType.INPUT_INT,
                TokenType.INPUT_FLOAT,
                TokenType.INPUT_CHAR,
                TokenType.INPUT_BOOL,
            }:
                self._advance()
                self._expect(TokenType.RPAREN)
                return InputNode(
                    value_type=self._builtin_value_type(op_tok.type),
                    line=op_tok.line,
                    column=op_tok.column,
                )

            # 随机数范围：(rand-range 1 100)
            if op_tok.type == TokenType.RAND_RANGE:
                self._advance()
                low = self._parse_expression()
                high = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return RandomRangeNode(
                    low=low,
                    high=high,
                    line=op_tok.line,
                    column=op_tok.column,
                )

            # 文件读取（按类型）：(read-int "file.txt")
            if op_tok.type in {
                TokenType.READ_INT,
                TokenType.READ_FLOAT,
                TokenType.READ_CHAR,
                TokenType.READ_BOOL,
            }:
                self._advance()
                path = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return FileReadNode(
                    value_type=self._builtin_value_type(op_tok.type),
                    path=path,
                    line=op_tok.line,
                    column=op_tok.column,
                )

            # ── 字符串内建操作 ──
            if op_tok.type == TokenType.STRING_LENGTH:
                self._advance()
                string_expr = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return StringLengthNode(string_expr=string_expr, line=op_tok.line, column=op_tok.column)
            if op_tok.type == TokenType.STRING_AT:
                self._advance()
                string_expr = self._parse_expression()
                index = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return StringAtNode(string_expr=string_expr, index=index, line=op_tok.line, column=op_tok.column)
            if op_tok.type == TokenType.STRING_SUB:
                self._advance()
                string_expr = self._parse_expression()
                start = self._parse_expression()
                length = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return StringSubNode(string_expr=string_expr, start=start, length=length, line=op_tok.line, column=op_tok.column)
            if op_tok.type == TokenType.STRING_CMP:
                self._advance()
                left = self._parse_expression()
                right = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return StringCmpNode(left=left, right=right, line=op_tok.line, column=op_tok.column)
            if op_tok.type == TokenType.STRING_CONTAINS:
                self._advance()
                haystack = self._parse_expression()
                needle = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return StringContainsNode(haystack=haystack, needle=needle, line=op_tok.line, column=op_tok.column)
            if op_tok.type == TokenType.INT_TO_STRING:
                self._advance()
                int_expr = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return IntToStringNode(int_expr=int_expr, line=op_tok.line, column=op_tok.column)
            if op_tok.type == TokenType.STRING_TO_INT:
                self._advance()
                string_expr = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return StringToIntNode(string_expr=string_expr, line=op_tok.line, column=op_tok.column)
            if op_tok.type == TokenType.ARGV_STRING:
                self._advance()
                index = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return ArgvStringNode(index=index, line=op_tok.line, column=op_tok.column)

            # ── 字符内建操作 ──
            if op_tok.type == TokenType.CHAR_TO_INT:
                self._advance()
                char_expr = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return CharToIntNode(char_expr=char_expr, line=op_tok.line, column=op_tok.column)
            if op_tok.type == TokenType.INT_TO_CHAR:
                self._advance()
                int_expr = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return IntToCharNode(int_expr=int_expr, line=op_tok.line, column=op_tok.column)
            if op_tok.type == TokenType.CHAR_TO_STRING:
                self._advance()
                char_expr = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return CharToStringNode(char_expr=char_expr, line=op_tok.line, column=op_tok.column)
            if op_tok.type == TokenType.IS_LETTER:
                self._advance()
                char_expr = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return IsLetterNode(char_expr=char_expr, line=op_tok.line, column=op_tok.column)
            if op_tok.type == TokenType.IS_DIGIT:
                self._advance()
                char_expr = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return IsDigitNode(char_expr=char_expr, line=op_tok.line, column=op_tok.column)
            if op_tok.type == TokenType.CHAR_UPCASE:
                self._advance()
                char_expr = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return CharUpcaseNode(char_expr=char_expr, line=op_tok.line, column=op_tok.column)
            if op_tok.type == TokenType.CHAR_DOWNCASE:
                self._advance()
                char_expr = self._parse_expression()
                self._expect(TokenType.RPAREN)
                return CharDowncaseNode(char_expr=char_expr, line=op_tok.line, column=op_tok.column)

            # ── 函数调用 ──
            # 如果在 ( 后面的是一个标识符，
            # 那它就是函数调用：(函数名 参数1 参数2 ...)
            # 例如：(factorial 5), (+ 1 2) ← 这里的 + 也被当作函数调用处理
            if op_tok.type == TokenType.IDENTIFIER:
                self._advance()
                args = []
                while self._current().type != TokenType.RPAREN:
                    args.append(self._parse_expression())
                self._expect(TokenType.RPAREN)
                return FuncCallNode(name=op_tok.value, args=args,
                                    line=op_tok.line, column=op_tok.column)

            # ── 二元运算符表达式 ──
            # 如果不是上述任何一种特殊形式，那它就是二元运算符：
            # (操作符 左操作数 右操作数)
            # 例如：(+ 1 2)  (< x 10)  (= result 42)
            self._advance()  # 吃掉操作符
            left = self._parse_expression()
            right = self._parse_expression()
            self._expect(TokenType.RPAREN)
            return BinOpNode(op=op_tok.value, left=left, right=right,
                             line=op_tok.line, column=op_tok.column)

        # ── 原子表达式（无括号） ──
        elif tok.type == TokenType.IDENTIFIER:
            # 变量引用（可能是变量名、函数名）
            self._advance()
            return IdentifierNode(name=tok.value, line=tok.line, column=tok.column)
        elif tok.type == TokenType.INTEGER:
            # 整数字面量
            self._advance()
            return IntLiteralNode(value=int(tok.value), line=tok.line, column=tok.column)
        elif tok.type == TokenType.FLOAT:
            # 浮点数字面量
            self._advance()
            return FloatLiteralNode(value=float(tok.value), line=tok.line, column=tok.column)
        elif tok.type == TokenType.BOOLEAN:
            # 布尔字面量
            self._advance()
            return BoolLiteralNode(value=(tok.value == "true"), line=tok.line, column=tok.column)
        elif tok.type == TokenType.CHAR:
            # 字符字面量
            self._advance()
            return CharLiteralNode(value=tok.value, line=tok.line, column=tok.column)
        elif tok.type == TokenType.STRING:
            # 字符串字面量
            self._advance()
            return StringLiteralNode(value=tok.value, line=tok.line, column=tok.column)
        else:
            src = self.source_lines[tok.line - 1] if 0 < tok.line <= len(self.source_lines) else ""
            raise ParseError(
                f"表达式中遇到意外的 token: {tok.value!r}",
                line=tok.line, column=tok.column,
                source_line=src
            )

    # ── 辅助工具 ──────────────────────────────────────────────

    def _builtin_value_type(self, token_type: TokenType) -> str:
        """
        根据内建函数的 Token 类型返回对应的 NekoLang 类型名。

        一些内建函数（argv, input, read, write）针对不同基本类型
        有独立的 TokenType（ARGV_INT/ARGV_FLOAT/ARGV_CHAR/ARGV_BOOL），
        这个方法把 TokenType 统一映射为类型字符串，方便后续处理。
        """
        mapping = {
            TokenType.ARGV_INT: "int",
            TokenType.ARGV_FLOAT: "float",
            TokenType.ARGV_CHAR: "char",
            TokenType.ARGV_BOOL: "bool",
            TokenType.INPUT_INT: "int",
            TokenType.INPUT_FLOAT: "float",
            TokenType.INPUT_CHAR: "char",
            TokenType.INPUT_BOOL: "bool",
            TokenType.READ_INT: "int",
            TokenType.READ_FLOAT: "float",
            TokenType.READ_CHAR: "char",
            TokenType.READ_BOOL: "bool",
            TokenType.WRITE_INT: "int",
            TokenType.WRITE_FLOAT: "float",
            TokenType.WRITE_CHAR: "char",
            TokenType.WRITE_BOOL: "bool",
        }
        return mapping[token_type]
