#!/usr/bin/env python3
"""NekoLang compiler CLI."""

import argparse
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass

from neko.ast_nodes import ProgramNode, dump_ast
from neko.codegen_llvm import LLVMCodegen
from neko.errors import NekoError
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
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "runtime", "runtime.c")


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


def command_tokens(args: argparse.Namespace) -> int:
    result = compile_file(args.file)
    for tok in result.tokens:
        print(tok)
    return 0


def command_ast(args: argparse.Namespace) -> int:
    result = compile_file(args.file)
    print(dump_ast(result.ast))
    return 0


def command_symbols(args: argparse.Namespace) -> int:
    result = compile_file(args.file)
    print_semantic_errors(result.analyzer)
    print(result.analyzer.symbol_table.dump())
    return 1 if result.analyzer.errors else 0


def command_quads(args: argparse.Namespace) -> int:
    result = compile_file(args.file)
    print_semantic_errors(result.analyzer)
    print(result.analyzer.dump_quadruples())
    return 1 if result.analyzer.errors else 0


def command_all(args: argparse.Namespace) -> int:
    result = compile_file(args.file)

    print("=" * 50)
    print("词法分析结果 (Tokens)")
    print("=" * 50)
    for tok in result.tokens:
        print(tok)
    print()

    print("=" * 50)
    print("语法分析结果 (AST)")
    print("=" * 50)
    print(dump_ast(result.ast))

    print_semantic_errors(result.analyzer)

    print("=" * 50)
    print("符号表")
    print("=" * 50)
    print(result.analyzer.symbol_table.dump())
    print()

    print("=" * 50)
    print("四元式 (Quadruples)")
    print("=" * 50)
    print(result.analyzer.dump_quadruples())
    return 1 if result.analyzer.errors else 0


def command_check(args: argparse.Namespace) -> int:
    result = compile_file(args.file)
    if result.analyzer.errors:
        print_semantic_errors(result.analyzer)
        return 1
    print(f"检查通过: {args.file}")
    return 0


def command_llvm_ir(args: argparse.Namespace) -> int:
    result = compile_file(args.file)
    ensure_no_semantic_errors(result)
    print(generate_ir(result.ast))
    return 0


def command_build(args: argparse.Namespace) -> int:
    result = compile_file(args.file)
    ensure_no_semantic_errors(result)
    output = args.output or default_output_name(args.file)
    compile_to_executable(result.ast, output, verbose=args.verbose)
    print(f"编译成功: {output}")
    return 0


def command_run(args: argparse.Namespace) -> int:
    result = compile_file(args.file)
    ensure_no_semantic_errors(result)

    runtime_args = list(args.args or [])
    if runtime_args and runtime_args[0] == "--":
        runtime_args = runtime_args[1:]

    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, default_output_name(args.file))
        compile_to_executable(result.ast, output, verbose=args.verbose)
        proc = subprocess.run([output, *runtime_args], text=True)
        return proc.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NekoLang Compiler")
    sub = parser.add_subparsers(dest="command")

    for name, help_text in [
        ("check", "Check source file"),
        ("build", "Compile to executable"),
        ("run", "Compile and run"),
        ("llvm-ir", "Print LLVM IR"),
        ("ast", "Print AST"),
        ("tokens", "Print tokens"),
        ("symbols", "Print symbol table"),
        ("quads", "Print quadruples"),
        ("all", "Print every compilation stage"),
    ]:
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("file", help="Source file (.neko)")
        if name == "build":
            cmd.add_argument("-o", "--output", help="Output executable path")
            cmd.add_argument("--verbose", action="store_true", help="Print LLVM IR and clang command")
            cmd.set_defaults(func=command_build)
        elif name == "run":
            cmd.add_argument("--verbose", action="store_true", help="Print LLVM IR and clang command")
            cmd.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to the program")
            cmd.set_defaults(func=command_run)
        elif name == "llvm-ir":
            cmd.set_defaults(func=command_llvm_ir)
        elif name == "ast":
            cmd.set_defaults(func=command_ast)
        elif name == "tokens":
            cmd.set_defaults(func=command_tokens)
        elif name == "symbols":
            cmd.set_defaults(func=command_symbols)
        elif name == "quads":
            cmd.set_defaults(func=command_quads)
        elif name == "all":
            cmd.set_defaults(func=command_all)
        elif name == "check":
            cmd.set_defaults(func=command_check)

    return parser


def run_legacy(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="NekoLang Compiler")
    parser.add_argument("file", help="Source file (.neko)")
    parser.add_argument("--tokens", action="store_true", help="Print token stream")
    parser.add_argument("--ast", action="store_true", help="Print AST")
    parser.add_argument("--symbols", action="store_true", help="Print symbol table")
    parser.add_argument("--quads", action="store_true", help="Print quadruples (default)")
    parser.add_argument("--all", action="store_true", help="Print everything")
    parser.add_argument("--llvm-ir", action="store_true", help="Print LLVM IR")
    parser.add_argument("--compile", "-o", metavar="OUTPUT", help="Compile to executable")
    args = parser.parse_args(argv)

    result = compile_file(args.file)

    show_all = args.all
    show_tokens = args.tokens or show_all
    show_ast = args.ast or show_all
    show_symbols = args.symbols or show_all
    show_quads = args.quads or show_all or not (
        args.tokens or args.ast or args.symbols or args.llvm_ir or args.compile
    )

    if show_tokens:
        print("=" * 50)
        print("词法分析结果 (Tokens)")
        print("=" * 50)
        for tok in result.tokens:
            print(tok)
        print()

    if show_ast:
        print("=" * 50)
        print("语法分析结果 (AST)")
        print("=" * 50)
        print(dump_ast(result.ast))
        print()

    if result.analyzer.errors:
        print_semantic_errors(result.analyzer)

    if show_symbols:
        print("=" * 50)
        print("符号表")
        print("=" * 50)
        print(result.analyzer.symbol_table.dump())
        print()

    if show_quads:
        print("=" * 50)
        print("四元式 (Quadruples)")
        print("=" * 50)
        print(result.analyzer.dump_quadruples())
        print()

    if args.llvm_ir or args.compile:
        ensure_no_semantic_errors(result)
        ir_text = generate_ir(result.ast)

        if args.llvm_ir:
            print("=" * 50)
            print("LLVM IR")
            print("=" * 50)
            print(ir_text)

        if args.compile:
            compile_to_executable(result.ast, args.compile, verbose=args.llvm_ir)
            print(f"编译成功: {args.compile}")

    return 1 if result.analyzer.errors else 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    commands = {"check", "build", "run", "llvm-ir", "ast", "tokens", "symbols", "quads", "all"}

    try:
        if argv and argv[0] in commands:
            parser = build_parser()
            args = parser.parse_args(argv)
            return args.func(args)
        return run_legacy(argv)
    except NekoError as e:
        print(e.format())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
