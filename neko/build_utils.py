"""Shared build utilities for neko.py and nekgo.py."""

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass

from neko.ast_nodes import ProgramNode
from neko.codegen_llvm import LLVMCodegen
from neko.lexer import Lexer
from neko.parser import Parser
from neko.semantic import SemanticAnalyzer


@dataclass
class CompilationResult:
    source: str
    tokens: list
    ast: ProgramNode
    analyzer: SemanticAnalyzer


def read_source(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"错误: 文件 '{path}' 未找到")
        raise SystemExit(1)


def compile_source(source: str) -> CompilationResult:
    lexer = Lexer(source)
    tokens = lexer.tokenize()

    parser = Parser(tokens)
    parser.set_source(source)
    ast = parser.parse()

    analyzer = SemanticAnalyzer()
    analyzer.set_source(source)
    analyzer.analyze(ast)

    return CompilationResult(source=source, tokens=tokens, ast=ast, analyzer=analyzer)


def compile_file(path: str) -> CompilationResult:
    return compile_source(read_source(path))


def print_semantic_errors(analyzer: SemanticAnalyzer) -> None:
    if not analyzer.errors:
        return

    print("=" * 50)
    print("语义错误")
    print("=" * 50)
    for err in analyzer.errors:
        print(err.format())
        print()


def ensure_no_semantic_errors(result: CompilationResult) -> None:
    if result.analyzer.errors:
        print_semantic_errors(result.analyzer)
        raise SystemExit(1)


def generate_ir(ast: ProgramNode) -> str:
    return LLVMCodegen().generate(ast)


def runtime_source_path() -> str:
    neko_pkg_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(neko_pkg_dir)
    return os.path.join(project_root, "runtime", "runtime.c")


def compile_to_executable(ast: ProgramNode, output_path: str, verbose: bool = False) -> str:
    ir_text = generate_ir(ast)

    if verbose:
        print("=" * 50)
        print("LLVM IR")
        print("=" * 50)
        print(ir_text)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ll", delete=False) as f:
        f.write(ir_text)
        ll_path = f.name

    try:
        cmd = ["clang", runtime_source_path(), ll_path, "-o", output_path]
        if verbose:
            print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"clang 编译失败:\n{result.stderr}", file=sys.stderr)
            raise SystemExit(1)
    finally:
        os.unlink(ll_path)

    return output_path


def default_output_name(source_path: str) -> str:
    return os.path.splitext(os.path.basename(source_path))[0]
