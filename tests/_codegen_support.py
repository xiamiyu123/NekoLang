"""Shared helpers for backend code generation tests."""

from __future__ import annotations

import os
import subprocess
import tempfile

from neko.build_utils import (
    compile_source,
    compile_to_executable,
    ensure_no_semantic_errors,
    generate_assembly,
    generate_ir,
)


def compile_and_run_process(
    source: str,
    backend: str = "llvm",
    args: list[str] | None = None,
    stdin_data: str | None = None,
) -> subprocess.CompletedProcess:
    """Compile NekoLang source to executable, run it, return the process result."""
    result = compile_source(source)
    ensure_no_semantic_errors(result)

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "test_bin")
        compile_to_executable(result.ast, out_path, backend=backend)
        return subprocess.run(
            [out_path, *(args or [])],
            input=stdin_data,
            capture_output=True,
            text=True,
        )


def compile_and_run(source: str, backend: str = "llvm") -> str:
    return compile_and_run_process(source, backend=backend).stdout.strip()


def compile_and_run_with_args(source: str, args: list[str] | None = None, backend: str = "llvm") -> str:
    return compile_and_run_process(source, backend=backend, args=args).stdout.strip()


def compile_and_run_with_input(source: str, stdin_data: str, backend: str = "llvm") -> str:
    return compile_and_run_process(source, backend=backend, stdin_data=stdin_data).stdout.strip()


def generate_ir_text(source: str) -> str:
    result = compile_source(source)
    ensure_no_semantic_errors(result)
    return generate_ir(result.ast)


def generate_asm_text(source: str) -> str:
    result = compile_source(source)
    ensure_no_semantic_errors(result)
    return generate_assembly(result.ast)
