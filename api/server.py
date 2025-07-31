#!/usr/bin/env python3
"""
REST API server for Tree-sitter Chunker.

Provides a simple HTTP API for code chunking that can be called from any language.

Usage:
    python api/server.py
    
    # Or with uvicorn directly:
    uvicorn api.server:app --reload
"""

from typing import List, Optional
from pathlib import Path
import tempfile

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import the simplified chunker API
from chunker import chunk_file, chunk_text, list_languages, __version__

# Create FastAPI app
app = FastAPI(
    title="Tree-sitter Chunker API",
    description="HTTP API for semantic code chunking using Tree-sitter",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class ChunkRequest(BaseModel):
    """Request model for chunking text."""
    content: str = Field(..., description="Source code content to chunk")
    language: str = Field(..., description="Programming language (e.g., 'python', 'javascript')")
    min_chunk_size: Optional[int] = Field(None, description="Minimum chunk size in lines")
    max_chunk_size: Optional[int] = Field(None, description="Maximum chunk size in lines")
    chunk_types: Optional[List[str]] = Field(None, description="Filter by chunk types")


class ChunkFileRequest(BaseModel):
    """Request model for chunking a file."""
    file_path: str = Field(..., description="Path to the file to chunk")
    language: Optional[str] = Field(None, description="Programming language (auto-detect if not specified)")
    min_chunk_size: Optional[int] = Field(None, description="Minimum chunk size in lines")
    max_chunk_size: Optional[int] = Field(None, description="Maximum chunk size in lines")
    chunk_types: Optional[List[str]] = Field(None, description="Filter by chunk types")


class ChunkResponse(BaseModel):
    """Response model for a code chunk."""
    node_type: str = Field(..., description="Type of code node (e.g., 'function_definition')")
    start_line: int = Field(..., description="Starting line number")
    end_line: int = Field(..., description="Ending line number")
    content: str = Field(..., description="Chunk content")
    parent_context: Optional[str] = Field(None, description="Parent context (e.g., class name)")
    size: int = Field(..., description="Size in lines")


class ChunkResult(BaseModel):
    """Result of chunking operation."""
    chunks: List[ChunkResponse]
    total_chunks: int
    language: str


class LanguageInfo(BaseModel):
    """Information about a supported language."""
    name: str
    extensions: List[str]
    chunk_types: List[str]


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
            "health": "/health"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": __version__}


@app.get("/languages", response_model=List[str])
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
                
            filtered_chunks.append(ChunkResponse(
                node_type=chunk.node_type,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                content=chunk.content,
                parent_context=chunk.parent_context,
                size=chunk_size
            ))
        
        return ChunkResult(
            chunks=filtered_chunks,
            total_chunks=len(filtered_chunks),
            language=request.language
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/chunk/file", response_model=ChunkResult)
async def chunk_file_endpoint(request: ChunkFileRequest):
    """
    Chunk a source code file.
    
    This endpoint chunks a file from the filesystem.
    """
    file_path = Path(request.file_path)
    
    # Check if file exists
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")
    
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail=f"Not a file: {request.file_path}")
    
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
                detail=f"Cannot auto-detect language for {file_path.suffix}. Please specify --language"
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
                
            filtered_chunks.append(ChunkResponse(
                node_type=chunk.node_type,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                content=chunk.content,
                parent_context=chunk.parent_context,
                size=chunk_size
            ))
        
        return ChunkResult(
            chunks=filtered_chunks,
            total_chunks=len(filtered_chunks),
            language=language
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Main entry point
if __name__ == "__main__":
    import uvicorn
    
    # Run the server
    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )