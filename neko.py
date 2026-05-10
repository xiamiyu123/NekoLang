#!/usr/bin/env python3
"""NekoLang Compiler - A Scheme-like language with standard keywords."""

import sys
import os
import argparse
import subprocess
import tempfile

from neko.lexer import Lexer
from neko.parser import Parser
from neko.semantic import SemanticAnalyzer
from neko.codegen_llvm import LLVMCodegen
from neko.ast_nodes import dump_ast
from neko.errors import NekoError


def compile_to_executable(ast, output_path: str, verbose: bool = False):
    """Compile AST to executable via LLVM IR + clang."""
    # Generate LLVM IR
    codegen = LLVMCodegen()
    ir_text = codegen.generate(ast)

    if verbose:
        print("=" * 50)
        print("LLVM IR")
        print("=" * 50)
        print(ir_text)

    # Find runtime.c relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    runtime_c = os.path.join(script_dir, "runtime", "runtime.c")

    # Write IR to temp .ll file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ll", delete=False) as f:
        f.write(ir_text)
        ll_path = f.name

    try:
        # Compile with clang: runtime.c + .ll -> executable
        cmd = ["clang", runtime_c, ll_path, "-o", output_path]
        if verbose:
            print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"clang 编译失败:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)
    finally:
        os.unlink(ll_path)


def main():
    ap = argparse.ArgumentParser(description="NekoLang Compiler")
    ap.add_argument("file", help="Source file (.neko)")
    ap.add_argument("--tokens", action="store_true", help="Print token stream")
    ap.add_argument("--ast", action="store_true", help="Print AST")
    ap.add_argument("--symbols", action="store_true", help="Print symbol table")
    ap.add_argument("--quads", action="store_true", help="Print quadruples (default)")
    ap.add_argument("--all", action="store_true", help="Print everything")
    ap.add_argument("--llvm-ir", action="store_true", help="Print LLVM IR")
    ap.add_argument("--compile", "-o", metavar="OUTPUT", help="Compile to executable")
    args = ap.parse_args()

    try:
        with open(args.file, "r", encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        print(f"错误: 文件 '{args.file}' 未找到")
        sys.exit(1)

    show_all = args.all
    show_tokens = args.tokens or show_all
    show_ast = args.ast or show_all
    show_symbols = args.symbols or show_all
    show_quads = args.quads or show_all or not (
        args.tokens or args.ast or args.symbols or args.llvm_ir or args.compile
    )

    try:
        # Phase 1: Lexical Analysis
        lexer = Lexer(source)
        tokens = lexer.tokenize()

        if show_tokens:
            print("=" * 50)
            print("词法分析结果 (Tokens)")
            print("=" * 50)
            for tok in tokens:
                print(tok)
            print()

        # Phase 2: Syntax Analysis
        parser = Parser(tokens)
        parser.set_source(source)
        ast = parser.parse()

        if show_ast:
            print("=" * 50)
            print("语法分析结果 (AST)")
            print("=" * 50)
            print(dump_ast(ast))
            print()

        # Phase 3 & 4: Semantic Analysis + Quadruple Generation
        analyzer = SemanticAnalyzer()
        analyzer.set_source(source)
        quadruples = analyzer.analyze(ast)

        if analyzer.errors:
            print("=" * 50)
            print("语义错误")
            print("=" * 50)
            for err in analyzer.errors:
                print(err.format())
                print()

        if show_symbols:
            print("=" * 50)
            print("符号表")
            print("=" * 50)
            print(analyzer.symbol_table.dump())
            print()

        if show_quads:
            print("=" * 50)
            print("四元式 (Quadruples)")
            print("=" * 50)
            print(analyzer.dump_quadruples())
            print()

        # Phase 5: LLVM IR generation
        if args.llvm_ir or args.compile:
            codegen = LLVMCodegen()
            ir_text = codegen.generate(ast)

            if args.llvm_ir:
                print("=" * 50)
                print("LLVM IR")
                print("=" * 50)
                print(ir_text)

            if args.compile:
                compile_to_executable(ast, args.compile, verbose=args.llvm_ir)
                print(f"编译成功: {args.compile}")

    except NekoError as e:
        print(e.format())
        sys.exit(1)


if __name__ == "__main__":
    main()
