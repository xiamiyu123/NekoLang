"""FastAPI HTTP API for NekoScope visualization tool.

Exposes the NekoLang compilation pipeline as JSON endpoints.
"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import tempfile

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from neko.build_utils import (
    CBuildConfig,
    compile_file_with_imports,
    compile_source,
    compile_to_executable,
    generate_code,
    resolve_c_build_config,
)
from neko.errors import NekoError
from neko.nekgo_cli import _load_toml_file
from neko.viz_serializers import (
    serialize_ast,
    serialize_compilation_result,
    serialize_errors,
    serialize_tokens,
)

app = FastAPI(title="NekoScope API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples")


# --- Request models ---


class CompileRequest(BaseModel):
    source: str
    backend: str = "auto"
    projectRoot: str | None = None
    sourcePath: str | None = None
    editedFiles: dict[str, str] | None = None


class SourceRequest(BaseModel):
    source: str


class AssemblyRequest(BaseModel):
    source: str
    backend: str = "auto"


class RunRequest(BaseModel):
    source: str
    backend: str = "auto"
    projectRoot: str | None = None
    sourcePath: str | None = None
    editedFiles: dict[str, str] | None = None


class WorkspaceOpenRequest(BaseModel):
    path: str


class WorkspaceFileRequest(BaseModel):
    rootPath: str
    filePath: str


# --- Helpers ---


def _run_pipeline(source: str):
    """Run the compilation pipeline, catching NekoError as structured errors."""
    try:
        return compile_source(source)
    except NekoError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _discover_examples() -> list[dict[str, str]]:
    """Scan examples/ directory for top-level .neko files."""
    examples = []
    if not os.path.isdir(EXAMPLES_DIR):
        return examples
    for f in sorted(os.listdir(EXAMPLES_DIR)):
        if f.endswith(".neko"):
            name = f[:-5]
            examples.append({"name": name, "description": name.replace("_", " ").title()})
    return examples


def _scan_directory(root_path: str) -> dict:
    """Recursively scan a directory for project files (.neko, .c, .h, Neko.toml)."""
    root_path = os.path.abspath(root_path)
    _SOURCE_EXTS = (".neko", ".c", ".h")

    def _scan(dir_path: str) -> list[dict]:
        entries: list[dict] = []
        try:
            names = sorted(os.listdir(dir_path))
        except PermissionError:
            return entries
        for name in names:
            full = os.path.join(dir_path, name)
            if name.startswith(".") or name == "build" or name == "__pycache__":
                continue
            rel = os.path.relpath(full, root_path)
            if os.path.isdir(full):
                children = _scan(full)
                entries.append({
                    "name": name,
                    "path": full,
                    "relativePath": rel,
                    "isDirectory": True,
                    "children": children,
                })
            elif name.endswith(_SOURCE_EXTS) or name == "Neko.toml":
                entries.append({
                    "name": name,
                    "path": full,
                    "relativePath": rel,
                    "isDirectory": False,
                })
        return entries

    tree = {
        "name": os.path.basename(root_path),
        "path": root_path,
        "relativePath": ".",
        "isDirectory": True,
        "children": _scan(root_path),
    }

    toml_path = os.path.join(root_path, "Neko.toml")
    project_name = os.path.basename(root_path)
    entry_file = None
    if os.path.isfile(toml_path):
        try:
            config = _load_toml_file(toml_path)
            if config and "project" in config:
                project = config["project"]
                project_name = project.get("name", project_name)
                entry_file = project.get("entry", None)
        except Exception:
            pass

    return {
        "rootPath": root_path,
        "projectName": project_name,
        "entryFile": entry_file,
        "tree": tree,
    }


def _compile_project_source(
    source: str,
    project_root: str,
    source_path: str,
    edited_files: dict[str, str] | None = None,
):
    """Compile source with import resolution, using a temp directory that
    mirrors the project structure so edited dependency files take priority
    over their on-disk versions."""
    project_root = os.path.abspath(project_root)
    source_path = os.path.abspath(source_path)
    edited_files = edited_files or {}

    tmp_dir = tempfile.mkdtemp()
    try:
        # Write all edited files into the temp tree, preserving relative paths
        rel_entry = os.path.relpath(source_path, project_root)
        for rel_path, content in {**edited_files, rel_entry: source}.items():
            tmp_path = os.path.join(tmp_dir, rel_path)
            os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)

        tmp_entry = os.path.join(tmp_dir, rel_entry)
        return compile_file_with_imports(
            tmp_entry,
            import_roots=[tmp_dir, os.path.dirname(source_path), project_root],
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# --- Endpoints ---


@app.get("/")
def root():
    return {"name": "NekoScope API", "version": "0.1.0", "endpoints": [
        "POST /api/compile", "POST /api/tokens", "POST /api/ast",
        "POST /api/assembly", "POST /api/run", "GET /api/examples",
        "GET /api/examples/{name}",
        "POST /api/workspace/open", "POST /api/workspace/file",
    ]}


@app.post("/api/compile")
def api_compile(req: CompileRequest):
    if req.sourcePath and req.projectRoot:
        try:
            result = _compile_project_source(
                req.source, req.projectRoot, req.sourcePath, req.editedFiles
            )
        except NekoError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except SystemExit as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        result = _run_pipeline(req.source)
    return serialize_compilation_result(result, backend=req.backend)


@app.post("/api/tokens")
def api_tokens(req: SourceRequest):
    result = _run_pipeline(req.source)
    return {"tokens": serialize_tokens(result.tokens)}


@app.post("/api/ast")
def api_ast(req: SourceRequest):
    result = _run_pipeline(req.source)
    return {"ast": serialize_ast(result.ast)}


@app.post("/api/assembly")
def api_assembly(req: AssemblyRequest):
    result = _run_pipeline(req.source)
    if result.analyzer.errors:
        return {
            "assembly": "",
            "errors": serialize_errors(result.analyzer.errors),
        }
    artifact = generate_code(result.ast, backend=req.backend)
    return {"assembly": artifact.text}


def _nekoscope_runs_dir() -> str:
    """Ensure ~/.nekoscope/runs/ exists and return its path."""
    runs_dir = os.path.join(os.path.expanduser("~"), ".nekoscope", "runs")
    os.makedirs(runs_dir, exist_ok=True)
    return runs_dir


@app.post("/api/run")
def api_run(req: RunRequest):
    if req.sourcePath and req.projectRoot:
        try:
            result = _compile_project_source(
                req.source, req.projectRoot, req.sourcePath, req.editedFiles
            )
        except NekoError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except SystemExit as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        result = _run_pipeline(req.source)
    if result.analyzer.errors:
        return {
            "executablePath": "",
            "errors": serialize_errors(result.analyzer.errors),
            "compileError": "",
        }

    # Resolve C build config from Neko.toml when running a project
    c_build_config = CBuildConfig()
    if req.projectRoot:
        toml_path = os.path.join(req.projectRoot, "Neko.toml")
        if os.path.isfile(toml_path):
            try:
                toml_config = _load_toml_file(toml_path)
                c_build_config = resolve_c_build_config(req.projectRoot, toml_config.get("c"))
            except Exception:
                pass

    # Compile to a persistent location so the terminal can run it
    runs_dir = _nekoscope_runs_dir()
    # Clean old executables
    for old in os.listdir(runs_dir):
        try:
            os.unlink(os.path.join(runs_dir, old))
        except Exception:
            pass

    output = os.path.join(runs_dir, "nekoscope-run")
    compile_stderr = io.StringIO()
    try:
        with contextlib.redirect_stderr(compile_stderr):
            compile_to_executable(result.ast, output, backend=req.backend, c_build_config=c_build_config)
    except SystemExit:
        return {
            "executablePath": "",
            "errors": [],
            "compileError": compile_stderr.getvalue(),
        }

    return {
        "executablePath": output,
        "errors": [],
        "compileError": "",
    }


@app.get("/api/examples")
def api_examples():
    return {"examples": _discover_examples()}


@app.get("/api/examples/{name}")
def api_example(name: str):
    path = os.path.join(EXAMPLES_DIR, f"{name}.neko")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"Example '{name}' not found")
    with open(path, "r", encoding="utf-8") as f:
        return {"source": f.read()}


@app.post("/api/workspace/open")
def api_workspace_open(req: WorkspaceOpenRequest):
    path = os.path.abspath(req.path)
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"Not a directory: {path}")
    return _scan_directory(path)


@app.post("/api/workspace/file")
def api_workspace_file(req: WorkspaceFileRequest):
    file_path = os.path.abspath(req.filePath)
    root_real = os.path.realpath(req.rootPath)
    file_real = os.path.realpath(file_path)
    if not file_real.startswith(root_real + os.sep) and file_real != root_real:
        raise HTTPException(status_code=403, detail="File is outside workspace root")
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return {
            "source": f.read(),
            "path": file_path,
            "relativePath": os.path.relpath(file_path, req.rootPath),
        }
