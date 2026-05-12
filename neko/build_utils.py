"""Shared build utilities for neko.py and nekgo.py."""

import os
import platform
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Literal

from neko.ast_nodes import ProgramNode
from neko.codegen_arm64 import ARM64Codegen
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


@dataclass
class CodegenArtifact:
    backend: Literal["llvm", "arm64"]
    text: str
    extension: str


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


def _is_arm64_darwin() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def _resolve_backend(requested: str) -> Literal["llvm", "arm64"]:
    if requested == "auto":
        return "arm64" if _is_arm64_darwin() else "llvm"
    if requested in {"llvm", "arm64"}:
        return requested
    raise ValueError(f"unknown backend: {requested}")


def generate_code(ast: ProgramNode, backend: str = "auto") -> CodegenArtifact:
    resolved = _resolve_backend(backend)
    if resolved == "llvm":
        return CodegenArtifact(backend="llvm", text=LLVMCodegen().generate(ast), extension=".ll")
    return CodegenArtifact(backend="arm64", text=ARM64Codegen().generate(ast), extension=".s")


def generate_ir(ast: ProgramNode) -> str:
    return generate_code(ast, "llvm").text


def generate_assembly(ast: ProgramNode) -> str:
    return generate_code(ast, "arm64").text


def runtime_source_path() -> str:
    neko_pkg_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(neko_pkg_dir)
    return os.path.join(project_root, "runtime", "runtime.c")


def compile_to_executable(
    ast: ProgramNode,
    output_path: str,
    backend: str = "auto",
    verbose: bool = False,
) -> str:
    artifact = generate_code(ast, backend=backend)

    if artifact.backend == "arm64" and not _is_arm64_darwin():
        print("错误: ARM64 后端仅支持在 Apple Silicon macOS 本机构建和运行。", file=sys.stderr)
        raise SystemExit(1)

    if verbose:
        print("=" * 50)
        print("ARM64 汇编" if artifact.backend == "arm64" else "LLVM IR")
        print("=" * 50)
        print(artifact.text)
        print(f"Backend: {artifact.backend}")

    with tempfile.NamedTemporaryFile(mode="w", suffix=artifact.extension, delete=False) as f:
        f.write(artifact.text)
        code_path = f.name

    try:
        cmd = ["clang", runtime_source_path(), code_path, "-o", output_path]
        if verbose:
            print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"clang 编译失败:\n{result.stderr}", file=sys.stderr)
            raise SystemExit(1)
    finally:
        os.unlink(code_path)

    return output_path


def default_output_name(source_path: str) -> str:
    return os.path.splitext(os.path.basename(source_path))[0]
