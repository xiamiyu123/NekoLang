from enum import Enum
from dataclasses import dataclass


class TokenType(Enum):
    # Literals
    IDENTIFIER = "IDENTIFIER"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"

    # Keywords - cat-themed
    NYA = "nya"               # program entry
    NYAN = "nyan"             # var declaration
    MEOW = "meow"             # assignment
    PAW = "paw"               # begin/end block
    IF_NYA = "if-nya"         # if conditional
    PURR_WHILE = "purr-while" # while loop
    PURR = "purr"             # print
    NYAA_DEF = "nyaa-def"     # function definition

    # Type keywords
    KW_INT = "int"
    KW_FLOAT = "float"
    KW_CHAR = "char"

    # Array keyword
    LITTER_BOX = "litter-box"

    # Assignment operators for arrays
    MEOW_ARR = "meow-arr"     # array assignment
    PURR_ARR = "purr-arr"     # array print

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
    "nya": TokenType.NYA,
    "nyan": TokenType.NYAN,
    "meow": TokenType.MEOW,
    "paw": TokenType.PAW,
    "if-nya": TokenType.IF_NYA,
    "purr-while": TokenType.PURR_WHILE,
    "purr": TokenType.PURR,
    "nyaa-def": TokenType.NYAA_DEF,
    "int": TokenType.KW_INT,
    "float": TokenType.KW_FLOAT,
    "char": TokenType.KW_CHAR,
    "nya-int": TokenType.KW_INT,
    "nya-float": TokenType.KW_FLOAT,
    "nya-char": TokenType.KW_CHAR,
    "litter-box": TokenType.LITTER_BOX,
    "meow-arr": TokenType.MEOW_ARR,
    "purr-arr": TokenType.PURR_ARR,
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
}

# Type sizes for address calculation
TYPE_SIZES: dict[str, int] = {
    "int": 4,
    "float": 8,
    "char": 1,
}
