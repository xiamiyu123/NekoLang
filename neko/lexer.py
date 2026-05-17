"""
词法分析器（Lexer / Scanner）

编译原理角色：
  词法分析是编译器的第一阶段。它读取源代码的原始字符流，
  按照语言的词法规则（正则文法）将其分组为有意义的词素（lexeme），
  并输出为 Token 序列供语法分析器使用。

  NekoLang 的 S-表达式语法使得词法结构相对简单：
  关键字/标识符、数字字面量、字符串/字符字面量、括号、运算符。

实现方式：手工编码的下推自动机（无词法分析器生成器）
  逐字符扫描源代码（从前往后），用前看字符决定下一个 Token 类型。
  这种实现比使用自动生成工具（如 Flex）更灵活，错误信息也更友好，
  同时代码对读者完全透明，便于学习理解。
"""

from .tokens import Token, TokenType, KEYWORDS, DELIMITERS
from .errors import LexError


class Lexer:
    """
    词法分析器主类。

    核心思路：
      在源代码字符串上维护一个位置指针 self.pos。
      三个关键底层操作支撑所有词法功能：
        _current()  —— 返回当前位置的字符，但不消费它
                      （相当于只看一眼输入，读头不动）
        _advance()  —— 消费当前字符并使指针前进
                      （相当于读入一个字符，读头移向下一个）
        _peek()     —— 向前看一（或多）个字符，也不消费
                      （用于区分 = 和 ==、< 和 <= 等双字符操作符）

    每个 _read_xxx 方法负责读取一种特定词法模式：
      _read_identifier → 标识符或关键字（如 program, begin, x, my-var）
      _read_number    → 整数字面量或浮点数字面量（如 42, 3.14）
      _read_char      → 字符字面量（如 'a', '\\n'）
      _read_string    → 字符串字面量（如 "hello world"）
    """

    def __init__(self, source: str):
        """
        初始化词法分析器。

        参数:
          source — 完整的源代码字符串，来自 .neko 文件的内容

        维护的状态：
          pos           当前读取位置，从 0 开始，指向 source 字符串的索引
          line          当前行号（从 1 开始），用于错误信息定位
          column        当前列号（从 1 开始），用于错误信息定位
          source_lines  按换行符拆分后的源码行列表，
                        当抛出错误时用来显示出错的源代码行和 ^ 标记
        """
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.source_lines = source.splitlines()

    # ── 底层字符操作 ──────────────────────────────────────────

    def _current(self) -> str | None:
        """
        看一眼当前位置是什么字符，但**不往前移动**。
        如果已经读完了全部源码，返回 None。

        可以把词法分析器想象成在铁轨上跑的火车，
        _current() 就是望向窗外看当前经过的站牌，
        但火车本身没有动。
        """
        if self.pos < len(self.source):
            return self.source[self.pos]
        return None

    def _peek(self, offset: int = 1) -> str | None:
        """
        提前看后面第 offset 个字符是什么，但**不往前移动**。
        offset=1 表示看下一个字符，offset=2 表示看下下个字符。

        为什么需要这个？
          有些操作符是单个字符（=, <, >），
          有些是两个字符组成的（==, <=, >=, !=, :=）。
          读到一个 '<' 时，必须看下一个字符是不是 '='，
          才能决定是"小于"还是"小于等于"。
          这叫作"一个字符的前看"（LL(1) 中的那个 1）。

        类似于火车司机提前看前方轨道：
          看到'<'时先不决定，再看前方有没有'='。
          有 → 这是一个 <= 操作符；
          没有 → 这是一个单独的 < 操作符。
        """
        pos = self.pos + offset
        if pos < len(self.source):
            return self.source[pos]
        return None

    def _advance(self) -> str:
        """
        消费当前位置的字符，把它吃掉，然后指针前进一步。
        返回被消费的那个字符。

        副作用 — 自动维护行号和列号：
          - 如果吃掉的是换行符 \\n，行号 line 加 1，列号 column 重置为 1
          - 否则列号 column 加 1

        可以把 _advance() 想象成"火车向前开一站，
        同时记录开到了第几行第几列"。
        这个行号列号最终会存在 Token 里，
        当语法报错时告诉用户"第几行第几列出错了"。
        """
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    # ── 辅助跳过 ──────────────────────────────────────────────

    def _skip_whitespace(self):
        """
        跳过空白字符（空格、制表符、换行、回车）。

        空白和换行在代码中有意义（分隔关键字/标识符），
        但词法分析阶段不需要把它们作为 Token 输出。
        遇到空白就跳过（_advance 吃掉它）并继续向前，
        直到遇到有意义的字符为止。
        """
        while self.pos < len(self.source) and self.source[self.pos] in ' \t\n\r':
            self._advance()

    def _skip_comment(self):
        """
        跳过注释。

        NekoLang 使用 ';' 作为注释起始（和 Lisp/Scheme 家族一致）。
        从第一个 ';' 开始到本行末尾，全部忽略。
        注释的作用是给程序员看，编译器不需要处理它。

        实现很简单：只要没到行尾就一直前进。
        注意这里检查的是 \\n 换行符，因为注释只延伸到行尾。
        """
        if self._current() == ';':
            while self.pos < len(self.source) and self.source[self.pos] != '\n':
                self._advance()

    # ── 各词法模式的读取方法 ──────────────────────────────────

    def _read_identifier(self) -> Token:
        """
        读取一个标识符或关键字。

        什么是标识符？
          变量名、函数名等由程序员自己起的名字。
          NekoLang 中标识符可以由以下字符组成：
            - 字母（a-z, A-Z）
            - 数字（0-9，但不能在开头）
            - 下划线 _
            - 短横线 -
          例如：my-var, x, factorial, _temp

        什么是关键字？
          语言预先保留的词，有特殊含义，不能用作变量名。
          例如：program, begin, if, while, return, int, var 等。

        如何区分关键字和普通标识符？
          先按相同的规则读完整串字符（"最长匹配"原则），
          然后去查 KEYWORDS 字典。
            如果在字典里 → 返回对应关键字类型的 Token
            不在字典里   → 返回标识符类型的 Token

        这种"先读完整字符串再查表"的方式叫作"关键字即标识符"：
          把关键字当作标识符读出来，再检查它是不是保留字。
        """
        start_col = self.column
        start_line = self.line
        result = ""
        while self.pos < len(self.source) and (self.source[self.pos].isalnum()
                                                 or self.source[self.pos] in '_-'):
            result += self._advance()
        if result in KEYWORDS:
            return Token(KEYWORDS[result], result, start_line, start_col)
        return Token(TokenType.IDENTIFIER, result, start_line, start_col)

    def _read_number(self) -> Token:
        """
        读取数字字面量。支持整数和浮点数。

        文法规则：
          整数 ::= 一个或多个连续数字
          浮点数 ::= 整数部分 + 小数点 + 小数部分

        识别策略：
          1. 先一口气吃掉所有连续的数字字符
          2. 然后前看下一个字符是不是小数点 '.'
          3. 如果是小数点后面还跟着数字 → 当作浮点数，继续吃掉小数部分
          4. 否则当作整数

        不支持的科学计数法如 1e10（因为 NekoLang 语言没有定义这种语法）。

        注意负数不是词法分析器的事！
          遇到 '-' 直接作为"减号"操作符返回。
          负数的处理在语法分析阶段：
            (- 42) 表示负四十二，解析为"运算符 -、操作数 42"
            而不是一步到位看成"负整数 -42"。
        """
        start_col = self.column
        start_line = self.line
        result = ""
        while self.pos < len(self.source) and self.source[self.pos].isdigit():
            result += self._advance()
        if (self.pos < len(self.source) and self.source[self.pos] == '.'
                and self._peek() and self._peek().isdigit()):
            result += self._advance()  # 吃掉小数点
            while self.pos < len(self.source) and self.source[self.pos].isdigit():
                result += self._advance()
            return Token(TokenType.FLOAT, result, start_line, start_col)
        return Token(TokenType.INTEGER, result, start_line, start_col)

    def _read_char(self) -> Token:
        """
        读取字符字面量。

        格式：'一个字符' 或 '\\转义序列'
        例如：'a' 表示字符 a，'\\n' 表示换行符

        处理流程：
          1. 吃掉开头的单引号 '
          2. 看中间的字符是什么：
             a. 如果是反斜杠 \\ → 进入转义序列处理
                - 再走一步吃掉转义符后的那个字符（如 n, t, \\, '）
                - 去 escapes 字典查出它对应的真实字符
                - \\n → 换行符，\\t → 制表符，\\\\ → 反斜杠，\\' → 单引号
             b. 不是反斜杠 → 直接吃一个字符作为内容
          3. 检查后面必须是结尾的单引号 '，否则报错
          4. 吃掉结尾单引号，返回 Token

        三个可能的错误：
          - 空字符字面量：'' 中间什么都没有
          - 没见过的转义序列：比如 \\x \\z 不在 escapes 字典中
          - 缺少结束引号：读到文件末尾也没找到结尾的 '
        """
        start_col = self.column
        start_line = self.line
        self._advance()  # 吃掉开头的单引号

        escapes = {
            "n": "\n",    # 转义序列 \n → 真正的换行符
            "t": "\t",    # 转义序列 \t → 真正的制表符
            "'": "'",     # 转义序列 \' → 真正的单引号
            "\\": "\\",   # 转义序列 \\ → 真正的反斜杠
        }

        ch = self._current()
        if ch is None or ch == "'":
            source_line = self.source_lines[start_line - 1] if start_line <= len(self.source_lines) else ""
            raise LexError(
                "字符字面量不能为空",
                line=start_line,
                column=start_col,
                source_line=source_line,
            )

        if ch is None:
            source_line = self.source_lines[start_line - 1] if start_line <= len(self.source_lines) else ""
            raise LexError(
                "字符字面量缺少结束引号",
                line=start_line,
                column=start_col,
                source_line=source_line,
            )

        if ch == "\\":
            self._advance()
            esc = self._current()
            if esc is None:
                source_line = self.source_lines[start_line - 1] if start_line <= len(self.source_lines) else ""
                raise LexError(
                    "字符字面量缺少结束引号",
                    line=start_line,
                    column=start_col,
                    source_line=source_line,
                )
            if esc not in escapes:
                source_line = self.source_lines[start_line - 1] if start_line <= len(self.source_lines) else ""
                raise LexError(
                    f"未识别的转义序列 '\\{esc}'",
                    line=start_line,
                    column=start_col,
                    source_line=source_line,
                )
            char_val = escapes[esc]
            self._advance()
        else:
            char_val = self._advance()

        if self._current() != "'":
            source_line = self.source_lines[start_line - 1] if start_line <= len(self.source_lines) else ""
            raise LexError(
                "字符字面量缺少结束引号",
                line=start_line,
                column=start_col,
                source_line=source_line,
            )
        self._advance()  # 吃掉结尾的单引号
        return Token(TokenType.CHAR, char_val, start_line, start_col)

    def _read_string(self) -> Token:
        """
        读取字符串字面量。

        格式："任意字符序列，支持转义"
        例如："hello", "hello\\nworld", "say \\"hi\\""

        和字符字面量的区别：
          - 字符用单引号，包一个字符：'a'
          - 字符串用双引号，包零个到任意多个字符："hello"
          - 字符串里双引号需要转义 \\"，单引号不需要
          - 字符串用 chars 列表收集每个字符，最后合并成一个字符串

        实现思路：
          1. 吃掉开头的双引号 "
          2. 逐个读取字符直到遇到结尾的 "：
             a. 遇到反斜杠 \\ → 处理转义序列
             b. 遇到双引号 " → 结束，返回 Token
             c. 其他字符 → 直接加入 chars 列表
          3. 如果文件读完了还没遇到 " → 报错"缺少结束引号"
        """
        start_col = self.column
        start_line = self.line
        self._advance()  # 吃掉开头的双引号
        chars: list[str] = []

        escapes = {
            "n": "\n",    # 转义序列 \n → 换行符
            "t": "\t",    # 转义序列 \t → 制表符
            '"': '"',     # 转义序列 \" → 双引号
            "\\": "\\",   # 转义序列 \\ → 反斜杠
        }

        while self.pos < len(self.source):
            ch = self._current()
            if ch == '"':
                self._advance()
                return Token(TokenType.STRING, "".join(chars), start_line, start_col)
            if ch == "\\":
                self._advance()
                esc = self._current()
                if esc is None:
                    break
                if esc not in escapes:
                    source_line = self.source_lines[start_line - 1] if start_line <= len(self.source_lines) else ""
                    raise LexError(
                        f"未识别的转义序列 '\\{esc}'",
                        line=start_line,
                        column=start_col,
                        source_line=source_line,
                    )
                chars.append(escapes[esc])
                self._advance()
                continue
            chars.append(self._advance())

        source_line = self.source_lines[start_line - 1] if start_line <= len(self.source_lines) else ""
        raise LexError(
            "字符串字面量缺少结束引号",
            line=start_line,
            column=start_col,
            source_line=source_line,
        )

    # ── Token 分发器 ──────────────────────────────────────────

    def next_token(self) -> Token:
        """
        获取下一个 Token——这是词法分析的核心调度方法。

        每次调用只返回一个 Token。
        这个方法实现了类似有限自动机的主循环：
          先跳过空白和注释（它们不产生 Token），
          然后根据当前遇到的第一个有效字符来决定走哪个分支。

        分支判断逻辑（按顺序）：
          1. 字母或下划线开头 → 调用 _read_identifier()
             可能是关键字（if, while, print...），也可能是变量名

          2. 数字开头 → 调用 _read_number()
             可能是整数 42 或浮点数 3.14

          3. 单引号 ' → 调用 _read_char()
             读取字符字面量如 'a'

          4. 双引号 " → 调用 _read_string()
             读取字符串字面量如 "hello"

          5. 字符在 < > ! : 中且下一个是 = → 双字符操作符
             如 <=, >=, !=, :=

          6. 字符在 DELIMITERS 字典中 → 单字符操作符或分隔符
             如 +, -, *, /, (, ), =

          7. 以上都不匹配 → 遇到了源码中无法识别的字符，报错

        如果文件已读完 → 返回 Token(TokenType.EOF, ...) 表示结束。
        """
        while self.pos < len(self.source):
            self._skip_whitespace()
            if self.pos >= len(self.source):
                break
            # 遇到分号开头的是注释，跳过整行
            if self.source[self.pos] == ';':
                self._skip_comment()
                continue       # 跳过注释后继续循环，不产生 Token
            ch = self.source[self.pos]
            start_col = self.column
            start_line = self.line

            # 字母或下划线 —— 标识符或关键字
            # 注意：标识符可以包含短横线（如 my-var, string-length），
            # 所以这里用 isalpha() 而不是直接判断字母表范围
            if ch.isalpha() or ch == '_':
                return self._read_identifier()

            # 数字 —— 整数或浮点数
            if ch.isdigit():
                return self._read_number()

            # 单引号开头 —— 字符字面量
            if ch == "'":
                return self._read_char()
            # 双引号开头 —— 字符串字面量
            if ch == '"':
                return self._read_string()

            # 可能形成双字符操作符的符号：< <= > >= != :=
            # 先看下一个字符是不是 '='，是的话组成双字符操作符
            # 否则 fall through 到下面的单字符判断
            if ch in '<>!:' and self._peek() == '=':
                op = self._advance() + self._advance()
                return Token(DELIMITERS[op], op, start_line, start_col)

            # 单字符分隔符或操作符：+ - * / ( ) = < > 等
            # 这些字符各自独立表意，不需要看后面的字符
            if ch in DELIMITERS:
                self._advance()
                return Token(DELIMITERS[ch], ch, start_line, start_col)

            # 无法识别的字符——源码中出现了既不是关键字、操作符、
            # 也不是字面量的字符，可能是打字错误或编码问题
            bad = self._advance()
            source_line = self.source_lines[start_line - 1] if start_line <= len(self.source_lines) else ""
            raise LexError(
                f"未识别的字符 '{bad}'",
                line=start_line, column=start_col,
                source_line=source_line
            )

        # 所有字符都已处理完毕，返回文件结束标记
        return Token(TokenType.EOF, "", self.line, self.column)

    def tokenize(self) -> list[Token]:
        """
        一次性完成全部词法分析，返回完整的 Token 列表。

        实现方式：
          在循环中反复调用 next_token()，每次拿一个 Token，
          直到拿到文件结束符（EOF）为止。

        为什么需要这个方法而不是只用 next_token()？
          next_token() 是"按需取"，一次只拿一个。
          但 NekoLang 的语法分析器（Parser 类）在初始化时
          需要访问完整的 Token 列表，因为递归下降解析中需要
          向前看任意多个 Token（通过 self.tokens[self.pos]），
          不能用流式处理。所以 tokenize() 就是包装成"一次拿完"。

        实际调用链路：
          Parser(tokens_list)  ← parser 接收的就是 tokenize() 的结果
        """
        tokens = []
        while True:
            tok = self.next_token()
            tokens.append(tok)
            if tok.type == TokenType.EOF:
                break
        return tokens
