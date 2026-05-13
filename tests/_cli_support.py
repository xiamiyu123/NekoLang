"""Helpers for invoking CLI entrypoints in-process during tests."""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from types import ModuleType


@contextlib.contextmanager
def _working_directory(path: str):
    old_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_cwd)


def run_cli_main(
    main: Callable[[list[str] | None], int],
    args: Sequence[str],
    cwd: str,
    subprocess_module: ModuleType | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a CLI main function while capturing output like subprocess.run would."""
    stdout = io.StringIO()
    stderr = io.StringIO()
    argv = list(args)
    real_run = subprocess.run
    original_run = None

    def capturing_run(*popenargs, **kwargs):
        should_capture = not kwargs.get("capture_output") and "stdout" not in kwargs and "stderr" not in kwargs
        if should_capture:
            kwargs = dict(kwargs)
            kwargs["capture_output"] = True
            kwargs.setdefault("text", True)

        proc = real_run(*popenargs, **kwargs)
        if should_capture:
            if proc.stdout:
                print(proc.stdout, end="")
            if proc.stderr:
                print(proc.stderr, end="", file=sys.stderr)
        return proc

    with _working_directory(cwd), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        if subprocess_module is not None:
            original_run = subprocess_module.run
            subprocess_module.run = capturing_run
        try:
            try:
                returncode = main(argv)
            except SystemExit as exc:
                returncode = exc.code if isinstance(exc.code, int) else 1
        finally:
            if subprocess_module is not None and original_run is not None:
                subprocess_module.run = original_run

    return subprocess.CompletedProcess(argv, returncode, stdout.getvalue(), stderr.getvalue())
