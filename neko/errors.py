"""
错误定义与格式化（Error Handling）

编译原理角色：
  错误处理贯穿编译器的各个阶段。良好的错误信息能帮助程序员快速定位问题。
  本文件定义了 NekoLang 的异常体系，以及标准化的错误信息格式化方法。

设计思路：
  1. 三级异常类：LexError(词法错误) → ParseError(语法错误) → SemanticError(语义错误)
     继承自 NekoError，分别对应编译流水线的三个主要阶段。
  2. 统一的格式化格式：
       [阶段名] Line {行号}, Column {列号}: {错误消息}
         {源码行}
         {^ 标记}
       {提示文字}
  3. 建议系统（SUGGESTIONS 字典）：
     对常见错误提供中文提示，引导用户修正。
     这个系统是可扩展的，通过 suggestion_key 关联。

使用示例（以语法分析为例）：
  parser.py 中：
    raise ParseError(
        "期望 program 关键字，但得到...",
        line=tok.line,
        column=tok.column,
        source_line=src,        # 源码行内容
        suggestion_key="unexpected_token",
    )
  输出格式：
    [Parser] Line 3, Column 2: 期望 program 关键字，但得到...
      (progrm hello ...)
       ^
    提示：这里出现了不符合语法的符号。

注意：
  - LexError 和 ParseError 使用 raise 抛出异常，终止当前阶段
  - SemanticError 在 semantic.py 中通过 _error() 收集到列表，不立即抛出，
    以便在一次运行中发现尽可能多的语义错误
"""


SUGGESTIONS = {
    # 未声明的变量 —— 引导用户先用 var 声明
    "undefined_var": "提示：请先使用 var 声明这个变量。",
    # 意外的 Token —— 语法结构不符合预期
    "unexpected_token": "提示：这里出现了不符合语法的符号。",
    # 括号不匹配 —— S-表达式常见的拼写错误
    "missing_paren": "提示：请检查括号是否匹配。",
    # 类型不匹配 —— 赋值或函数传参时的类型冲突
    "type_mismatch": "提示：请检查表达式和目标变量的类型是否一致。",
    # 无法识别的字符 —— 源码中包含非法字符
    "invalid_char": "提示：源码中包含无法识别的字符。",
    # 重复声明 —— 同名变量在同一作用域声明两次
    "duplicate_var": "提示：这个变量已经声明过了。",
}


class NekoError(Exception):
    """
    编译错误基类。

    所有 NekoLang 编译错误的统一基类，继承自 Python 的 Exception。
    format() 方法生成格式化的错误信息字符串，包含：
      - 错误阶段（Lexer / Parser / Semantic）
      - 错误位置（文件行号、列号）
      - 错误消息
      - 源码行与 ^ 标记（如果有）
      - 中文提示建议（如果有）

    注意 __init__ 最后调用了 super().__init__(self.format())，
    这意味着 str(e) 会自动返回格式化的错误字符串。
    """

    def __init__(self, phase: str, message: str, line: int = 0, column: int = 0,
                 source_line: str = "", suggestion_key: str = ""):
        """
        参数：
          phase           — 编译阶段名，如 "Lexer", "Parser", "Semantic"
          message         — 错误描述文本
          line            — 错误所在行号（从 1 开始，0 表示未知）
          column          — 错误所在列号（从 1 开始，0 表示未知）
          source_line     — 出错的源代码行文本（用于显示具体代码行）
          suggestion_key  — 建议的键名，在 SUGGESTIONS 字典中查找
        """
        self.phase = phase
        self.message = message
        self.line = line
        self.column = column
        self.source_line = source_line
        self.suggestion_key = suggestion_key
        # 将格式化后的字符串作为 Exception 的 message，
        # 这样 print(e) 或 str(e) 直接输出格式化的错误信息
        super().__init__(self.format())

    def format(self) -> str:
        """
        将错误信息格式化为标准化的可读文本。

        输出格式示例：
          [Parser] Line 3, Column 2: 期望 program 关键字，但得到...
            (progrm hello ...)
             ^
          提示：这里出现了不符合语法的符号。

        如果列号 > 0，会在源码行下方用 ^ 标记错误位置。
        如果有 suggestion_key，会在末尾添加对应的中文提示。
        """
        parts = [f"[{self.phase}]"]
        if self.line > 0:
            parts.append(f"Line {self.line}, Column {self.column}:")
        parts.append(self.message)

        result = " ".join(parts)

        # 显示出错的那行源代码
        if self.source_line:
            result += f"\n  {self.source_line}"
            # 在对应列位置画 ^ 标记
            if self.column > 0:
                result += f"\n  {' ' * (self.column - 1)}^"

        # 附加中文提示
        if self.suggestion_key and self.suggestion_key in SUGGESTIONS:
            result += "\n" + SUGGESTIONS[self.suggestion_key]

        return result


class LexError(NekoError):
    """
    词法分析错误。

    在 lexer.py 中抛出，当遇到无法识别的字符或不合法的字面量时。

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

    在 parser.py 中抛出，当 Token 序列不符合语法规则时。

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

    在 semantic.py 中创建，当程序通过语法检查但存在语义错误时
    （如类型不匹配、未声明的变量、函数参数数量错误等）。

    与 LexError/ParseError 的区别：
      - 这些错误不是通过 raise 立即抛出的，而是收集到
        SemanticAnalyzer.errors 列表中（见 semantic.py 的 _error 方法）
      - phase 固定为 "Semantic"
      - 没有默认的 suggestion_key（语义错误的建议由调用方指定）
    """
    def __init__(self, message: str, line: int = 0, column: int = 0,
                 source_line: str = "", suggestion_key: str = ""):
        super().__init__("Semantic", message, line, column, source_line, suggestion_key)
