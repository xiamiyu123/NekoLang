"""Shared helpers for backend code generation tests."""

from __future__ import annotations

import atexit
import os
import platform
import shutil
import subprocess
import tempfile

from neko.build_utils import (
    compile_source,
    ensure_no_semantic_errors,
    generate_assembly,
    generate_code,
    generate_ir,
    runtime_source_path,
)

_RUNTIME_OBJECT_DIR = tempfile.mkdtemp(prefix="neko-runtime-objects-")
_RUNTIME_OBJECTS: dict[str, str] = {}


def _cleanup_runtime_objects() -> None:
    shutil.rmtree(_RUNTIME_OBJECT_DIR, ignore_errors=True)


atexit.register(_cleanup_runtime_objects)


def _is_arm64_darwin() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def _runtime_object_path() -> str:
    key = f"{platform.system()}-{platform.machine()}"
    cached = _RUNTIME_OBJECTS.get(key)
    if cached and os.path.exists(cached):
        return cached

    object_path = os.path.join(_RUNTIME_OBJECT_DIR, f"runtime-{key}.o")
    result = subprocess.run(
        ["clang", "-c", runtime_source_path(), "-o", object_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"clang 编译 runtime 失败:\n{result.stderr}")
        raise SystemExit(1)

    _RUNTIME_OBJECTS[key] = object_path
    return object_path


def _compile_to_test_executable(ast, output_path: str, backend: str = "llvm") -> str:
    artifact = generate_code(ast, backend=backend)

    if artifact.backend == "arm64" and not _is_arm64_darwin():
        print("错误: ARM64 后端仅支持在 Apple Silicon macOS 本机构建和运行。")
        raise SystemExit(1)

    with tempfile.NamedTemporaryFile(mode="w", suffix=artifact.extension, delete=False) as f:
        f.write(artifact.text)
        code_path = f.name

    try:
        result = subprocess.run(
            ["clang", _runtime_object_path(), code_path, "-o", output_path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"clang 编译失败:\n{result.stderr}")
            raise SystemExit(1)
    finally:
        os.unlink(code_path)

    return output_path


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
        _compile_to_test_executable(result.ast, out_path, backend=backend)
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
