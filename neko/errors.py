SUGGESTIONS = {
    "undefined_var": "提示：请先使用 var 声明这个变量。",
    "unexpected_token": "提示：这里出现了不符合语法的符号。",
    "missing_paren": "提示：请检查括号是否匹配。",
    "type_mismatch": "提示：请检查表达式和目标变量的类型是否一致。",
    "invalid_char": "提示：源码中包含无法识别的字符。",
    "duplicate_var": "提示：这个变量已经声明过了。",
}


class NekoError(Exception):
    def __init__(self, phase: str, message: str, line: int = 0, column: int = 0,
                 source_line: str = "", suggestion_key: str = ""):
        self.phase = phase
        self.message = message
        self.line = line
        self.column = column
        self.source_line = source_line
        self.suggestion_key = suggestion_key
        super().__init__(self.format())

    def format(self) -> str:
        parts = [f"[{self.phase}]"]
        if self.line > 0:
            parts.append(f"Line {self.line}, Column {self.column}:")
        parts.append(self.message)

        result = " ".join(parts)

        if self.source_line:
            result += f"\n  {self.source_line}"
            if self.column > 0:
                result += f"\n  {' ' * (self.column - 1)}^"

        if self.suggestion_key and self.suggestion_key in SUGGESTIONS:
            result += "\n" + SUGGESTIONS[self.suggestion_key]

        return result


class LexError(NekoError):
    def __init__(self, message: str, line: int = 0, column: int = 0,
                 source_line: str = "", suggestion_key: str = "invalid_char"):
        super().__init__("Lexer", message, line, column, source_line, suggestion_key)


class ParseError(NekoError):
    def __init__(self, message: str, line: int = 0, column: int = 0,
                 source_line: str = "", suggestion_key: str = "unexpected_token"):
        super().__init__("Parser", message, line, column, source_line, suggestion_key)


class SemanticError(NekoError):
    def __init__(self, message: str, line: int = 0, column: int = 0,
                 source_line: str = "", suggestion_key: str = ""):
        super().__init__("Semantic", message, line, column, source_line, suggestion_key)
