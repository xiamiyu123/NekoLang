from enum import Enum
from dataclasses import dataclass


class TokenType(Enum):
    # Literals
    IDENTIFIER = "IDENTIFIER"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    BOOLEAN = "BOOLEAN"
    STRING = "STRING"

    # Language keywords
    PROGRAM = "program"        # program entry
    VAR = "var"                # variable declaration
    ASSIGN = ":="              # assignment
    BEGIN = "begin"            # begin/end block
    IF = "if"                  # conditional
    WHILE = "while"            # loop
    PRINT = "print"            # print
    FUNCTION = "function"      # function definition
    EXTERN = "extern"          # external function declaration
    IMPORT = "import"          # import module
    RETURN = "return"          # function return

    # Type keywords
    KW_INT = "int"
    KW_FLOAT = "float"
    KW_CHAR = "char"
    KW_BOOL = "bool"
    KW_STRING = "string"
    KW_POINTER = "pointer"

    # Char literal
    CHAR = "CHAR"

    # Lambda
    LAMBDA = "lambda"

    # Array keyword
    ARRAY = "array"

    # Array operations
    ARRAY_SET = "array-set"    # array assignment
    ARRAY_PRINT = "array-print" # array print
    ARGC = "argc"
    ARGV_INT = "argv-int"
    ARGV_FLOAT = "argv-float"
    ARGV_CHAR = "argv-char"
    ARGV_BOOL = "argv-bool"
    INPUT_INT = "input-int"
    INPUT_FLOAT = "input-float"
    INPUT_CHAR = "input-char"
    INPUT_BOOL = "input-bool"
    RAND_SEED = "rand-seed"
    RAND_RANGE = "rand-range"
    READ_INT = "read-int"
    READ_FLOAT = "read-float"
    READ_CHAR = "read-char"
    READ_BOOL = "read-bool"
    WRITE_INT = "write-int"
    WRITE_FLOAT = "write-float"
    WRITE_CHAR = "write-char"
    WRITE_BOOL = "write-bool"

    # String operations
    STRING_LENGTH = "string-length"
    STRING_AT = "string-at"
    STRING_SUB = "string-sub"
    STRING_CMP = "string-cmp"
    STRING_CONTAINS = "string-contains"
    INT_TO_STRING = "int-to-string"
    STRING_TO_INT = "string-to-int"
    ARGV_STRING = "argv-string"

    # Char operations
    CHAR_TO_INT = "char-to-int"
    INT_TO_CHAR = "int-to-char"
    CHAR_TO_STRING = "char-to-string"
    IS_LETTER = "is-letter"
    IS_DIGIT = "is-digit"
    CHAR_UPCASE = "char-upcase"
    CHAR_DOWNCASE = "char-downcase"

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
    "nya": TokenType.PROGRAM,
    "var": TokenType.VAR,
    "nyan": TokenType.VAR,
    "begin": TokenType.BEGIN,
    "paw": TokenType.BEGIN,
    "if": TokenType.IF,
    "while": TokenType.WHILE,
    "purr-while": TokenType.WHILE,
    "print": TokenType.PRINT,
    "purr": TokenType.PRINT,
    "meow": TokenType.PRINT,
    "function": TokenType.FUNCTION,
    "nyaa-def": TokenType.FUNCTION,
    "extern": TokenType.EXTERN,
    "import": TokenType.IMPORT,
    "return": TokenType.RETURN,
    "int": TokenType.KW_INT,
    "float": TokenType.KW_FLOAT,
    "char": TokenType.KW_CHAR,
    "bool": TokenType.KW_BOOL,
    "pointer": TokenType.KW_POINTER,
    "true": TokenType.BOOLEAN,
    "false": TokenType.BOOLEAN,
    "lambda": TokenType.LAMBDA,
    "array": TokenType.ARRAY,
    "neko-box": TokenType.ARRAY,
    "array-set": TokenType.ARRAY_SET,
    "meow-arr": TokenType.ARRAY_SET,
    "array-print": TokenType.ARRAY_PRINT,
    "purr-arr": TokenType.ARRAY_PRINT,
    "argc": TokenType.ARGC,
    "argv-int": TokenType.ARGV_INT,
    "argv-float": TokenType.ARGV_FLOAT,
    "argv-char": TokenType.ARGV_CHAR,
    "argv-bool": TokenType.ARGV_BOOL,
    "input-int": TokenType.INPUT_INT,
    "input-float": TokenType.INPUT_FLOAT,
    "input-char": TokenType.INPUT_CHAR,
    "input-bool": TokenType.INPUT_BOOL,
    "rand-seed": TokenType.RAND_SEED,
    "rand-range": TokenType.RAND_RANGE,
    "read-int": TokenType.READ_INT,
    "read-float": TokenType.READ_FLOAT,
    "read-char": TokenType.READ_CHAR,
    "read-bool": TokenType.READ_BOOL,
    "write-int": TokenType.WRITE_INT,
    "write-float": TokenType.WRITE_FLOAT,
    "write-char": TokenType.WRITE_CHAR,
    "write-bool": TokenType.WRITE_BOOL,
    "string": TokenType.KW_STRING,
    "string-length": TokenType.STRING_LENGTH,
    "string-at": TokenType.STRING_AT,
    "string-sub": TokenType.STRING_SUB,
    "string-cmp": TokenType.STRING_CMP,
    "string-contains": TokenType.STRING_CONTAINS,
    "int-to-string": TokenType.INT_TO_STRING,
    "string-to-int": TokenType.STRING_TO_INT,
    "argv-string": TokenType.ARGV_STRING,
    "char-to-int": TokenType.CHAR_TO_INT,
    "int-to-char": TokenType.INT_TO_CHAR,
    "char-to-string": TokenType.CHAR_TO_STRING,
    "is-letter": TokenType.IS_LETTER,
    "is-digit": TokenType.IS_DIGIT,
    "char-upcase": TokenType.CHAR_UPCASE,
    "char-downcase": TokenType.CHAR_DOWNCASE,
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
    "bool": 1,
    "string": 8,
    "pointer": 8,
    "func": 8,
}
