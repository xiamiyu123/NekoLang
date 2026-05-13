"""FastAPI HTTP API for NekoScope visualization tool.

Exposes the NekoLang compilation pipeline as JSON endpoints.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from neko.build_utils import compile_source, generate_code
from neko.errors import NekoError
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


class SourceRequest(BaseModel):
    source: str


class AssemblyRequest(BaseModel):
    source: str
    backend: str = "auto"


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


# --- Endpoints ---


@app.get("/")
def root():
    return {"name": "NekoScope API", "version": "0.1.0", "endpoints": [
        "POST /api/compile", "POST /api/tokens", "POST /api/ast",
        "POST /api/assembly", "GET /api/examples", "GET /api/examples/{name}",
    ]}


@app.post("/api/compile")
def api_compile(req: CompileRequest):
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
