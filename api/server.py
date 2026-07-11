#!/usr/bin/env python3
"""
REST API server for Tree-sitter Chunker.

Provides a simple HTTP API for code chunking that can be called
from any language.

Usage:
    python api/server.py

    # Or with uvicorn directly:
    uvicorn api.server:app --reload
"""

import os
import secrets
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import the simplified chunker API
from chunker import __version__, chunk_file, chunk_text, list_languages
from chunker.graph.cut import graph_cut
from chunker.graph.xref import build_xref
from chunker._internal.path_confinement import resolve_within_root

DEFAULT_HOST = "127.0.0.1"
MAX_REQUEST_BODY_BYTES = 1_048_576
_bearer_scheme = HTTPBearer(auto_error=False)
_api_token_security = Security(_bearer_scheme)


def _cors_origins() -> list[str]:
    return [
        origin.strip()
        for origin in os.environ.get("TREE_SITTER_CHUNKER_API_CORS_ORIGINS", "").split(
            ",",
        )
        if origin.strip() and origin.strip() != "*"
    ]


def _api_root() -> Path:
    return Path(
        os.environ.get("TREE_SITTER_CHUNKER_API_ROOT", str(Path.cwd())),
    ).resolve()


def _resolve_api_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        raise HTTPException(status_code=400, detail="Absolute paths are not allowed")
    try:
        return resolve_within_root(candidate, _api_root())
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="Path is outside the API root"
        ) from exc


def require_api_token(
    credentials: HTTPAuthorizationCredentials | None = _api_token_security,
) -> None:
    """Require the configured bearer token for filesystem-backed operations."""
    expected_token = os.environ.get("TREE_SITTER_CHUNKER_API_TOKEN")
    if (
        not expected_token
        or credentials is None
        or not secrets.compare_digest(
            credentials.credentials.encode("utf-8"),
            expected_token.encode("utf-8"),
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Create FastAPI app
app = FastAPI(
    title="Tree-sitter Chunker API",
    description=("HTTP API for semantic code chunking using Tree-sitter"),
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def reject_oversized_requests(request: Request, call_next: Any):
    """Reject oversized requests before model parsing allocates their bodies."""
    content_length = request.headers.get("content-length")
    try:
        declared_length = int(content_length) if content_length is not None else 0
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid Content-Length header"},
        )
    if declared_length > MAX_REQUEST_BODY_BYTES:
        return JSONResponse(
            status_code=413,
            content={"detail": "Request body exceeds the configured limit"},
        )
    # Do not trust Content-Length: read the actual body and enforce the cap on
    # its real size (chunked / omitted-length requests would otherwise bypass it).
    body = await request.body()
    if len(body) > MAX_REQUEST_BODY_BYTES:
        return JSONResponse(
            status_code=413,
            content={"detail": "Request body exceeds the configured limit"},
        )
    return await call_next(request)


# Request/Response models
class ChunkRequest(BaseModel):
    """Request model for chunking text."""

    content: str = Field(..., description="Source code content to chunk")
    language: str = Field(
        ...,
        description=("Programming language (e.g., 'python', 'javascript')"),
    )
    min_chunk_size: int | None = Field(
        None,
        description="Minimum chunk size in lines",
    )
    max_chunk_size: int | None = Field(
        None,
        description="Maximum chunk size in lines",
    )
    chunk_types: list[str] | None = Field(
        None,
        description="Filter by chunk types",
    )


class ChunkFileRequest(BaseModel):
    """Request model for chunking a file."""

    file_path: str = Field(..., description="Path to the file to chunk")
    language: str | None = Field(
        None,
        description="Programming language (auto-detect if not specified)",
    )
    min_chunk_size: int | None = Field(
        None,
        description="Minimum chunk size in lines",
    )
    max_chunk_size: int | None = Field(
        None,
        description="Maximum chunk size in lines",
    )
    chunk_types: list[str] | None = Field(
        None,
        description="Filter by chunk types",
    )


class ChunkResponse(BaseModel):
    """Response model for a code chunk."""

    node_type: str = Field(
        ...,
        description="Type of code node (e.g., 'function_definition')",
    )
    start_line: int = Field(..., description="Starting line number")
    end_line: int = Field(..., description="Ending line number")
    content: str = Field(..., description="Chunk content")
    parent_context: str | None = Field(
        None,
        description="Parent context (e.g., class name)",
    )
    size: int = Field(..., description="Size in lines")


class ChunkResult(BaseModel):
    """Result of chunking operation."""

    chunks: list[ChunkResponse]
    total_chunks: int
    language: str


class LanguageInfo(BaseModel):
    """Information about a supported language."""

    name: str
    extensions: list[str]
    chunk_types: list[str]


# New models for extended API
class ExportPostgresRequest(BaseModel):
    repo_root: str
    config: dict[str, Any] | None = None


class ExportPostgresResponse(BaseModel):
    rows_written: int


class GraphXrefRequest(BaseModel):
    paths: list[str]


class GraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class GraphCutParams(BaseModel):
    radius: int | None = 2
    budget: int | None = 200
    weights: dict[str, float] | None = None


class GraphCutRequest(BaseModel):
    seeds: list[str]
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    params: GraphCutParams | None = None


class GraphCutResponse(BaseModel):
    nodes: list[str]
    edges: list[dict[str, Any]]


class NearestTestsRequest(BaseModel):
    symbols: list[str]


class NearestTestsResponse(BaseModel):
    tests: list[dict[str, Any]]


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Tree-sitter Chunker API",
        "version": __version__,
        "docs": "/docs",
        "endpoints": {
            "chunk_text": "/chunk/text",
            "chunk_file": "/chunk/file",
            "languages": "/languages",
            "health": "/health",
            "export_postgres": "/export/postgres",
            "graph_xref": "/graph/xref",
            "graph_cut": "/graph/cut",
            "nearest_tests": "/nearest-tests",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": __version__}


@app.get("/languages", response_model=list[str])
async def get_languages():
    """Get list of supported languages."""
    return list_languages()


@app.post("/chunk/text", response_model=ChunkResult)
async def chunk_text_endpoint(request: ChunkRequest):
    """
    Chunk source code text.

    This endpoint accepts raw source code and returns semantic chunks.
    """
    try:
        # Chunk the text
        chunks = chunk_text(request.content, request.language)

        # Apply filters
        filtered_chunks = []
        for chunk in chunks:
            chunk_size = chunk.end_line - chunk.start_line + 1

            # Apply size filters
            if request.min_chunk_size and chunk_size < request.min_chunk_size:
                continue
            if request.max_chunk_size and chunk_size > request.max_chunk_size:
                continue

            # Apply type filter
            if request.chunk_types and chunk.node_type not in request.chunk_types:
                continue

            filtered_chunks.append(
                ChunkResponse(
                    node_type=chunk.node_type,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    content=chunk.content,
                    parent_context=chunk.parent_context,
                    size=chunk_size,
                ),
            )

        return ChunkResult(
            chunks=filtered_chunks,
            total_chunks=len(filtered_chunks),
            language=request.language,
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/chunk/file", response_model=ChunkResult)
async def chunk_file_endpoint(
    request: ChunkFileRequest,
    _: None = Depends(require_api_token),
):
    """
    Chunk a source code file.

    This endpoint chunks a file from the filesystem.
    """
    file_path = _resolve_api_path(request.file_path)

    # Check if file exists
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {request.file_path}",
        )

    if not file_path.is_file():
        raise HTTPException(
            status_code=400,
            detail=f"Not a file: {request.file_path}",
        )

    # Auto-detect language if not provided
    language = request.language
    if not language:
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".rs": "rust",
            ".go": "go",
            ".rb": "ruby",
            ".php": "php",
            ".cs": "csharp",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".r": "r",
            ".jl": "julia",
            ".lua": "lua",
            ".dart": "dart",
            ".hs": "haskell",
            ".clj": "clojure",
            ".ex": "elixir",
            ".elm": "elm",
            ".ml": "ocaml",
            ".vim": "vim",
            ".sh": "bash",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".xml": "xml",
            ".html": "html",
            ".css": "css",
            ".sql": "sql",
            ".dockerfile": "dockerfile",
            ".Dockerfile": "dockerfile",
        }
        language = ext_map.get(file_path.suffix.lower())

        if not language:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot auto-detect language for {file_path.suffix}. "
                    "Please specify --language"
                ),
            )

    try:
        # Chunk the file
        chunks = chunk_file(str(file_path), language)

        # Apply filters
        filtered_chunks = []
        for chunk in chunks:
            chunk_size = chunk.end_line - chunk.start_line + 1

            # Apply size filters
            if request.min_chunk_size and chunk_size < request.min_chunk_size:
                continue
            if request.max_chunk_size and chunk_size > request.max_chunk_size:
                continue

            # Apply type filter
            if request.chunk_types and chunk.node_type not in request.chunk_types:
                continue

            filtered_chunks.append(
                ChunkResponse(
                    node_type=chunk.node_type,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    content=chunk.content,
                    parent_context=chunk.parent_context,
                    size=chunk_size,
                ),
            )

        return ChunkResult(
            chunks=filtered_chunks,
            total_chunks=len(filtered_chunks),
            language=language,
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# New endpoints per spec (implemented)
@app.post("/export/postgres", response_model=ExportPostgresResponse)
async def export_postgres_endpoint(
    request: ExportPostgresRequest,
    _: None = Depends(require_api_token),
):
    try:
        from chunker.export.postgres_spec_exporter import export as pg_export

        rows_written = pg_export(
            str(_resolve_api_path(request.repo_root)), request.config or {}
        )
        return ExportPostgresResponse(rows_written=rows_written)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/graph/xref", response_model=GraphResponse)
async def graph_xref_endpoint(
    request: GraphXrefRequest,
    _: None = Depends(require_api_token),
):
    paths = [_resolve_api_path(path) for path in request.paths]
    chunks = []
    for p in paths:
        if p.exists() and p.is_file():
            # naive language detection from extension
            ext = p.suffix.lower()
            lang_map = {
                ".py": "python",
                ".js": "javascript",
                ".ts": "typescript",
                ".java": "java",
                ".go": "go",
                ".rs": "rust",
            }
            language = lang_map.get(ext, "python")
            chunks.extend(chunk_file(str(p), language))
    nodes, edges = build_xref(chunks)
    return GraphResponse(nodes=nodes, edges=edges)


@app.post("/graph/cut", response_model=GraphCutResponse)
async def graph_cut_endpoint(request: GraphCutRequest):
    try:
        params = request.params or GraphCutParams()
        selected, induced = graph_cut(
            request.seeds,
            request.nodes,
            request.edges,
            radius=params.radius or 2,
            budget=params.budget or 200,
            weights=params.weights or {},
        )
        return GraphCutResponse(nodes=selected, edges=induced)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/nearest-tests", response_model=NearestTestsResponse)
async def nearest_tests_endpoint(
    request: NearestTestsRequest,
    _: None = Depends(require_api_token),
):
    try:
        from chunker.helpers.nearest_tests import nearest_tests

        # Confine the walk root to the configured API root so this endpoint
        # cannot enumerate / read arbitrary files (APISAFE hardening).
        root = _resolve_api_path(str(Path()))
        tests = nearest_tests(request.symbols, str(root))
        return NearestTestsResponse(tests=tests)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# Main entry point
if __name__ == "__main__":
    import uvicorn

    # Run the server
    uvicorn.run(app, host=DEFAULT_HOST, port=8000)
