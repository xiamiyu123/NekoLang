"""Tests for the NekoLang ARM64 backend."""

from __future__ import annotations

import platform
import unittest

import tests.test_llvm as llvm_tests
from tests._codegen_support import (
    compile_and_run as _compile_and_run,
    compile_and_run_process as _compile_and_run_process,
    compile_and_run_with_args as _compile_and_run_with_args,
    compile_and_run_with_input as _compile_and_run_with_input,
    generate_asm_text,
)


ARM64_HOST = platform.system() == "Darwin" and platform.machine() == "arm64"


def compile_and_run(source: str) -> str:
    return _compile_and_run(source, backend="arm64")


def compile_and_run_process(
    source: str, args: list[str] | None = None, stdin_data: str | None = None
):
    return _compile_and_run_process(source, backend="arm64", args=args, stdin_data=stdin_data)


def compile_and_run_with_args(source: str, args: list[str] | None = None) -> str:
    return _compile_and_run_with_args(source, args=args, backend="arm64")


def compile_and_run_with_input(source: str, stdin_data: str) -> str:
    return _compile_and_run_with_input(source, stdin_data=stdin_data, backend="arm64")


class TestARM64AssemblyGeneration(unittest.TestCase):
    def test_program_structure(self):
        asm = generate_asm_text("(program t (begin (print 0)))")
        self.assertIn(".section\t__TEXT,__text,regular,pure_instructions", asm)
        self.assertIn(".globl\t_main", asm)
        self.assertIn("ret", asm)

    def test_prologue_and_epilogue(self):
        asm = generate_asm_text("(program t (begin (print 0)))")
        self.assertIn("stp\tx29, x30", asm)
        self.assertIn("ldp\tx29, x30", asm)

    def test_branch_generation(self):
        asm = generate_asm_text("(program t (var ((x int))) (begin (if (> x 0) (:= x 1) (:= x 0))))")
        self.assertIn("b.eq", asm)

    def test_print_call(self):
        asm = generate_asm_text("(program t (var ((x int))) (begin (:= x 42) (print x)))")
        self.assertIn("bl\t_nekoprint_int", asm)

    def test_string_literals(self):
        asm = generate_asm_text('(program t (begin (print "你好")))')
        self.assertIn(".section\t__TEXT,__cstring,cstring_literals", asm)
        self.assertIn("adrp\tx0", asm)

    def test_float_literals(self):
        asm = generate_asm_text("(program t (var ((x float))) (begin (:= x 3.14) (print x)))")
        self.assertIn(".section\t__TEXT,__const", asm)
        self.assertIn("adrp\tx9", asm)

    def test_extern_call(self):
        asm = generate_asm_text(
            '(program t (var ((x int))) (begin (extern atoi (string) int) (:= x (atoi "42")) (print x)))'
        )
        self.assertIn("bl\t_atoi", asm)


class Arm64BackendMixin:
    def setUp(self):
        super().setUp()
        self._old_compile_and_run = llvm_tests.compile_and_run
        self._old_compile_and_run_process = llvm_tests.compile_and_run_process
        self._old_compile_and_run_with_args = llvm_tests.compile_and_run_with_args
        self._old_compile_and_run_with_input = llvm_tests.compile_and_run_with_input
        llvm_tests.compile_and_run = compile_and_run
        llvm_tests.compile_and_run_process = compile_and_run_process
        llvm_tests.compile_and_run_with_args = compile_and_run_with_args
        llvm_tests.compile_and_run_with_input = compile_and_run_with_input

    def tearDown(self):
        llvm_tests.compile_and_run = self._old_compile_and_run
        llvm_tests.compile_and_run_process = self._old_compile_and_run_process
        llvm_tests.compile_and_run_with_args = self._old_compile_and_run_with_args
        llvm_tests.compile_and_run_with_input = self._old_compile_and_run_with_input
        super().tearDown()


@unittest.skipUnless(ARM64_HOST, "ARM64 backend execution tests require Apple Silicon macOS")
class TestARM64BasicExecution(Arm64BackendMixin, llvm_tests.TestBasicExecution):
    pass


@unittest.skipUnless(ARM64_HOST, "ARM64 backend execution tests require Apple Silicon macOS")
class TestARM64ControlFlow(Arm64BackendMixin, llvm_tests.TestControlFlow):
    pass


@unittest.skipUnless(ARM64_HOST, "ARM64 backend execution tests require Apple Silicon macOS")
class TestARM64ComparisonOps(Arm64BackendMixin, llvm_tests.TestComparisonOps):
    pass


@unittest.skipUnless(ARM64_HOST, "ARM64 backend execution tests require Apple Silicon macOS")
class TestARM64IntegrationPrograms(Arm64BackendMixin, llvm_tests.TestIntegrationPrograms):
    pass


@unittest.skipUnless(ARM64_HOST, "ARM64 backend execution tests require Apple Silicon macOS")
class TestARM64StringOperations(Arm64BackendMixin, llvm_tests.TestStringOperations):
    pass


@unittest.skipUnless(ARM64_HOST, "ARM64 backend execution tests require Apple Silicon macOS")
class TestARM64CharOperations(Arm64BackendMixin, llvm_tests.TestCharOperations):
    pass


@unittest.skipUnless(ARM64_HOST, "ARM64 backend execution tests require Apple Silicon macOS")
class TestARM64Lambda(Arm64BackendMixin, llvm_tests.TestLambda):
    pass
