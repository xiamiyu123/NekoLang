from enum import Enum
from dataclasses import dataclass


class TokenType(Enum):
    # Literals
    IDENTIFIER = "IDENTIFIER"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"

    # Language keywords
    PROGRAM = "program"        # program entry
    VAR = "var"                # variable declaration
    ASSIGN = ":="              # assignment
    BEGIN = "begin"            # begin/end block
    IF = "if"                  # conditional
    WHILE = "while"            # loop
    PRINT = "print"            # print
    FUNCTION = "function"      # function definition

    # Type keywords
    KW_INT = "int"
    KW_FLOAT = "float"
    KW_CHAR = "char"

    # Array keyword
    ARRAY = "array"

    # Array operations
    ARRAY_SET = "array-set"    # array assignment
    ARRAY_PRINT = "array-print" # array print

    # Delimiters / operators
    LPAREN = "("
    RPAREN = ")"
    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    SLASH = "/"
    LT = "<"
    GT = ">"
    EQ = "="
    LE = "<="
    GE = ">="
    NE = "!="

    # Special
    EOF = "EOF"


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int

    def __repr__(self):
        return f"Token({self.type.value}, {self.value!r}, {self.line}:{self.column})"


# Keyword table: string -> TokenType
KEYWORDS: dict[str, TokenType] = {
    "program": TokenType.PROGRAM,
    "var": TokenType.VAR,
    "begin": TokenType.BEGIN,
    "if": TokenType.IF,
    "while": TokenType.WHILE,
    "print": TokenType.PRINT,
    "function": TokenType.FUNCTION,
    "int": TokenType.KW_INT,
    "float": TokenType.KW_FLOAT,
    "char": TokenType.KW_CHAR,
    "array": TokenType.ARRAY,
    "array-set": TokenType.ARRAY_SET,
    "array-print": TokenType.ARRAY_PRINT,
}

# Delimiter table: single/double char -> TokenType
DELIMITERS: dict[str, TokenType] = {
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.STAR,
    "/": TokenType.SLASH,
    "<": TokenType.LT,
    ">": TokenType.GT,
    "=": TokenType.EQ,
    "<=": TokenType.LE,
    ">=": TokenType.GE,
    "!=": TokenType.NE,
    ":=": TokenType.ASSIGN,
}

# Type sizes for address calculation
TYPE_SIZES: dict[str, int] = {
    "int": 4,
    "float": 8,
    "char": 1,
}
