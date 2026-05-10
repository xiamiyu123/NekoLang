import unittest
from neko.lexer import Lexer
from neko.tokens import TokenType
from neko.errors import LexError


class TestLexerKeywords(unittest.TestCase):
    def test_program_keyword(self):
        tokens = Lexer("program").tokenize()
        self.assertEqual(tokens[0].type, TokenType.PROGRAM)
        self.assertEqual(tokens[0].value, "program")

    def test_var_keyword(self):
        tokens = Lexer("var").tokenize()
        self.assertEqual(tokens[0].type, TokenType.VAR)

    def test_assign_operator(self):
        tokens = Lexer(":=").tokenize()
        self.assertEqual(tokens[0].type, TokenType.ASSIGN)

    def test_begin_keyword(self):
        tokens = Lexer("begin").tokenize()
        self.assertEqual(tokens[0].type, TokenType.BEGIN)

    def test_if_keyword(self):
        tokens = Lexer("if").tokenize()
        self.assertEqual(tokens[0].type, TokenType.IF)

    def test_while_keyword(self):
        tokens = Lexer("while").tokenize()
        self.assertEqual(tokens[0].type, TokenType.WHILE)

    def test_print_keyword(self):
        tokens = Lexer("print").tokenize()
        self.assertEqual(tokens[0].type, TokenType.PRINT)

    def test_type_keywords(self):
        for kw, expected in [("int", TokenType.KW_INT),
                             ("float", TokenType.KW_FLOAT),
                             ("char", TokenType.KW_CHAR)]:
            tokens = Lexer(kw).tokenize()
            self.assertEqual(tokens[0].type, expected)

    def test_array_keywords(self):
        for kw, expected in [("array", TokenType.ARRAY),
                             ("array-set", TokenType.ARRAY_SET),
                             ("array-print", TokenType.ARRAY_PRINT)]:
            tokens = Lexer(kw).tokenize()
            self.assertEqual(tokens[0].type, expected)

    def test_personalized_keyword_aliases(self):
        aliases = [
            ("nya", TokenType.PROGRAM),
            ("nyan", TokenType.VAR),
            ("paw", TokenType.BEGIN),
            ("purr-while", TokenType.WHILE),
            ("purr", TokenType.PRINT),
            ("meow", TokenType.PRINT),
            ("nyaa-def", TokenType.FUNCTION),
            ("neko-box", TokenType.ARRAY),
            ("meow-arr", TokenType.ARRAY_SET),
            ("purr-arr", TokenType.ARRAY_PRINT),
        ]
        for alias, expected in aliases:
            tokens = Lexer(alias).tokenize()
            self.assertEqual(tokens[0].type, expected)

    def test_removed_keyword_aliases_are_identifiers(self):
        for old_alias in ["if-nya", "litter-box"]:
            tokens = Lexer(old_alias).tokenize()
            self.assertEqual(tokens[0].type, TokenType.IDENTIFIER)

    def test_removed_type_aliases_are_identifiers(self):
        for old_alias in ["nya-int", "nya-float", "nya-char"]:
            tokens = Lexer(old_alias).tokenize()
            self.assertEqual(tokens[0].type, TokenType.IDENTIFIER)


class TestLexerIdentifiers(unittest.TestCase):
    def test_simple_identifier(self):
        tokens = Lexer("foo").tokenize()
        self.assertEqual(tokens[0].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].value, "foo")

    def test_identifier_with_digits(self):
        tokens = Lexer("var123").tokenize()
        self.assertEqual(tokens[0].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].value, "var123")

    def test_identifier_with_underscore(self):
        tokens = Lexer("my_var").tokenize()
        self.assertEqual(tokens[0].type, TokenType.IDENTIFIER)


class TestLexerNumbers(unittest.TestCase):
    def test_integer(self):
        tokens = Lexer("42").tokenize()
        self.assertEqual(tokens[0].type, TokenType.INTEGER)
        self.assertEqual(tokens[0].value, "42")

    def test_float(self):
        tokens = Lexer("3.14").tokenize()
        self.assertEqual(tokens[0].type, TokenType.FLOAT)
        self.assertEqual(tokens[0].value, "3.14")

    def test_zero(self):
        tokens = Lexer("0").tokenize()
        self.assertEqual(tokens[0].type, TokenType.INTEGER)
        self.assertEqual(tokens[0].value, "0")


class TestLexerOperators(unittest.TestCase):
    def test_single_char_ops(self):
        for op in ["+", "-", "*", "/", "(", ")"]:
            tokens = Lexer(op).tokenize()
            self.assertEqual(tokens[0].value, op)

    def test_double_char_ops(self):
        for op in ["<=", ">=", "!="]:
            tokens = Lexer(op).tokenize()
            self.assertEqual(tokens[0].value, op)

    def test_comparison_ops(self):
        for op in ["<", ">", "="]:
            tokens = Lexer(op).tokenize()
            self.assertEqual(tokens[0].value, op)


class TestLexerComments(unittest.TestCase):
    def test_comment_is_skipped(self):
        tokens = Lexer("; this is a comment\nprogram").tokenize()
        self.assertEqual(tokens[0].type, TokenType.PROGRAM)

    def test_inline_comment(self):
        tokens = Lexer("program ; program name\nfoo").tokenize()
        self.assertEqual(tokens[0].type, TokenType.PROGRAM)
        self.assertEqual(tokens[1].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[1].value, "foo")


class TestLexerLineTracking(unittest.TestCase):
    def test_line_number(self):
        tokens = Lexer("a\nb\nc").tokenize()
        self.assertEqual(tokens[0].line, 1)
        self.assertEqual(tokens[1].line, 2)
        self.assertEqual(tokens[2].line, 3)

    def test_column_tracking(self):
        tokens = Lexer("a b c").tokenize()
        self.assertEqual(tokens[0].column, 1)
        self.assertEqual(tokens[1].column, 3)
        self.assertEqual(tokens[2].column, 5)


class TestLexerErrors(unittest.TestCase):
    def test_invalid_character(self):
        with self.assertRaises(LexError):
            Lexer("~").tokenize()

    def test_error_has_line_info(self):
        try:
            Lexer("a\n~").tokenize()
        except LexError as e:
            self.assertEqual(e.line, 2)
            return
        self.fail("Expected LexError")


class TestLexerFullProgram(unittest.TestCase):
    def test_tokenize_demo(self):
        source = "(program example (var ((a int))) (begin (:= a 2) (print a)))"
        tokens = Lexer(source).tokenize()
        self.assertEqual(tokens[-1].type, TokenType.EOF)
        types = [t.type for t in tokens]
        self.assertIn(TokenType.PROGRAM, types)
        self.assertIn(TokenType.VAR, types)
        self.assertIn(TokenType.ASSIGN, types)
        self.assertIn(TokenType.BEGIN, types)
        self.assertIn(TokenType.PRINT, types)


if __name__ == "__main__":
    unittest.main()
