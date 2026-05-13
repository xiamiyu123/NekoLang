"""NekoLang compiler CLI."""

import argparse
import os
import subprocess
import sys
import tempfile

from neko.ast_nodes import dump_ast
from neko.build_utils import (
    CompilationResult,
    compile_file_with_imports,
    compile_to_executable,
    default_output_name,
    ensure_no_semantic_errors,
    generate_assembly,
    generate_ir,
    print_semantic_errors,
)
from neko.errors import NekoError


def command_tokens(args: argparse.Namespace) -> int:
    result = compile_file_with_imports(args.file)
    for tok in result.tokens:
        print(tok)
    return 0


def command_ast(args: argparse.Namespace) -> int:
    result = compile_file_with_imports(args.file)
    print(dump_ast(result.ast))
    return 0


def command_symbols(args: argparse.Namespace) -> int:
    result = compile_file_with_imports(args.file)
    print_semantic_errors(result.analyzer)
    print(result.analyzer.symbol_table.dump())
    return 1 if result.analyzer.errors else 0


def command_quads(args: argparse.Namespace) -> int:
    result = compile_file_with_imports(args.file)
    print_semantic_errors(result.analyzer)
    print(result.analyzer.dump_quadruples())
    return 1 if result.analyzer.errors else 0


def command_all(args: argparse.Namespace) -> int:
    result = compile_file_with_imports(args.file)

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
    result = compile_file_with_imports(args.file)
    if result.analyzer.errors:
        print_semantic_errors(result.analyzer)
        return 1
    print(f"检查通过: {args.file}")
    return 0


def command_llvm_ir(args: argparse.Namespace) -> int:
    result = compile_file_with_imports(args.file)
    ensure_no_semantic_errors(result)
    print(generate_ir(result.ast))
    return 0


def command_asm(args: argparse.Namespace) -> int:
    result = compile_file_with_imports(args.file)
    ensure_no_semantic_errors(result)
    print(generate_assembly(result.ast))
    return 0


def command_build(args: argparse.Namespace) -> int:
    result = compile_file_with_imports(args.file)
    ensure_no_semantic_errors(result)
    output = args.output or default_output_name(args.file)
    compile_to_executable(result.ast, output, backend=args.backend, verbose=args.verbose, mode=args.mode)
    print(f"编译成功: {output}")
    return 0


def command_run(args: argparse.Namespace) -> int:
    result = compile_file_with_imports(args.file)
    ensure_no_semantic_errors(result)

    runtime_args = list(args.args or [])
    if runtime_args and runtime_args[0] == "--":
        runtime_args = runtime_args[1:]

    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, default_output_name(args.file))
        compile_to_executable(result.ast, output, backend=args.backend, verbose=args.verbose, mode=args.mode)
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
        ("asm", "Print ARM64 assembly"),
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
            cmd.add_argument("--backend", choices=["auto", "llvm", "arm64"], default="auto", help="Codegen backend")
            cmd.add_argument("--mode", choices=["debug", "release"], default="debug", help="Compilation mode")
            cmd.set_defaults(func=command_build)
        elif name == "run":
            cmd.add_argument("--verbose", action="store_true", help="Print LLVM IR and clang command")
            cmd.add_argument("--backend", choices=["auto", "llvm", "arm64"], default="auto", help="Codegen backend")
            cmd.add_argument("--mode", choices=["debug", "release"], default="debug", help="Compilation mode")
            cmd.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to the program")
            cmd.set_defaults(func=command_run)
        elif name == "llvm-ir":
            cmd.set_defaults(func=command_llvm_ir)
        elif name == "asm":
            cmd.set_defaults(func=command_asm)
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

    result = compile_file_with_imports(args.file)

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
    commands = {"check", "build", "run", "llvm-ir", "asm", "ast", "tokens", "symbols", "quads", "all"}

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
