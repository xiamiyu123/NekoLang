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

    def test_return_keyword(self):
        tokens = Lexer("return").tokenize()
        self.assertEqual(tokens[0].type, TokenType.RETURN)

    def test_extern_keyword(self):
        tokens = Lexer("extern").tokenize()
        self.assertEqual(tokens[0].type, TokenType.EXTERN)

    def test_type_keywords(self):
        for kw, expected in [("int", TokenType.KW_INT),
                             ("float", TokenType.KW_FLOAT),
                             ("char", TokenType.KW_CHAR),
                             ("bool", TokenType.KW_BOOL)]:
            tokens = Lexer(kw).tokenize()
            self.assertEqual(tokens[0].type, expected)

    def test_array_keywords(self):
        for kw, expected in [("array", TokenType.ARRAY),
                             ("array-set", TokenType.ARRAY_SET),
                             ("array-print", TokenType.ARRAY_PRINT)]:
            tokens = Lexer(kw).tokenize()
            self.assertEqual(tokens[0].type, expected)

    def test_runtime_keywords(self):
        keywords = [
            ("argc", TokenType.ARGC),
            ("argv-int", TokenType.ARGV_INT),
            ("argv-float", TokenType.ARGV_FLOAT),
            ("argv-char", TokenType.ARGV_CHAR),
            ("argv-bool", TokenType.ARGV_BOOL),
            ("input-int", TokenType.INPUT_INT),
            ("input-float", TokenType.INPUT_FLOAT),
            ("input-char", TokenType.INPUT_CHAR),
            ("input-bool", TokenType.INPUT_BOOL),
            ("rand-seed", TokenType.RAND_SEED),
            ("rand-range", TokenType.RAND_RANGE),
            ("read-int", TokenType.READ_INT),
            ("read-float", TokenType.READ_FLOAT),
            ("read-char", TokenType.READ_CHAR),
            ("read-bool", TokenType.READ_BOOL),
            ("write-int", TokenType.WRITE_INT),
            ("write-float", TokenType.WRITE_FLOAT),
            ("write-char", TokenType.WRITE_CHAR),
            ("write-bool", TokenType.WRITE_BOOL),
        ]
        for kw, expected in keywords:
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

    def test_boolean(self):
        for value in ["true", "false"]:
            tokens = Lexer(value).tokenize()
            self.assertEqual(tokens[0].type, TokenType.BOOLEAN)
            self.assertEqual(tokens[0].value, value)

    def test_string(self):
        tokens = Lexer('"hello\\nworld"').tokenize()
        self.assertEqual(tokens[0].type, TokenType.STRING)
        self.assertEqual(tokens[0].value, "hello\nworld")


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

    def test_unterminated_string(self):
        with self.assertRaises(LexError):
            Lexer('"oops').tokenize()


class TestLexerCharLiteral(unittest.TestCase):
    def test_simple_char(self):
        tokens = Lexer("'a'").tokenize()
        self.assertEqual(tokens[0].type, TokenType.CHAR)
        self.assertEqual(tokens[0].value, "a")

    def test_escape_newline(self):
        tokens = Lexer(r"'\n'").tokenize()
        self.assertEqual(tokens[0].type, TokenType.CHAR)
        self.assertEqual(tokens[0].value, "\n")

    def test_escape_tab(self):
        tokens = Lexer(r"'\t'").tokenize()
        self.assertEqual(tokens[0].type, TokenType.CHAR)
        self.assertEqual(tokens[0].value, "\t")

    def test_escape_quote(self):
        tokens = Lexer(r"'\''").tokenize()
        self.assertEqual(tokens[0].type, TokenType.CHAR)
        self.assertEqual(tokens[0].value, "'")

    def test_escape_backslash(self):
        tokens = Lexer(r"'\\'").tokenize()
        self.assertEqual(tokens[0].type, TokenType.CHAR)
        self.assertEqual(tokens[0].value, "\\")

    def test_unterminated_char(self):
        with self.assertRaises(LexError):
            Lexer("'a").tokenize()

    def test_empty_char(self):
        with self.assertRaises(LexError):
            Lexer("''").tokenize()

    def test_invalid_escape(self):
        with self.assertRaises(LexError):
            Lexer(r"'\a'").tokenize()

    def test_invalid_escape_in_string(self):
        with self.assertRaises(LexError):
            Lexer(r"'\a'").tokenize()


class TestLexerStringKeywords(unittest.TestCase):
    def test_string_type_keyword(self):
        tokens = Lexer("string").tokenize()
        self.assertEqual(tokens[0].type, TokenType.KW_STRING)
        self.assertEqual(tokens[0].value, "string")

    def test_string_operations(self):
        keywords = [
            ("string-length", TokenType.STRING_LENGTH),
            ("string-at", TokenType.STRING_AT),
            ("string-sub", TokenType.STRING_SUB),
            ("string-cmp", TokenType.STRING_CMP),
            ("string-contains", TokenType.STRING_CONTAINS),
            ("int-to-string", TokenType.INT_TO_STRING),
            ("string-to-int", TokenType.STRING_TO_INT),
            ("argv-string", TokenType.ARGV_STRING),
        ]
        for kw, expected in keywords:
            tokens = Lexer(kw).tokenize()
            self.assertEqual(tokens[0].type, expected, f"Failed for {kw}")

    def test_char_operations(self):
        keywords = [
            ("char-to-int", TokenType.CHAR_TO_INT),
            ("int-to-char", TokenType.INT_TO_CHAR),
            ("char-to-string", TokenType.CHAR_TO_STRING),
            ("is-letter", TokenType.IS_LETTER),
            ("is-digit", TokenType.IS_DIGIT),
            ("char-upcase", TokenType.CHAR_UPCASE),
            ("char-downcase", TokenType.CHAR_DOWNCASE),
        ]
        for kw, expected in keywords:
            tokens = Lexer(kw).tokenize()
            self.assertEqual(tokens[0].type, expected, f"Failed for {kw}")


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


class TestLexerEdgeCases(unittest.TestCase):
    """Edge case tests for lexer stability."""

    def test_empty_input(self):
        """Empty input should produce only EOF token."""
        tokens = Lexer("").tokenize()
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, TokenType.EOF)

    def test_whitespace_only_input(self):
        """Whitespace-only input should produce only EOF token."""
        tokens = Lexer("   \n\t  ").tokenize()
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, TokenType.EOF)

    def test_comment_only_input(self):
        """Comment-only input should produce only EOF token."""
        tokens = Lexer("; this is a comment").tokenize()
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, TokenType.EOF)

    def test_multiple_consecutive_comments(self):
        """Multiple comments should be skipped correctly."""
        source = "; comment1\n; comment2\n; comment3\nprogram"
        tokens = Lexer(source).tokenize()
        self.assertEqual(tokens[0].type, TokenType.PROGRAM)

    def test_keyword_boundary_whilex(self):
        """'whilex' should be identifier, not keyword."""
        tokens = Lexer("whilex").tokenize()
        self.assertEqual(tokens[0].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].value, "whilex")

    def test_keyword_boundary_ifx(self):
        """'ifx' should be identifier, not keyword."""
        tokens = Lexer("ifx").tokenize()
        self.assertEqual(tokens[0].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].value, "ifx")

    def test_keyword_boundary_beginx(self):
        """'beginx' should be identifier, not keyword."""
        tokens = Lexer("beginx").tokenize()
        self.assertEqual(tokens[0].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].value, "beginx")

    def test_empty_string_literal(self):
        """Empty string literal should lex correctly."""
        tokens = Lexer('""').tokenize()
        self.assertEqual(tokens[0].type, TokenType.STRING)
        self.assertEqual(tokens[0].value, "")

    def test_string_with_escape_sequences(self):
        """String with various escape sequences."""
        tokens = Lexer('"\\n\\t\\\\"').tokenize()
        self.assertEqual(tokens[0].type, TokenType.STRING)
        self.assertEqual(tokens[0].value, "\n\t\\")

    def test_string_with_escaped_quotes(self):
        """String with escaped quotes."""
        tokens = Lexer('"hello\\"world"').tokenize()
        self.assertEqual(tokens[0].type, TokenType.STRING)
        self.assertIn('"', tokens[0].value)

    def test_multiple_tokens_with_comments(self):
        """Comments interspersed with tokens."""
        source = "; comment1\nprogram ; comment2\n(begin ; comment3\n(print 0))"
        tokens = Lexer(source).tokenize()
        self.assertEqual(tokens[0].type, TokenType.PROGRAM)
        self.assertEqual(tokens[-1].type, TokenType.EOF)

    def test_negative_number_as_expression(self):
        """Negative numbers are expressed as (- 0 n), not as single tokens."""
        source = "(- 0 42)"
        tokens = Lexer(source).tokenize()
        self.assertEqual(tokens[0].type, TokenType.LPAREN)
        self.assertEqual(tokens[1].type, TokenType.MINUS)
        self.assertEqual(tokens[2].type, TokenType.INTEGER)
        self.assertEqual(tokens[2].value, "0")
        self.assertEqual(tokens[3].type, TokenType.INTEGER)
        self.assertEqual(tokens[3].value, "42")

    def test_large_integer(self):
        """Large integer should be tokenized correctly."""
        tokens = Lexer("2147483647").tokenize()
        self.assertEqual(tokens[0].type, TokenType.INTEGER)
        self.assertEqual(tokens[0].value, "2147483647")

    def test_zero_float(self):
        """Zero as float should be tokenized correctly."""
        tokens = Lexer("0.0").tokenize()
        self.assertEqual(tokens[0].type, TokenType.FLOAT)
        self.assertEqual(tokens[0].value, "0.0")

    def test_negative_float(self):
        """Negative float should be tokenized correctly (as separate tokens)."""
        source = "(- 0.0 3.14)"
        tokens = Lexer(source).tokenize()
        self.assertEqual(tokens[0].type, TokenType.LPAREN)
        self.assertEqual(tokens[1].type, TokenType.MINUS)
        self.assertEqual(tokens[2].type, TokenType.FLOAT)
        self.assertEqual(tokens[2].value, "0.0")
        self.assertEqual(tokens[3].type, TokenType.FLOAT)
        self.assertEqual(tokens[3].value, "3.14")

    def test_very_small_float(self):
        """Very small float should be tokenized correctly."""
        tokens = Lexer("0.000001").tokenize()
        self.assertEqual(tokens[0].type, TokenType.FLOAT)
        self.assertEqual(tokens[0].value, "0.000001")

    def test_char_literal_unicode(self):
        """Unicode character literal should lex correctly."""
        tokens = Lexer("'中'").tokenize()
        self.assertEqual(tokens[0].type, TokenType.CHAR)
        self.assertEqual(tokens[0].value, "中")

    def test_char_literal_escape(self):
        """Escape character literal should lex correctly."""
        tokens = Lexer("'\\n'").tokenize()
        self.assertEqual(tokens[0].type, TokenType.CHAR)
        self.assertEqual(tokens[0].value, "\n")

    def test_identifier_with_underscores(self):
        """Identifier with underscores should be tokenized correctly."""
        tokens = Lexer("my_var_name").tokenize()
        self.assertEqual(tokens[0].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].value, "my_var_name")

    def test_identifier_starting_with_underscore(self):
        """Identifier starting with underscore should be tokenized correctly."""
        tokens = Lexer("_private").tokenize()
        self.assertEqual(tokens[0].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].value, "_private")

    def test_mixed_tokens_with_newlines(self):
        """Tokens separated by newlines should be tracked correctly."""
        source = "program\nvar\nbegin"
        tokens = Lexer(source).tokenize()
        self.assertEqual(tokens[0].type, TokenType.PROGRAM)
        self.assertEqual(tokens[1].type, TokenType.VAR)
        self.assertEqual(tokens[2].type, TokenType.BEGIN)

    def test_column_tracking_after_string(self):
        """Column tracking should work after string literals."""
        source = '(print "hello")'
        tokens = Lexer(source).tokenize()
        # ( at column 1, print at column 2, "hello" at column 8, ) at column 15
        self.assertEqual(tokens[0].column, 1)
        self.assertEqual(tokens[0].type, TokenType.LPAREN)
        self.assertEqual(tokens[1].column, 2)
        self.assertEqual(tokens[1].type, TokenType.PRINT)
        self.assertEqual(tokens[2].column, 8)
        self.assertEqual(tokens[2].type, TokenType.STRING)
        self.assertEqual(tokens[3].column, 15)
        self.assertEqual(tokens[3].type, TokenType.RPAREN)

    def test_line_tracking_multiline(self):
        """Line tracking should work across multiple lines."""
        source = "program\nvar\nbegin"
        tokens = Lexer(source).tokenize()
        self.assertEqual(tokens[0].line, 1)
        self.assertEqual(tokens[1].line, 2)
        self.assertEqual(tokens[2].line, 3)


if __name__ == "__main__":
    unittest.main()
