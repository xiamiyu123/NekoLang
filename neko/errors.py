"""
错误定义与格式化（Error Handling）

编译原理角色：
  错误处理贯穿编译器的各个阶段。良好的错误信息能帮助程序员快速定位问题。
  本文件定义了 NekoLang 的异常体系，以及标准化的错误信息格式化方法。

设计思路：
  1. 三级异常类：LexError(词法错误) → ParseError(语法错误) → SemanticError(语义错误)
     分别对应编译流水线的三个主要阶段，继承自 NekoError。
  2. 统一的格式化格式：
       [阶段名] Line {行号}, Column {列号}: {错误消息}
         {源码行}
         {^ 标记}
       {提示文字}
  3. 建议系统（SUGGESTIONS 字典）：
     对常见错误提供中文提示，引导用户修正。
     通过 suggestion_key 关联，可扩展。

使用示例：
  以语法分析阶段为例，parser.py 中遇到不符合预期的 Token 时：
    raise ParseError(
        "期望 program 关键字，但得到...",
        line=tok.line,
        column=tok.column,
        source_line=src,
        suggestion_key="unexpected_token",
    )
    输出：
      [Parser] Line 3, Column 2: 期望 program 关键字，但得到...
        (progrm hello ...)
         ^
      提示：这里出现了不符合语法的符号。

三种错误类的调用方式差异：
  - LexError / ParseError：使用 raise 抛出异常，立即终止当前阶段
  - SemanticError：在 semantic.py 中通过 _error() 收集到列表，
    不立即抛出，以便在一次运行中发现尽量多的语义错误
"""


SUGGESTIONS = {
    # 未声明的变量 —— 引导用户先用 var 声明
    "undefined_var": "提示：请先使用 var 声明这个变量。",
    # 意外的 Token —— 语法结构不符合预期，通常是拼写错误或漏写了关键字
    "unexpected_token": "提示：这里出现了不符合语法的符号。",
    # 括号不匹配 —— S-表达式常见的拼写错误，漏写或多写了括号
    "missing_paren": "提示：请检查括号是否匹配。",
    # 类型不匹配 —— 赋值或函数传参时源类型和目标类型冲突
    "type_mismatch": "提示：请检查表达式和目标变量的类型是否一致。",
    # 无法识别的字符 —— 源码中包含既不是关键字、操作符也不是字面量的字符
    "invalid_char": "提示：源码中包含无法识别的字符。",
    # 重复声明 —— 同名变量在同一作用域声明了两次
    "duplicate_var": "提示：这个变量已经声明过了。",
}


class NekoError(Exception):
    """
    编译错误基类。

    所有 NekoLang 编译错误的统一基类，继承自 Python 的 Exception。
    __init__ 最后调用了 super().__init__(self.format())，
    这意味着 str(e) 或 print(e) 会直接输出格式化的错误信息。

    format() 方法生成标准化的错误信息字符串，包含以下部分
    （按出现顺序）：
      1. 阶段标识：[Lexer] / [Parser] / [Semantic]
      2. 位置信息：Line {行号}, Column {列号}（如果提供了行号）
      3. 错误描述：程序员可读的错误消息
      4. 源码行：出错的那一行源代码（如果提供了 source_line）
      5. ^ 标记：在源码行下方标注错误的具体列位置（如果提供了列号）
      6. 中文建议：根据 suggestion_key 从 SUGGESTIONS 字典中查找
    """

    def __init__(self, phase: str, message: str, line: int = 0, column: int = 0,
                 source_line: str = "", suggestion_key: str = ""):
        """
        参数：
          phase           — 编译阶段名，如 "Lexer", "Parser", "Semantic"
          message         — 错误描述文本
          line            — 错误所在行号（从 1 开始，0 表示位置未知）
          column          — 错误所在列号（从 1 开始，0 表示位置未知）
          source_line     — 出错的源代码行文本（用于显示代码行）
          suggestion_key  — 建议的键名，在 SUGGESTIONS 字典中查找提示文字
        """
        self.phase = phase
        self.message = message
        self.line = line
        self.column = column
        self.source_line = source_line
        self.suggestion_key = suggestion_key
        # 把格式化后的字符串作为 Exception 的 message，
        # 这样直接 print(e) 就能输出格式化的完整错误信息
        super().__init__(self.format())

    def format(self) -> str:
        """
        将错误信息格式化为标准化的可读文本。

        输出格式示例（完整的四行）：
          [Parser] Line 3, Column 2: 期望 program 关键字，但得到 'progrm'
            (progrm hello ...)
             ^
          提示：这里出现了不符合语法的符号。

        各行的生成条件：
          - 阶段 + 行号 + 消息：始终输出
          - 源码行：仅在 source_line 非空时输出
          - ^ 标记：仅在 column > 0 时输出，在列号位置画 ^
            空格的个数是 column - 1（因为列号从 1 开始）
          - 提示：仅在 suggestion_key 在 SUGGESTIONS 中有对应值时输出
        """
        # 第一部分：阶段 + 位置 + 消息
        # 例如 "[Lexer] Line 1, Column 5: 未识别的字符 '@'"
        parts = [f"[{self.phase}]"]
        if self.line > 0:
            parts.append(f"Line {self.line}, Column {self.column}:")
        parts.append(self.message)

        result = " ".join(parts)

        # 第二部分：出错的那行源代码（如果有）
        if self.source_line:
            result += f"\n  {self.source_line}"
            # 第三部分：在对应列位置画 ^ 标记（如果有列号）
            if self.column > 0:
                result += f"\n  {' ' * (self.column - 1)}^"

        # 第四部分：中文提示建议（如果有关联的建议键）
        if self.suggestion_key and self.suggestion_key in SUGGESTIONS:
            result += "\n" + SUGGESTIONS[self.suggestion_key]

        return result


class LexError(NekoError):
    """
    词法分析错误。

    在 lexer.py 中抛出，当遇到以下情况时：
      - 无法识别的字符（不在任何词法模式中）
      - 不合法的字面量（空字符字面量 ''、未识别的转义序列 \\x 等）
      - 缺少结束引号（字符串或字符字面量没找到结尾的 ' 或 "）

    与基类的区别：
      - phase 固定为 "Lexer"
      - suggestion_key 默认为 "invalid_char"
    """
    def __init__(self, message: str, line: int = 0, column: int = 0,
                 source_line: str = "", suggestion_key: str = "invalid_char"):
        super().__init__("Lexer", message, line, column, source_line, suggestion_key)


class ParseError(NekoError):
    """
    语法分析错误。

    在 parser.py 中抛出，当 Token 序列不符合语法规则时：
      - 期望的 Token 类型与实际不匹配
      - 未知的语句关键字（既不是 if/while/print 也不是赋值等）
      - 表达式中的意外 Token
      - 括号不匹配

    与基类的区别：
      - phase 固定为 "Parser"
      - suggestion_key 默认为 "unexpected_token"
    """
    def __init__(self, message: str, line: int = 0, column: int = 0,
                 source_line: str = "", suggestion_key: str = "unexpected_token"):
        super().__init__("Parser", message, line, column, source_line, suggestion_key)


class SemanticError(NekoError):
    """
    语义分析错误。

    在 semantic.py 中创建，当程序通过词法和语法检查但存在语义问题时：
      - 未声明的变量
      - 类型不匹配（赋值类型不兼容、函数参数类型不匹配等）
      - 函数参数数量不匹配
      - 在函数体外使用 return
      - 函数缺少 return 语句
      - 重复声明

    与 LexError/ParseError 的区别：
      - LexError/ParseError 通过 raise 立即抛出，中断当前阶段
      - SemanticError 通过 SemanticAnalyzer._error() 收集到 errors 列表，
        不立即抛出，以便在一次编译中尽可能发现所有语义错误
      - phase 固定为 "Semantic"
      - 没有默认的 suggestion_key（建议由调用方按具体情况指定）
    """
    def __init__(self, message: str, line: int = 0, column: int = 0,
                 source_line: str = "", suggestion_key: str = ""):
        super().__init__("Semantic", message, line, column, source_line, suggestion_key)
