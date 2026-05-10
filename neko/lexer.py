from .tokens import Token, TokenType, KEYWORDS, DELIMITERS
from .errors import LexError


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.source_lines = source.splitlines()

    def _current(self) -> str | None:
        if self.pos < len(self.source):
            return self.source[self.pos]
        return None

    def _peek(self, offset: int = 1) -> str | None:
        pos = self.pos + offset
        if pos < len(self.source):
            return self.source[pos]
        return None

    def _advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _skip_whitespace(self):
        while self.pos < len(self.source) and self.source[self.pos] in ' \t\n\r':
            self._advance()

    def _skip_comment(self):
        if self._current() == ';':
            while self.pos < len(self.source) and self.source[self.pos] != '\n':
                self._advance()

    def _read_identifier(self) -> Token:
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
        start_col = self.column
        start_line = self.line
        result = ""
        while self.pos < len(self.source) and self.source[self.pos].isdigit():
            result += self._advance()
        if (self.pos < len(self.source) and self.source[self.pos] == '.'
                and self._peek() and self._peek().isdigit()):
            result += self._advance()  # consume '.'
            while self.pos < len(self.source) and self.source[self.pos].isdigit():
                result += self._advance()
            return Token(TokenType.FLOAT, result, start_line, start_col)
        return Token(TokenType.INTEGER, result, start_line, start_col)

    def next_token(self) -> Token:
        while self.pos < len(self.source):
            self._skip_whitespace()
            if self.pos >= len(self.source):
                break
            # Skip comments
            if self.source[self.pos] == ';':
                self._skip_comment()
                continue
            ch = self.source[self.pos]
            start_col = self.column
            start_line = self.line

            # Identifiers and keywords (including hyphenated)
            if ch.isalpha() or ch == '_':
                return self._read_identifier()

            # Numbers
            if ch.isdigit():
                return self._read_number()

            # Two-char operators
            if ch in '<>!:' and self._peek() == '=':
                op = self._advance() + self._advance()
                return Token(DELIMITERS[op], op, start_line, start_col)

            # Single-char delimiters/operators
            if ch in DELIMITERS:
                self._advance()
                return Token(DELIMITERS[ch], ch, start_line, start_col)

            # Unknown character
            bad = self._advance()
            source_line = self.source_lines[start_line - 1] if start_line <= len(self.source_lines) else ""
            raise LexError(
                f"未识别的字符 '{bad}'",
                line=start_line, column=start_col,
                source_line=source_line
            )

        return Token(TokenType.EOF, "", self.line, self.column)

    def tokenize(self) -> list[Token]:
        tokens = []
        while True:
            tok = self.next_token()
            tokens.append(tok)
            if tok.type == TokenType.EOF:
                break
        return tokens
