"""Tests for multi-file compilation with imports."""

import os
import subprocess
import sys
import tempfile
import unittest

from neko.build_utils import compile_file_with_imports, compile_to_executable
from neko.lexer import Lexer
from neko.parser import Parser
from neko.semantic import SemanticAnalyzer


FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestImportParsing(unittest.TestCase):
    """Test that the parser correctly handles import statements."""

    def test_parse_single_import(self):
        source = """(import utils)
(program main (var ((x int))) (begin (:= x 1) (print x)))"""
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        parser.set_source(source)
        ast = parser.parse()
        self.assertEqual(len(ast.imports), 1)
        self.assertEqual(ast.imports[0].path, "utils")

    def test_parse_multiple_imports(self):
        source = """(import math)
(import utils)
(import io)
(program main (var ((x int))) (begin (:= x 1) (print x)))"""
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        parser.set_source(source)
        ast = parser.parse()
        self.assertEqual(len(ast.imports), 3)
        self.assertEqual(ast.imports[1].path, "utils")

    def test_parse_no_imports(self):
        source = "(program main (var ((x int))) (begin (:= x 1) (print x)))"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        parser.set_source(source)
        ast = parser.parse()
        self.assertEqual(len(ast.imports), 0)

    def test_parse_definition_file(self):
        source = """(function add ((a int) (b int)) int
  (return (+ a b)))
(extern printf (int) void)
(function mul ((a int) (b int)) int
  (return (* a b)))"""
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        parser.set_source(source)
        _, defs = parser.parse_definition_file()
        self.assertEqual(len(defs), 3)
        self.assertEqual(defs[0].name, "add")
        self.assertEqual(defs[1].name, "printf")
        self.assertEqual(defs[2].name, "mul")


class TestImportCompilation(unittest.TestCase):
    """Test compilation with imports using actual fixture files."""

    def test_basic_import_llvm(self):
        """Basic import: main file uses a function from an imported definition file."""
        source = """(import import_utils)
(program test_basic
  (var ((result int)))
  (begin
    (:= result (add 10 20))
    (print result)))"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".neko", delete=False, dir=FIXTURES
        ) as f:
            f.write(source)
            tmp_path = f.name

        try:
            result = compile_file_with_imports(tmp_path)
            self.assertEqual(len(result.analyzer.errors), 0)
        finally:
            os.unlink(tmp_path)

    def test_basic_import_arm64(self):
        """Basic import on ARM64 backend."""
        import platform

        if not (platform.system() == "Darwin" and platform.machine() == "arm64"):
            self.skipTest("ARM64 backend only available on Apple Silicon")

        source = """(import import_utils)
(program test_basic
  (var ((result int)))
  (begin
    (:= result (add 10 20))
    (print result)))"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".neko", delete=False, dir=FIXTURES
        ) as f:
            f.write(source)
            tmp_path = f.name

        try:
            result = compile_file_with_imports(tmp_path)
            self.assertEqual(len(result.analyzer.errors), 0)

            with tempfile.TemporaryDirectory() as tmpdir:
                output = os.path.join(tmpdir, "test_basic")
                compile_to_executable(result.ast, output, backend="arm64")
        finally:
            os.unlink(tmp_path)

    def test_chained_import(self):
        """Chained import: A imports B which imports C."""
        source = """(import import_chain_b)
(program test_chain
  (var ((result int)))
  (begin
    (:= result (quadruple 5))
    (print result)))"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".neko", delete=False, dir=FIXTURES
        ) as f:
            f.write(source)
            tmp_path = f.name

        try:
            result = compile_file_with_imports(tmp_path)
            self.assertEqual(len(result.analyzer.errors), 0)
        finally:
            os.unlink(tmp_path)

    def test_import_with_program_header(self):
        """Import a file that has a program header — only function defs are extracted."""
        source = """(import import_with_program)
(program test_prog
  (var ((result int)))
  (begin
    (:= result (multiply 6 7))
    (print result)))"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".neko", delete=False, dir=FIXTURES
        ) as f:
            f.write(source)
            tmp_path = f.name

        try:
            result = compile_file_with_imports(tmp_path)
            self.assertEqual(len(result.analyzer.errors), 0)
        finally:
            os.unlink(tmp_path)

    def test_cyclic_import_detected(self):
        """Circular dependencies should be detected and raise an error."""
        source = """(import import_cycle_a)
(program test_cycle
  (var ((x int)))
  (begin
    (:= x 1)
    (print x)))"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".neko", delete=False, dir=FIXTURES
        ) as f:
            f.write(source)
            tmp_path = f.name

        try:
            with self.assertRaises(SystemExit):
                compile_file_with_imports(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_import_missing_file(self):
        """Importing a non-existent file should raise an error."""
        source = """(import nonexistent_module)
(program test_missing
  (var ((x int)))
  (begin
    (:= x 1)
    (print x)))"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".neko", delete=False, dir=FIXTURES
        ) as f:
            f.write(source)
            tmp_path = f.name

        try:
            with self.assertRaises(SystemExit):
                compile_file_with_imports(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_undefined_function_in_import(self):
        """Semantic error: calling undefined function from imported context."""
        source = """(import import_utils)
(program test_undefined
  (var ((result int)))
  (begin
    (:= result (nonexistent_func 1 2))
    (print result)))"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".neko", delete=False, dir=FIXTURES
        ) as f:
            f.write(source)
            tmp_path = f.name

        try:
            result = compile_file_with_imports(tmp_path)
            self.assertGreater(len(result.analyzer.errors), 0)
        finally:
            os.unlink(tmp_path)


if __name__ == "__main__":
    unittest.main()