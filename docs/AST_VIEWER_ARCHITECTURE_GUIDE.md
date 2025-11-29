# Building an AST Viewer & Manipulation App with treesitter-chunker

A comprehensive guide for building a standalone AST (Abstract Syntax Tree) viewing and manipulation application using `treesitter-chunker` as the parsing backbone.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Dependencies](#core-dependencies)
4. [Project Structure](#project-structure)
5. [Backend Implementation](#backend-implementation)
6. [Frontend Implementation](#frontend-implementation)
7. [Key Features to Implement](#key-features-to-implement)
8. [Integration Examples](#integration-examples)
9. [Performance Considerations](#performance-considerations)
10. [Deployment](#deployment)

---

## Overview

### What You're Building

An **AST Viewer & Manipulation App** allows developers to:

- **Visualize** code as a tree structure showing syntax nodes
- **Navigate** through parent-child relationships in code
- **Edit** nodes and see real-time syntax changes
- **Analyze** code structure, complexity, and dependencies
- **Export** AST representations for further processing

### Why treesitter-chunker?

`treesitter-chunker` provides a robust foundation because it:

| Feature | Benefit for AST Viewer |
|---------|------------------------|
| 36+ built-in language plugins | Immediate multi-language support |
| Automatic grammar management | No manual tree-sitter setup |
| Stable node identification (SHA1-based) | Track nodes across edits |
| Hierarchical parent_route tracking | Natural tree navigation |
| Metadata extraction (complexity, calls, imports) | Rich node annotations |
| Incremental processing | Efficient live updates |
| Graph building utilities | Relationship visualization |

---

## Architecture

### Recommended Stack

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND                                       │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────────────────┐  │
│  │ Code Editor │   │  AST Tree    │   │  Properties Panel            │  │
│  │ (Monaco/CM) │   │  (D3/React   │   │  - Node type, position       │  │
│  │             │   │   Flow)      │   │  - Metadata, complexity      │  │
│  │ ↔ Sync      │←→│  ↔ Select    │←→│  - References, dependencies   │  │
│  └─────────────┘   └──────────────┘   └──────────────────────────────┘  │
│         │                  │                         │                   │
│         └──────────────────┼─────────────────────────┘                   │
│                            │                                             │
│                     WebSocket / REST                                     │
└────────────────────────────┼─────────────────────────────────────────────┘
                             │
┌────────────────────────────┼─────────────────────────────────────────────┐
│                       BACKEND (FastAPI)                                  │
│                            │                                             │
│  ┌─────────────────────────▼─────────────────────────────────────────┐  │
│  │                    AST Service Layer                              │  │
│  │  - Parse code → AST                                               │  │
│  │  - Traverse & serialize nodes                                     │  │
│  │  - Compute incremental diffs                                      │  │
│  │  - Build dependency graphs                                        │  │
│  └─────────────────────────┬─────────────────────────────────────────┘  │
│                            │                                             │
│  ┌─────────────────────────▼─────────────────────────────────────────┐  │
│  │               treesitter-chunker Core                             │  │
│  │  ┌───────────────┐  ┌────────────────┐  ┌───────────────────┐    │  │
│  │  │ get_parser()  │  │ chunk_text()   │  │ build_xref()      │    │  │
│  │  │ ParserFactory │  │ _walk()        │  │ graph_cut()       │    │  │
│  │  └───────────────┘  └────────────────┘  └───────────────────┘    │  │
│  │  ┌───────────────┐  ┌────────────────┐  ┌───────────────────┐    │  │
│  │  │ PluginManager │  │ Incremental    │  │ MetadataExtractor │    │  │
│  │  │ (36 langs)    │  │ Processor      │  │                   │    │  │
│  │  └───────────────┘  └────────────────┘  └───────────────────┘    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
User types code → Editor sends text → Backend parses with tree-sitter
                                              ↓
                                    AST nodes extracted via _walk()
                                              ↓
                                    Nodes enriched with metadata
                                              ↓
                                    JSON response to frontend
                                              ↓
                              Frontend renders tree + highlights editor
```

---

## Core Dependencies

### Python Backend

```toml
# pyproject.toml
[project]
name = "ast-viewer"
version = "0.1.0"
dependencies = [
    "treesitter-chunker>=2.0.1",  # Core parsing engine
    "fastapi>=0.100.0",            # API framework
    "uvicorn>=0.22.0",             # ASGI server
    "websockets>=11.0",            # Real-time updates
    "pydantic>=2.0",               # Data validation
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "httpx>=0.24.0",  # Async HTTP client for testing
]
```

### Frontend (React + TypeScript)

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "@monaco-editor/react": "^4.6.0",
    "reactflow": "^11.10.0",
    "d3": "^7.8.0",
    "@tanstack/react-query": "^5.0.0",
    "zustand": "^4.4.0"
  }
}
```

---

## Project Structure

```
ast-viewer/
├── backend/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── parse.py        # /parse endpoints
│   │   │   ├── analyze.py      # /analyze endpoints
│   │   │   └── languages.py    # /languages endpoints
│   │   └── websocket.py        # WebSocket handlers
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ast_service.py      # Core AST operations
│   │   ├── diff_service.py     # Incremental diffing
│   │   └── graph_service.py    # Dependency graphs
│   ├── models/
│   │   ├── __init__.py
│   │   ├── ast_node.py         # Pydantic models
│   │   └── requests.py         # API request models
│   └── utils/
│       └── serializers.py      # AST → JSON conversion
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── Editor/
│   │   │   │   ├── CodeEditor.tsx
│   │   │   │   └── LanguageSelector.tsx
│   │   │   ├── ASTTree/
│   │   │   │   ├── TreeView.tsx
│   │   │   │   ├── TreeNode.tsx
│   │   │   │   └── TreeControls.tsx
│   │   │   ├── Properties/
│   │   │   │   ├── PropertiesPanel.tsx
│   │   │   │   └── MetadataView.tsx
│   │   │   └── Graph/
│   │   │       ├── DependencyGraph.tsx
│   │   │       └── GraphControls.tsx
│   │   ├── hooks/
│   │   │   ├── useAST.ts
│   │   │   ├── useWebSocket.ts
│   │   │   └── useSelection.ts
│   │   ├── stores/
│   │   │   └── astStore.ts
│   │   └── types/
│   │       └── ast.ts
│   └── package.json
│
├── pyproject.toml
├── README.md
└── docker-compose.yml
```

---

## Backend Implementation

### 1. Core AST Service

This is the heart of your application - wrapping treesitter-chunker for AST operations:

```python
# backend/services/ast_service.py
from dataclasses import dataclass, field
from typing import Any

from chunker import get_parser, list_languages
from chunker.types import CodeChunk
from chunker.core import chunk_text
from chunker.metadata.extractor import BaseMetadataExtractor


@dataclass
class ASTNode:
    """Represents a single AST node for frontend consumption."""
    id: str
    type: str
    text: str
    start_byte: int
    end_byte: int
    start_point: tuple[int, int]  # (row, col)
    end_point: tuple[int, int]
    children: list["ASTNode"] = field(default_factory=list)
    is_named: bool = True
    field_name: str | None = None

    # Enriched data
    metadata: dict[str, Any] = field(default_factory=dict)


class ASTService:
    """Service for parsing and manipulating ASTs using treesitter-chunker."""

    def __init__(self):
        self._metadata_extractor = BaseMetadataExtractor()

    def parse_to_ast(
        self,
        source_code: str,
        language: str,
        include_anonymous: bool = False,
        max_depth: int | None = None,
    ) -> ASTNode:
        """
        Parse source code and return full AST as nested ASTNode structure.

        Args:
            source_code: The code to parse
            language: Language identifier (e.g., "python", "javascript")
            include_anonymous: Include non-named nodes (punctuation, etc.)
            max_depth: Maximum tree depth to return (None = unlimited)

        Returns:
            Root ASTNode with nested children
        """
        parser = get_parser(language)
        tree = parser.parse(source_code.encode("utf-8"))

        return self._node_to_ast(
            tree.root_node,
            source_code,
            include_anonymous=include_anonymous,
            max_depth=max_depth,
            current_depth=0,
        )

    def _node_to_ast(
        self,
        node,
        source: str,
        include_anonymous: bool,
        max_depth: int | None,
        current_depth: int,
        field_name: str | None = None,
    ) -> ASTNode:
        """Recursively convert tree-sitter node to ASTNode."""
        # Extract node text
        text = source[node.start_byte:node.end_byte]

        # Create node
        ast_node = ASTNode(
            id=f"{node.type}:{node.start_byte}:{node.end_byte}",
            type=node.type,
            text=text[:200] + "..." if len(text) > 200 else text,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            start_point=(node.start_point[0], node.start_point[1]),
            end_point=(node.end_point[0], node.end_point[1]),
            is_named=node.is_named,
            field_name=field_name,
        )

        # Check depth limit
        if max_depth is not None and current_depth >= max_depth:
            ast_node.metadata["truncated"] = True
            ast_node.metadata["child_count"] = node.child_count
            return ast_node

        # Process children
        children = node.children if include_anonymous else node.named_children

        for i, child in enumerate(children):
            # Get field name if available
            child_field = None
            for field_name_candidate in node.type.split("_"):
                if hasattr(node, f"{field_name_candidate}_node"):
                    child_field = field_name_candidate

            child_ast = self._node_to_ast(
                child,
                source,
                include_anonymous,
                max_depth,
                current_depth + 1,
                child_field,
            )
            ast_node.children.append(child_ast)

        return ast_node

    def get_chunks_with_metadata(
        self,
        source_code: str,
        language: str,
    ) -> list[CodeChunk]:
        """
        Get semantic chunks with full metadata using treesitter-chunker's
        built-in chunking.

        This gives you function/class level chunks with:
        - Complexity metrics
        - Call extraction
        - Import detection
        - Parent context
        """
        return chunk_text(source_code, language)

    def get_node_at_position(
        self,
        source_code: str,
        language: str,
        row: int,
        col: int,
    ) -> ASTNode | None:
        """Find the most specific node at a given position."""
        parser = get_parser(language)
        tree = parser.parse(source_code.encode("utf-8"))

        # Tree-sitter uses 0-indexed positions
        point = (row, col)

        def find_node(node):
            """Find smallest node containing the point."""
            if not (node.start_point <= point <= node.end_point):
                return None

            # Check children for more specific match
            for child in node.children:
                result = find_node(child)
                if result:
                    return result

            return node

        ts_node = find_node(tree.root_node)
        if ts_node:
            return self._node_to_ast(
                ts_node, source_code,
                include_anonymous=True,
                max_depth=0,
                current_depth=0
            )
        return None

    def get_supported_languages(self) -> list[dict[str, Any]]:
        """List all supported languages with their extensions."""
        languages = list_languages()
        return [
            {
                "name": lang,
                "available": True,
            }
            for lang in languages
        ]
```

### 2. Incremental Diff Service

For live editing with efficient updates:

```python
# backend/services/diff_service.py
from chunker.incremental import DefaultIncrementalProcessor
from chunker import chunk_text


class DiffService:
    """Tracks changes between AST versions for efficient updates."""

    def __init__(self):
        self._processor = DefaultIncrementalProcessor()
        self._cache: dict[str, list] = {}  # session_id -> chunks

    def compute_diff(
        self,
        session_id: str,
        source_code: str,
        language: str,
    ) -> dict:
        """
        Compute what changed between the current and previous AST.

        Returns:
            {
                "added": [chunk_ids],
                "removed": [chunk_ids],
                "modified": [chunk_ids],
                "unchanged": [chunk_ids],
            }
        """
        new_chunks = chunk_text(source_code, language)

        if session_id not in self._cache:
            # First parse - everything is "added"
            self._cache[session_id] = new_chunks
            return {
                "added": [c.chunk_id for c in new_chunks],
                "removed": [],
                "modified": [],
                "unchanged": [],
                "chunks": new_chunks,
            }

        old_chunks = self._cache[session_id]

        # Use treesitter-chunker's incremental processor
        self._processor.store_chunks(session_id, old_chunks)
        diff = self._processor.compute_diff(session_id, new_chunks)

        # Update cache
        self._cache[session_id] = new_chunks

        return {
            "added": [c.chunk_id for c in diff.added],
            "removed": [c.chunk_id for c in diff.removed],
            "modified": [c.chunk_id for c in diff.modified],
            "unchanged": [c.chunk_id for c in diff.unchanged],
            "chunks": new_chunks,
        }

    def clear_session(self, session_id: str):
        """Clear cached state for a session."""
        self._cache.pop(session_id, None)
```

### 3. Graph Service

For dependency and relationship visualization:

```python
# backend/services/graph_service.py
from chunker.graph.xref import build_xref
from chunker.graph.cut import graph_cut
from chunker import chunk_text


class GraphService:
    """Build and query code dependency graphs."""

    def build_dependency_graph(
        self,
        source_code: str,
        language: str,
    ) -> dict:
        """
        Build a cross-reference graph showing relationships between
        code elements.

        Returns:
            {
                "nodes": [{"id", "type", "name", "file", ...}],
                "edges": [{"source", "target", "type", "weight"}]
            }
        """
        chunks = chunk_text(source_code, language)
        nodes, edges = build_xref(chunks)

        return {
            "nodes": [
                {
                    "id": n["id"],
                    "type": n.get("kind", "unknown"),
                    "name": n.get("symbol", ""),
                    "language": n.get("lang", language),
                    "attributes": n.get("attrs", {}),
                }
                for n in nodes
            ],
            "edges": [
                {
                    "source": e["src"],
                    "target": e["dst"],
                    "type": e.get("type", "REFERENCES"),
                    "weight": e.get("weight", 1.0),
                }
                for e in edges
            ],
        }

    def get_related_nodes(
        self,
        source_code: str,
        language: str,
        seed_node_id: str,
        radius: int = 2,
        max_nodes: int = 50,
    ) -> dict:
        """
        Get nodes related to a specific node using graph cut.

        Useful for "find related code" features.
        """
        chunks = chunk_text(source_code, language)
        nodes, edges = build_xref(chunks)

        selected_ids, induced_edges = graph_cut(
            seeds=[seed_node_id],
            nodes=nodes,
            edges=edges,
            radius=radius,
            budget=max_nodes,
        )

        # Filter to selected nodes
        selected_nodes = [n for n in nodes if n["id"] in selected_ids]

        return {
            "nodes": selected_nodes,
            "edges": induced_edges,
            "seed_id": seed_node_id,
        }
```

### 4. FastAPI Application

Wire everything together:

```python
# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.services.ast_service import ASTService
from backend.services.diff_service import DiffService
from backend.services.graph_service import GraphService


# Services
ast_service = ASTService()
diff_service = DiffService()
graph_service = GraphService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: preload common languages
    from chunker import get_parser
    for lang in ["python", "javascript", "typescript", "rust", "go"]:
        try:
            get_parser(lang)
        except Exception:
            pass
    yield
    # Shutdown: cleanup


app = FastAPI(
    title="AST Viewer API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response Models ---

class ParseRequest(BaseModel):
    source_code: str
    language: str
    include_anonymous: bool = False
    max_depth: int | None = None


class ChunkRequest(BaseModel):
    source_code: str
    language: str


class PositionRequest(BaseModel):
    source_code: str
    language: str
    row: int
    col: int


class GraphRequest(BaseModel):
    source_code: str
    language: str
    seed_node_id: str | None = None
    radius: int = 2
    max_nodes: int = 50


# --- REST Endpoints ---

@app.get("/languages")
def get_languages():
    """List all supported languages."""
    return ast_service.get_supported_languages()


@app.post("/parse")
def parse_code(request: ParseRequest):
    """Parse code and return full AST."""
    ast = ast_service.parse_to_ast(
        request.source_code,
        request.language,
        include_anonymous=request.include_anonymous,
        max_depth=request.max_depth,
    )
    return {"ast": ast}


@app.post("/chunks")
def get_chunks(request: ChunkRequest):
    """Get semantic code chunks with metadata."""
    chunks = ast_service.get_chunks_with_metadata(
        request.source_code,
        request.language,
    )
    return {
        "chunks": [
            {
                "id": c.chunk_id,
                "node_type": c.node_type,
                "content": c.content,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "parent_context": c.parent_context,
                "parent_route": c.parent_route,
                "metadata": c.metadata,
            }
            for c in chunks
        ]
    }


@app.post("/node-at-position")
def get_node_at_position(request: PositionRequest):
    """Get the AST node at a specific cursor position."""
    node = ast_service.get_node_at_position(
        request.source_code,
        request.language,
        request.row,
        request.col,
    )
    return {"node": node}


@app.post("/graph")
def get_dependency_graph(request: GraphRequest):
    """Build dependency graph for the code."""
    if request.seed_node_id:
        return graph_service.get_related_nodes(
            request.source_code,
            request.language,
            request.seed_node_id,
            request.radius,
            request.max_nodes,
        )
    return graph_service.build_dependency_graph(
        request.source_code,
        request.language,
    )


# --- WebSocket for Live Updates ---

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)
        diff_service.clear_session(session_id)


manager = ConnectionManager()


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket for real-time AST updates.

    Client sends: {"source_code": "...", "language": "python"}
    Server sends: {"diff": {...}, "chunks": [...]}
    """
    await manager.connect(session_id, websocket)

    try:
        while True:
            data = await websocket.receive_json()

            source_code = data.get("source_code", "")
            language = data.get("language", "python")

            # Compute incremental diff
            diff_result = diff_service.compute_diff(
                session_id,
                source_code,
                language,
            )

            # Also get full AST for tree view
            ast = ast_service.parse_to_ast(
                source_code,
                language,
                include_anonymous=data.get("include_anonymous", False),
            )

            await websocket.send_json({
                "diff": {
                    "added": diff_result["added"],
                    "removed": diff_result["removed"],
                    "modified": diff_result["modified"],
                },
                "ast": ast.__dict__,
                "chunks": [
                    {
                        "id": c.chunk_id,
                        "node_type": c.node_type,
                        "start_line": c.start_line,
                        "end_line": c.end_line,
                        "parent_context": c.parent_context,
                    }
                    for c in diff_result["chunks"]
                ],
            })

    except WebSocketDisconnect:
        manager.disconnect(session_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## Frontend Implementation

### 1. TypeScript Types

```typescript
// frontend/src/types/ast.ts

export interface ASTNode {
  id: string;
  type: string;
  text: string;
  start_byte: number;
  end_byte: number;
  start_point: [number, number]; // [row, col]
  end_point: [number, number];
  children: ASTNode[];
  is_named: boolean;
  field_name: string | null;
  metadata: Record<string, unknown>;
}

export interface CodeChunk {
  id: string;
  node_type: string;
  content: string;
  start_line: number;
  end_line: number;
  parent_context: string;
  parent_route: string[];
  metadata: {
    token_count?: number;
    complexity?: {
      cyclomatic: number;
      cognitive: number;
    };
    calls?: string[];
    imports?: string[];
  };
}

export interface GraphNode {
  id: string;
  type: string;
  name: string;
  language: string;
  attributes: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: 'DEFINES' | 'IMPORTS' | 'CALLS' | 'INHERITS' | 'REFERENCES';
  weight: number;
}

export interface DiffResult {
  added: string[];
  removed: string[];
  modified: string[];
}
```

### 2. State Management (Zustand)

```typescript
// frontend/src/stores/astStore.ts

import { create } from 'zustand';
import type { ASTNode, CodeChunk, DiffResult } from '../types/ast';

interface ASTState {
  // Source code
  sourceCode: string;
  language: string;

  // AST data
  ast: ASTNode | null;
  chunks: CodeChunk[];

  // Selection
  selectedNodeId: string | null;
  hoveredNodeId: string | null;

  // Diff tracking
  lastDiff: DiffResult | null;

  // Actions
  setSourceCode: (code: string) => void;
  setLanguage: (lang: string) => void;
  setAST: (ast: ASTNode) => void;
  setChunks: (chunks: CodeChunk[]) => void;
  selectNode: (nodeId: string | null) => void;
  hoverNode: (nodeId: string | null) => void;
  setDiff: (diff: DiffResult) => void;
}

export const useASTStore = create<ASTState>((set) => ({
  sourceCode: '',
  language: 'python',
  ast: null,
  chunks: [],
  selectedNodeId: null,
  hoveredNodeId: null,
  lastDiff: null,

  setSourceCode: (code) => set({ sourceCode: code }),
  setLanguage: (lang) => set({ language: lang }),
  setAST: (ast) => set({ ast }),
  setChunks: (chunks) => set({ chunks }),
  selectNode: (nodeId) => set({ selectedNodeId: nodeId }),
  hoverNode: (nodeId) => set({ hoveredNodeId: nodeId }),
  setDiff: (diff) => set({ lastDiff: diff }),
}));
```

### 3. WebSocket Hook

```typescript
// frontend/src/hooks/useWebSocket.ts

import { useEffect, useRef, useCallback } from 'react';
import { useASTStore } from '../stores/astStore';
import { v4 as uuidv4 } from 'uuid';

export function useASTWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const sessionIdRef = useRef(uuidv4());

  const { setAST, setChunks, setDiff, sourceCode, language } = useASTStore();

  // Connect on mount
  useEffect(() => {
    const ws = new WebSocket(
      `ws://localhost:8000/ws/${sessionIdRef.current}`
    );

    ws.onopen = () => {
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.ast) {
        setAST(data.ast);
      }
      if (data.chunks) {
        setChunks(data.chunks);
      }
      if (data.diff) {
        setDiff(data.diff);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, [setAST, setChunks, setDiff]);

  // Send updates when code changes
  const sendUpdate = useCallback(
    (code: string, lang: string) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          source_code: code,
          language: lang,
          include_anonymous: false,
        }));
      }
    },
    []
  );

  return { sendUpdate };
}
```

### 4. Code Editor Component

```tsx
// frontend/src/components/Editor/CodeEditor.tsx

import { useCallback, useRef } from 'react';
import Editor, { OnMount, OnChange } from '@monaco-editor/react';
import { useASTStore } from '../../stores/astStore';
import { useASTWebSocket } from '../../hooks/useWebSocket';
import { debounce } from 'lodash-es';

const LANGUAGE_MAP: Record<string, string> = {
  python: 'python',
  javascript: 'javascript',
  typescript: 'typescript',
  rust: 'rust',
  go: 'go',
  java: 'java',
  cpp: 'cpp',
  c: 'c',
};

export function CodeEditor() {
  const editorRef = useRef<any>(null);
  const decorationsRef = useRef<string[]>([]);

  const {
    sourceCode,
    language,
    selectedNodeId,
    hoveredNodeId,
    ast,
    setSourceCode,
  } = useASTStore();

  const { sendUpdate } = useASTWebSocket();

  // Debounced update to avoid overwhelming the backend
  const debouncedSendUpdate = useCallback(
    debounce((code: string, lang: string) => {
      sendUpdate(code, lang);
    }, 300),
    [sendUpdate]
  );

  const handleEditorMount: OnMount = (editor) => {
    editorRef.current = editor;

    // Initial parse
    if (sourceCode) {
      sendUpdate(sourceCode, language);
    }
  };

  const handleEditorChange: OnChange = (value) => {
    const code = value || '';
    setSourceCode(code);
    debouncedSendUpdate(code, language);
  };

  // Highlight selected/hovered nodes
  useEffect(() => {
    if (!editorRef.current || !ast) return;

    const decorations: any[] = [];

    // Find nodes to highlight
    const findNode = (node: ASTNode, targetId: string): ASTNode | null => {
      if (node.id === targetId) return node;
      for (const child of node.children) {
        const found = findNode(child, targetId);
        if (found) return found;
      }
      return null;
    };

    // Highlight selected node
    if (selectedNodeId) {
      const node = findNode(ast, selectedNodeId);
      if (node) {
        decorations.push({
          range: {
            startLineNumber: node.start_point[0] + 1,
            startColumn: node.start_point[1] + 1,
            endLineNumber: node.end_point[0] + 1,
            endColumn: node.end_point[1] + 1,
          },
          options: {
            className: 'ast-selected-node',
            isWholeLine: false,
          },
        });
      }
    }

    // Highlight hovered node (lighter)
    if (hoveredNodeId && hoveredNodeId !== selectedNodeId) {
      const node = findNode(ast, hoveredNodeId);
      if (node) {
        decorations.push({
          range: {
            startLineNumber: node.start_point[0] + 1,
            startColumn: node.start_point[1] + 1,
            endLineNumber: node.end_point[0] + 1,
            endColumn: node.end_point[1] + 1,
          },
          options: {
            className: 'ast-hovered-node',
            isWholeLine: false,
          },
        });
      }
    }

    // Apply decorations
    decorationsRef.current = editorRef.current.deltaDecorations(
      decorationsRef.current,
      decorations
    );
  }, [ast, selectedNodeId, hoveredNodeId]);

  return (
    <div className="code-editor">
      <Editor
        height="100%"
        language={LANGUAGE_MAP[language] || 'plaintext'}
        value={sourceCode}
        onChange={handleEditorChange}
        onMount={handleEditorMount}
        theme="vs-dark"
        options={{
          minimap: { enabled: false },
          fontSize: 14,
          lineNumbers: 'on',
          scrollBeyondLastLine: false,
          automaticLayout: true,
        }}
      />
    </div>
  );
}
```

### 5. AST Tree View Component

```tsx
// frontend/src/components/ASTTree/TreeView.tsx

import { useMemo } from 'react';
import { useASTStore } from '../../stores/astStore';
import { TreeNode } from './TreeNode';
import type { ASTNode } from '../../types/ast';

export function TreeView() {
  const { ast, selectedNodeId, hoveredNodeId, selectNode, hoverNode } =
    useASTStore();

  if (!ast) {
    return (
      <div className="tree-view-empty">
        <p>Enter code in the editor to see the AST</p>
      </div>
    );
  }

  return (
    <div className="tree-view">
      <div className="tree-view-header">
        <h3>Abstract Syntax Tree</h3>
        <span className="node-count">
          {countNodes(ast)} nodes
        </span>
      </div>
      <div className="tree-view-content">
        <TreeNode
          node={ast}
          depth={0}
          selectedNodeId={selectedNodeId}
          hoveredNodeId={hoveredNodeId}
          onSelect={selectNode}
          onHover={hoverNode}
        />
      </div>
    </div>
  );
}

function countNodes(node: ASTNode): number {
  return 1 + node.children.reduce((acc, child) => acc + countNodes(child), 0);
}
```

```tsx
// frontend/src/components/ASTTree/TreeNode.tsx

import { useState, useCallback } from 'react';
import type { ASTNode } from '../../types/ast';

interface TreeNodeProps {
  node: ASTNode;
  depth: number;
  selectedNodeId: string | null;
  hoveredNodeId: string | null;
  onSelect: (id: string | null) => void;
  onHover: (id: string | null) => void;
}

export function TreeNode({
  node,
  depth,
  selectedNodeId,
  hoveredNodeId,
  onSelect,
  onHover,
}: TreeNodeProps) {
  const [isExpanded, setIsExpanded] = useState(depth < 3);

  const isSelected = node.id === selectedNodeId;
  const isHovered = node.id === hoveredNodeId;
  const hasChildren = node.children.length > 0;

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onSelect(isSelected ? null : node.id);
    },
    [node.id, isSelected, onSelect]
  );

  const handleToggle = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      setIsExpanded(!isExpanded);
    },
    [isExpanded]
  );

  const nodeClassName = [
    'tree-node',
    isSelected && 'tree-node--selected',
    isHovered && 'tree-node--hovered',
    !node.is_named && 'tree-node--anonymous',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className="tree-node-container">
      <div
        className={nodeClassName}
        style={{ paddingLeft: `${depth * 16}px` }}
        onClick={handleClick}
        onMouseEnter={() => onHover(node.id)}
        onMouseLeave={() => onHover(null)}
      >
        {/* Expand/Collapse Toggle */}
        {hasChildren ? (
          <button
            className="tree-node-toggle"
            onClick={handleToggle}
          >
            {isExpanded ? '▼' : '▶'}
          </button>
        ) : (
          <span className="tree-node-toggle-placeholder" />
        )}

        {/* Node Type */}
        <span className="tree-node-type">{node.type}</span>

        {/* Field Name (if present) */}
        {node.field_name && (
          <span className="tree-node-field">
            ({node.field_name})
          </span>
        )}

        {/* Preview Text (truncated) */}
        {node.text && node.text.length < 50 && !hasChildren && (
          <span className="tree-node-text">
            "{node.text}"
          </span>
        )}

        {/* Position */}
        <span className="tree-node-position">
          [{node.start_point[0]}:{node.start_point[1]}]
        </span>
      </div>

      {/* Children */}
      {hasChildren && isExpanded && (
        <div className="tree-node-children">
          {node.children.map((child, index) => (
            <TreeNode
              key={`${child.id}-${index}`}
              node={child}
              depth={depth + 1}
              selectedNodeId={selectedNodeId}
              hoveredNodeId={hoveredNodeId}
              onSelect={onSelect}
              onHover={onHover}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

### 6. Properties Panel

```tsx
// frontend/src/components/Properties/PropertiesPanel.tsx

import { useMemo } from 'react';
import { useASTStore } from '../../stores/astStore';
import type { ASTNode, CodeChunk } from '../../types/ast';

export function PropertiesPanel() {
  const { ast, chunks, selectedNodeId } = useASTStore();

  // Find selected node and matching chunk
  const { selectedNode, matchingChunk } = useMemo(() => {
    if (!selectedNodeId || !ast) {
      return { selectedNode: null, matchingChunk: null };
    }

    const findNode = (node: ASTNode): ASTNode | null => {
      if (node.id === selectedNodeId) return node;
      for (const child of node.children) {
        const found = findNode(child);
        if (found) return found;
      }
      return null;
    };

    const selectedNode = findNode(ast);

    // Find chunk that contains this node
    const matchingChunk = chunks.find((chunk) => {
      if (!selectedNode) return false;
      const nodeStartLine = selectedNode.start_point[0] + 1;
      const nodeEndLine = selectedNode.end_point[0] + 1;
      return (
        chunk.start_line <= nodeStartLine &&
        chunk.end_line >= nodeEndLine
      );
    });

    return { selectedNode, matchingChunk };
  }, [ast, chunks, selectedNodeId]);

  if (!selectedNode) {
    return (
      <div className="properties-panel">
        <h3>Properties</h3>
        <p className="properties-empty">Select a node to view properties</p>
      </div>
    );
  }

  return (
    <div className="properties-panel">
      <h3>Properties</h3>

      {/* Node Info */}
      <section className="properties-section">
        <h4>Node</h4>
        <dl className="properties-list">
          <dt>Type</dt>
          <dd><code>{selectedNode.type}</code></dd>

          <dt>Named</dt>
          <dd>{selectedNode.is_named ? 'Yes' : 'No'}</dd>

          {selectedNode.field_name && (
            <>
              <dt>Field</dt>
              <dd>{selectedNode.field_name}</dd>
            </>
          )}

          <dt>Children</dt>
          <dd>{selectedNode.children.length}</dd>
        </dl>
      </section>

      {/* Position */}
      <section className="properties-section">
        <h4>Position</h4>
        <dl className="properties-list">
          <dt>Start</dt>
          <dd>
            Line {selectedNode.start_point[0] + 1},
            Col {selectedNode.start_point[1] + 1}
          </dd>

          <dt>End</dt>
          <dd>
            Line {selectedNode.end_point[0] + 1},
            Col {selectedNode.end_point[1] + 1}
          </dd>

          <dt>Bytes</dt>
          <dd>
            {selectedNode.start_byte} - {selectedNode.end_byte}
            ({selectedNode.end_byte - selectedNode.start_byte} bytes)
          </dd>
        </dl>
      </section>

      {/* Text Content */}
      {selectedNode.text && (
        <section className="properties-section">
          <h4>Text</h4>
          <pre className="properties-text">{selectedNode.text}</pre>
        </section>
      )}

      {/* Chunk Metadata (if available) */}
      {matchingChunk && (
        <section className="properties-section">
          <h4>Chunk Metadata</h4>
          <dl className="properties-list">
            <dt>Chunk ID</dt>
            <dd><code>{matchingChunk.id.slice(0, 12)}...</code></dd>

            <dt>Context</dt>
            <dd>{matchingChunk.parent_context || 'Global'}</dd>

            <dt>Route</dt>
            <dd>{matchingChunk.parent_route.join(' → ')}</dd>

            {matchingChunk.metadata.token_count && (
              <>
                <dt>Tokens</dt>
                <dd>{matchingChunk.metadata.token_count}</dd>
              </>
            )}

            {matchingChunk.metadata.complexity && (
              <>
                <dt>Complexity</dt>
                <dd>
                  Cyclomatic: {matchingChunk.metadata.complexity.cyclomatic},
                  Cognitive: {matchingChunk.metadata.complexity.cognitive}
                </dd>
              </>
            )}

            {matchingChunk.metadata.calls?.length > 0 && (
              <>
                <dt>Calls</dt>
                <dd>{matchingChunk.metadata.calls.join(', ')}</dd>
              </>
            )}
          </dl>
        </section>
      )}
    </div>
  );
}
```

### 7. Main App Layout

```tsx
// frontend/src/App.tsx

import { CodeEditor } from './components/Editor/CodeEditor';
import { TreeView } from './components/ASTTree/TreeView';
import { PropertiesPanel } from './components/Properties/PropertiesPanel';
import { LanguageSelector } from './components/Editor/LanguageSelector';
import './App.css';

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>AST Viewer</h1>
        <LanguageSelector />
      </header>

      <main className="app-main">
        <div className="panel panel-editor">
          <CodeEditor />
        </div>

        <div className="panel panel-tree">
          <TreeView />
        </div>

        <div className="panel panel-properties">
          <PropertiesPanel />
        </div>
      </main>
    </div>
  );
}

export default App;
```

---

## Key Features to Implement

### Feature Matrix

| Feature | Difficulty | treesitter-chunker Support |
|---------|------------|----------------------------|
| Basic AST Tree View | Easy | `get_parser()` + tree traversal |
| Syntax Highlighting Sync | Easy | Node start/end positions |
| Multi-language Support | Easy | 36+ built-in plugins |
| Node Search/Filter | Medium | Custom traversal |
| Incremental Updates | Medium | `DefaultIncrementalProcessor` |
| Dependency Graph | Medium | `build_xref()`, `graph_cut()` |
| Code Complexity View | Easy | `metadata.complexity` |
| Chunk-level Navigation | Easy | `chunk_text()` output |
| AST Diff Visualization | Medium | Incremental processor |
| Export to JSON/GraphML | Easy | Built-in exporters |
| Custom Node Styling | Easy | Node type → CSS class |
| Breadcrumb Navigation | Easy | `parent_route` from chunks |

### Implementation Priority

**Phase 1: Core Functionality**
1. Basic parsing and tree display
2. Editor ↔ Tree synchronization
3. Node selection and highlighting
4. Language switching

**Phase 2: Enhanced Analysis**
1. Properties panel with metadata
2. Semantic chunk view
3. Search and filtering
4. Breadcrumb navigation

**Phase 3: Advanced Features**
1. Dependency graph visualization
2. Incremental diff highlighting
3. Export functionality
4. Custom styling/themes

---

## Integration Examples

### Example 1: Adding a "Go to Definition" Feature

```python
# backend/services/navigation_service.py

from chunker import chunk_text
from chunker.graph.xref import build_xref


class NavigationService:
    def find_definition(
        self,
        source_code: str,
        language: str,
        symbol_name: str,
    ) -> dict | None:
        """Find where a symbol is defined."""
        chunks = chunk_text(source_code, language)
        nodes, edges = build_xref(chunks)

        # Find definition edges pointing to this symbol
        for edge in edges:
            if edge.get("type") == "DEFINES":
                target_node = next(
                    (n for n in nodes if n["id"] == edge["dst"]),
                    None
                )
                if target_node and target_node.get("symbol") == symbol_name:
                    # Find the chunk with this ID
                    for chunk in chunks:
                        if chunk.chunk_id == edge["dst"]:
                            return {
                                "file_path": chunk.file_path,
                                "start_line": chunk.start_line,
                                "end_line": chunk.end_line,
                                "content": chunk.content,
                            }

        return None
```

### Example 2: Syntax-Aware Code Folding

```typescript
// frontend/src/hooks/useCodeFolding.ts

import { useMemo } from 'react';
import type { CodeChunk } from '../types/ast';

interface FoldingRange {
  start: number;
  end: number;
  kind: 'function' | 'class' | 'block';
}

export function useCodeFolding(chunks: CodeChunk[]): FoldingRange[] {
  return useMemo(() => {
    return chunks
      .filter((chunk) =>
        ['function_definition', 'class_definition', 'method'].includes(
          chunk.node_type
        )
      )
      .map((chunk) => ({
        start: chunk.start_line,
        end: chunk.end_line,
        kind: chunk.node_type.includes('class') ? 'class' : 'function',
      }));
  }, [chunks]);
}
```

### Example 3: Complexity Heatmap Overlay

```typescript
// frontend/src/components/ComplexityOverlay.tsx

import { useMemo } from 'react';
import type { CodeChunk } from '../types/ast';

function getComplexityColor(cyclomatic: number): string {
  if (cyclomatic <= 5) return 'rgba(0, 255, 0, 0.1)';   // Green - simple
  if (cyclomatic <= 10) return 'rgba(255, 255, 0, 0.1)'; // Yellow - moderate
  if (cyclomatic <= 20) return 'rgba(255, 165, 0, 0.1)'; // Orange - complex
  return 'rgba(255, 0, 0, 0.2)';                          // Red - very complex
}

export function useComplexityDecorations(chunks: CodeChunk[]) {
  return useMemo(() => {
    return chunks
      .filter((chunk) => chunk.metadata.complexity)
      .map((chunk) => ({
        range: {
          startLineNumber: chunk.start_line,
          startColumn: 1,
          endLineNumber: chunk.end_line,
          endColumn: 1,
        },
        options: {
          isWholeLine: true,
          className: 'complexity-overlay',
          backgroundColor: getComplexityColor(
            chunk.metadata.complexity!.cyclomatic
          ),
        },
      }));
  }, [chunks]);
}
```

---

## Performance Considerations

### Backend Optimizations

```python
# backend/utils/caching.py

from functools import lru_cache
from hashlib import sha256
from chunker import get_parser


# Parser caching is already handled by treesitter-chunker
# Additional application-level caching:

@lru_cache(maxsize=100)
def cached_parse(source_hash: str, language: str):
    """
    Cache parsed ASTs by content hash.

    Note: treesitter-chunker already caches parsers (11.9x speedup),
    but we can cache the full AST serialization too.
    """
    # This is called after hash computation
    pass


def compute_source_hash(source_code: str) -> str:
    """Compute hash for caching."""
    return sha256(source_code.encode()).hexdigest()[:16]


# Rate limiting for WebSocket updates
class RateLimiter:
    def __init__(self, min_interval_ms: int = 100):
        self.min_interval = min_interval_ms / 1000
        self.last_update: dict[str, float] = {}

    def should_process(self, session_id: str) -> bool:
        import time
        now = time.time()
        last = self.last_update.get(session_id, 0)

        if now - last >= self.min_interval:
            self.last_update[session_id] = now
            return True
        return False
```

### Frontend Optimizations

```typescript
// frontend/src/hooks/useVirtualizedTree.ts

import { useMemo, useState, useCallback } from 'react';
import type { ASTNode } from '../types/ast';

interface FlattenedNode {
  node: ASTNode;
  depth: number;
  isExpanded: boolean;
  hasChildren: boolean;
}

/**
 * For large ASTs, flatten and virtualize the tree.
 * Only render visible nodes.
 */
export function useVirtualizedTree(
  root: ASTNode | null,
  maxVisible: number = 500
) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const flattenedNodes = useMemo(() => {
    if (!root) return [];

    const result: FlattenedNode[] = [];

    function flatten(node: ASTNode, depth: number) {
      if (result.length >= maxVisible) return;

      const isExpanded = expandedIds.has(node.id);

      result.push({
        node,
        depth,
        isExpanded,
        hasChildren: node.children.length > 0,
      });

      if (isExpanded) {
        for (const child of node.children) {
          flatten(child, depth + 1);
        }
      }
    }

    flatten(root, 0);
    return result;
  }, [root, expandedIds, maxVisible]);

  const toggleExpand = useCallback((nodeId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  }, []);

  return { flattenedNodes, toggleExpand };
}
```

### Recommended Limits

| Metric | Recommended Limit | Reason |
|--------|-------------------|--------|
| Max file size | 1 MB | Tree-sitter handles larger, but UI slows |
| Tree render depth | 50 levels | DOM performance |
| Visible nodes | 500 | Smooth scrolling |
| WebSocket update rate | 100ms debounce | Network efficiency |
| AST cache entries | 100 | Memory management |

---

## Deployment

### Docker Compose Setup

```yaml
# docker-compose.yml

version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - PYTHONUNBUFFERED=1
    volumes:
      - grammar-cache:/root/.cache/treesitter-chunker

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    depends_on:
      - backend

volumes:
  grammar-cache:
```

### Backend Dockerfile

```dockerfile
# backend/Dockerfile

FROM python:3.11-slim

# Install build dependencies for tree-sitter grammars
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Preload common grammars
RUN python -c "from chunker import get_parser; \
    [get_parser(l) for l in ['python', 'javascript', 'typescript', 'rust', 'go']]"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend Dockerfile

```dockerfile
# frontend/Dockerfile

FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

---

## Part 2: Code Intelligence Platform Architecture

For building a **production code intelligence system** that serves both human visualization and AI agent context management, a database-backed architecture is the right approach. This section covers building a platform where:

- **Code is the source of truth** stored in the database
- **Humans** visualize and navigate via the AST viewer UI
- **AI agents** query for relevant context via APIs
- **Changes propagate** through a one-way reactive data flow

### Why Database-Backed Architecture?

| Requirement | Direct WebSocket | DB-Backed |
|-------------|------------------|-----------|
| Persist code across sessions | No | Yes |
| Multi-user/multi-agent access | Limited | Yes |
| Query code semantically | No | Yes (vector search) |
| Version history | No | Yes |
| Cross-repository analysis | No | Yes |
| Offline AI agent access | No | Yes (cached) |

### Platform Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CONSUMERS                                       │
│                                                                             │
│   ┌─────────────────────┐              ┌─────────────────────────────────┐  │
│   │    HUMAN VIEWER     │              │         AI AGENTS               │  │
│   │  ┌───────────────┐  │              │  ┌─────────────────────────┐   │  │
│   │  │ Code Editor   │  │              │  │ Context Retrieval API   │   │  │
│   │  │ AST Tree View │  │              │  │ - Semantic search       │   │  │
│   │  │ Dependency    │  │              │  │ - Graph traversal       │   │  │
│   │  │   Graph       │  │              │  │ - Chunk retrieval       │   │  │
│   │  └───────────────┘  │              │  └─────────────────────────┘   │  │
│   └──────────┬──────────┘              └──────────────┬─────────────────┘  │
│              │                                        │                     │
│              │         Subscribe (read-only)          │  Query              │
│              └────────────────┬───────────────────────┘                     │
│                               │                                             │
└───────────────────────────────┼─────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────────────────┐
│                          DATABASE LAYER                                      │
│                               │                                             │
│   ┌───────────────────────────▼───────────────────────────────────────────┐ │
│   │                    PostgreSQL + pgvector                               │ │
│   │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐  │ │
│   │  │   files      │ │   chunks     │ │  embeddings  │ │    edges     │  │ │
│   │  │  - path      │ │  - chunk_id  │ │  - chunk_id  │ │  - source    │  │ │
│   │  │  - content   │ │  - content   │ │  - vector    │ │  - target    │  │ │
│   │  │  - language  │ │  - metadata  │ │  - model     │ │  - type      │  │ │
│   │  │  - hash      │ │  - file_id   │ │              │ │  - weight    │  │ │
│   │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘  │ │
│   │                                                                        │ │
│   │                    Real-time Subscriptions (Supabase)                  │ │
│   └────────────────────────────────────────────────────────────────────────┘ │
│                               ▲                                             │
└───────────────────────────────┼─────────────────────────────────────────────┘
                                │
                                │ Write (one-way)
                                │
┌───────────────────────────────┼─────────────────────────────────────────────┐
│                        INDEXING SERVICE                                      │
│                               │                                             │
│   ┌───────────────────────────▼───────────────────────────────────────────┐ │
│   │                    Code Indexing Pipeline                              │ │
│   │                                                                        │ │
│   │  1. Receive code → 2. Parse AST → 3. Extract chunks → 4. Embed        │ │
│   │                         │              │                  │            │ │
│   │                   treesitter-     treesitter-      OpenAI /           │ │
│   │                   chunker         chunker          local model         │ │
│   │                                                                        │ │
│   │  5. Build xref graph → 6. Write to DB → 7. Notify subscribers         │ │
│   └────────────────────────────────────────────────────────────────────────┘ │
│                               ▲                                             │
└───────────────────────────────┼─────────────────────────────────────────────┘
                                │
                                │ Code changes
                                │
┌───────────────────────────────┼─────────────────────────────────────────────┐
│                         CODE SOURCES                                         │
│   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                   │
│   │  Git Repos    │  │  File Upload  │  │  Editor API   │                   │
│   └───────────────┘  └───────────────┘  └───────────────┘                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Database Schema

```sql
-- PostgreSQL with pgvector extension

-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Repositories/Projects
CREATE TABLE repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    url TEXT,
    default_branch TEXT DEFAULT 'main',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Source files (the source of truth)
CREATE TABLE files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    content TEXT NOT NULL,
    language TEXT NOT NULL,
    content_hash TEXT NOT NULL,  -- SHA256 for change detection
    version INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(repository_id, path)
);

-- Index for fast lookups
CREATE INDEX idx_files_repo_path ON files(repository_id, path);
CREATE INDEX idx_files_language ON files(language);
CREATE INDEX idx_files_hash ON files(content_hash);

-- Semantic code chunks (derived from files via treesitter-chunker)
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID REFERENCES files(id) ON DELETE CASCADE,

    -- treesitter-chunker identifiers
    chunk_id TEXT NOT NULL,        -- Stable SHA1 from treesitter-chunker
    node_id TEXT NOT NULL,         -- Node identifier

    -- Content & position
    content TEXT NOT NULL,
    node_type TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    start_byte INTEGER NOT NULL,
    end_byte INTEGER NOT NULL,

    -- Context hierarchy
    parent_context TEXT,           -- e.g., "ClassName"
    parent_route TEXT[],           -- e.g., ["module", "Class", "method"]
    parent_chunk_id UUID REFERENCES chunks(id),

    -- Rich metadata from treesitter-chunker
    metadata JSONB DEFAULT '{}',   -- complexity, calls, imports, etc.

    -- Tracking
    created_at TIMESTAMPTZ DEFAULT NOW(),
    file_version INTEGER NOT NULL,  -- Links to files.version

    UNIQUE(file_id, chunk_id)
);

-- Indexes for chunk queries
CREATE INDEX idx_chunks_file ON chunks(file_id);
CREATE INDEX idx_chunks_node_type ON chunks(node_type);
CREATE INDEX idx_chunks_parent ON chunks(parent_chunk_id);
CREATE INDEX idx_chunks_metadata ON chunks USING GIN(metadata);

-- Vector embeddings for semantic search
CREATE TABLE embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id UUID REFERENCES chunks(id) ON DELETE CASCADE,

    -- Embedding vector (1536 dims for text-embedding-3-small)
    embedding vector(1536) NOT NULL,

    -- Model tracking
    model TEXT NOT NULL,           -- e.g., "text-embedding-3-small"
    model_version TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(chunk_id, model)
);

-- Vector similarity index
CREATE INDEX idx_embeddings_vector ON embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Cross-reference edges (from treesitter-chunker's build_xref)
CREATE TABLE edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_chunk_id UUID REFERENCES chunks(id) ON DELETE CASCADE,
    target_chunk_id UUID REFERENCES chunks(id) ON DELETE CASCADE,

    edge_type TEXT NOT NULL,       -- DEFINES, IMPORTS, CALLS, INHERITS, REFERENCES
    weight FLOAT DEFAULT 1.0,
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(source_chunk_id, target_chunk_id, edge_type)
);

-- Index for graph traversal
CREATE INDEX idx_edges_source ON edges(source_chunk_id);
CREATE INDEX idx_edges_target ON edges(target_chunk_id);
CREATE INDEX idx_edges_type ON edges(edge_type);

-- Symbols table for fast symbol lookup
CREATE TABLE symbols (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id UUID REFERENCES chunks(id) ON DELETE CASCADE,

    name TEXT NOT NULL,
    kind TEXT NOT NULL,            -- function, class, method, variable
    language TEXT NOT NULL,

    -- Quick access without joining
    file_path TEXT NOT NULL,
    start_line INTEGER NOT NULL,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_symbols_name ON symbols(name);
CREATE INDEX idx_symbols_kind ON symbols(kind);
CREATE INDEX idx_symbols_name_trgm ON symbols USING GIN(name gin_trgm_ops);  -- Fuzzy search
```

### Indexing Service Implementation

```python
# services/indexing_service.py

import asyncio
import hashlib
from dataclasses import dataclass
from typing import AsyncIterator

import asyncpg
from openai import AsyncOpenAI

from chunker import chunk_text, get_parser
from chunker.graph.xref import build_xref
from chunker.types import CodeChunk


@dataclass
class IndexingResult:
    file_id: str
    chunks_indexed: int
    embeddings_created: int
    edges_created: int


class CodeIndexingService:
    """
    Service that indexes code into the database.

    This is the ONLY writer to the database. All other services
    (human UI, AI agents) only read from it.
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        openai_client: AsyncOpenAI,
        embedding_model: str = "text-embedding-3-small",
    ):
        self.db = db_pool
        self.openai = openai_client
        self.embedding_model = embedding_model

    async def index_file(
        self,
        repository_id: str,
        file_path: str,
        content: str,
        language: str,
    ) -> IndexingResult:
        """
        Index a single file: parse, chunk, embed, and store.

        This is idempotent - re-indexing the same content is a no-op.
        """
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        async with self.db.acquire() as conn:
            # Check if file already indexed with same content
            existing = await conn.fetchrow(
                """
                SELECT id, version FROM files
                WHERE repository_id = $1 AND path = $2 AND content_hash = $3
                """,
                repository_id, file_path, content_hash
            )

            if existing:
                # Content unchanged, skip re-indexing
                return IndexingResult(
                    file_id=str(existing['id']),
                    chunks_indexed=0,
                    embeddings_created=0,
                    edges_created=0,
                )

            # Start transaction
            async with conn.transaction():
                # Upsert file
                file_row = await conn.fetchrow(
                    """
                    INSERT INTO files (repository_id, path, content, language, content_hash)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (repository_id, path) DO UPDATE SET
                        content = EXCLUDED.content,
                        language = EXCLUDED.language,
                        content_hash = EXCLUDED.content_hash,
                        version = files.version + 1,
                        updated_at = NOW()
                    RETURNING id, version
                    """,
                    repository_id, file_path, content, language, content_hash
                )

                file_id = file_row['id']
                file_version = file_row['version']

                # Delete old chunks (cascade deletes embeddings and edges)
                await conn.execute(
                    "DELETE FROM chunks WHERE file_id = $1 AND file_version < $2",
                    file_id, file_version
                )

                # Parse and chunk with treesitter-chunker
                chunks = chunk_text(content, language)

                if not chunks:
                    return IndexingResult(
                        file_id=str(file_id),
                        chunks_indexed=0,
                        embeddings_created=0,
                        edges_created=0,
                    )

                # Build xref graph
                nodes, xref_edges = build_xref(chunks)

                # Insert chunks
                chunk_id_map = {}  # chunk.chunk_id -> db UUID

                for chunk in chunks:
                    chunk_db_id = await conn.fetchval(
                        """
                        INSERT INTO chunks (
                            file_id, chunk_id, node_id, content, node_type,
                            start_line, end_line, start_byte, end_byte,
                            parent_context, parent_route, metadata, file_version
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                        ON CONFLICT (file_id, chunk_id) DO UPDATE SET
                            content = EXCLUDED.content,
                            metadata = EXCLUDED.metadata,
                            file_version = EXCLUDED.file_version
                        RETURNING id
                        """,
                        file_id, chunk.chunk_id, chunk.node_id, chunk.content,
                        chunk.node_type, chunk.start_line, chunk.end_line,
                        chunk.byte_start, chunk.byte_end, chunk.parent_context,
                        chunk.parent_route, chunk.metadata, file_version
                    )
                    chunk_id_map[chunk.chunk_id] = chunk_db_id

                    # Insert symbol for quick lookup
                    symbol_name = self._extract_symbol_name(chunk)
                    if symbol_name:
                        await conn.execute(
                            """
                            INSERT INTO symbols (chunk_id, name, kind, language, file_path, start_line)
                            VALUES ($1, $2, $3, $4, $5, $6)
                            ON CONFLICT DO NOTHING
                            """,
                            chunk_db_id, symbol_name, chunk.node_type,
                            language, file_path, chunk.start_line
                        )

                # Insert edges
                edges_created = 0
                for edge in xref_edges:
                    src_db_id = chunk_id_map.get(edge['src'])
                    dst_db_id = chunk_id_map.get(edge['dst'])

                    if src_db_id and dst_db_id:
                        await conn.execute(
                            """
                            INSERT INTO edges (source_chunk_id, target_chunk_id, edge_type, weight)
                            VALUES ($1, $2, $3, $4)
                            ON CONFLICT DO NOTHING
                            """,
                            src_db_id, dst_db_id,
                            edge.get('type', 'REFERENCES'),
                            edge.get('weight', 1.0)
                        )
                        edges_created += 1

                # Generate and store embeddings
                embeddings_created = await self._create_embeddings(
                    conn, chunks, chunk_id_map
                )

                return IndexingResult(
                    file_id=str(file_id),
                    chunks_indexed=len(chunks),
                    embeddings_created=embeddings_created,
                    edges_created=edges_created,
                )

    async def _create_embeddings(
        self,
        conn: asyncpg.Connection,
        chunks: list[CodeChunk],
        chunk_id_map: dict[str, str],
    ) -> int:
        """Generate embeddings for chunks in batches."""

        # Prepare texts for embedding
        texts = []
        chunk_ids = []

        for chunk in chunks:
            # Create embedding text with context
            embed_text = self._prepare_embedding_text(chunk)
            texts.append(embed_text)
            chunk_ids.append(chunk_id_map[chunk.chunk_id])

        # Batch embed (OpenAI allows up to 2048 per request)
        embeddings_created = 0
        batch_size = 100

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_ids = chunk_ids[i:i + batch_size]

            response = await self.openai.embeddings.create(
                model=self.embedding_model,
                input=batch_texts,
            )

            for j, embedding_data in enumerate(response.data):
                await conn.execute(
                    """
                    INSERT INTO embeddings (chunk_id, embedding, model)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (chunk_id, model) DO UPDATE SET
                        embedding = EXCLUDED.embedding
                    """,
                    batch_ids[j],
                    embedding_data.embedding,
                    self.embedding_model,
                )
                embeddings_created += 1

        return embeddings_created

    def _prepare_embedding_text(self, chunk: CodeChunk) -> str:
        """Prepare text for embedding with context."""
        parts = []

        # Add hierarchical context
        if chunk.parent_route:
            parts.append(f"Path: {' > '.join(chunk.parent_route)}")

        # Add type info
        parts.append(f"Type: {chunk.node_type}")

        # Add the code
        parts.append(chunk.content)

        return "\n".join(parts)

    def _extract_symbol_name(self, chunk: CodeChunk) -> str | None:
        """Extract symbol name from chunk for symbol table."""
        if chunk.parent_route:
            return chunk.parent_route[-1]
        return None
```

### AI Agent Context Retrieval API

```python
# services/context_service.py

from dataclasses import dataclass
from typing import Literal

import asyncpg
from openai import AsyncOpenAI


@dataclass
class ContextChunk:
    """A chunk of code returned to AI agents."""
    chunk_id: str
    file_path: str
    language: str
    content: str
    node_type: str
    start_line: int
    end_line: int
    parent_context: str | None
    parent_route: list[str]
    relevance_score: float
    metadata: dict


@dataclass
class ContextResult:
    """Result of a context query."""
    chunks: list[ContextChunk]
    total_tokens: int  # Estimated token count
    query_type: str


class AIContextService:
    """
    Service for AI agents to retrieve relevant code context.

    Provides multiple retrieval strategies:
    - Semantic search (vector similarity)
    - Symbol lookup (exact/fuzzy name match)
    - Graph traversal (related code)
    - Hybrid (combine multiple strategies)
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        openai_client: AsyncOpenAI,
        embedding_model: str = "text-embedding-3-small",
    ):
        self.db = db_pool
        self.openai = openai_client
        self.embedding_model = embedding_model

    async def semantic_search(
        self,
        query: str,
        repository_id: str | None = None,
        languages: list[str] | None = None,
        limit: int = 10,
        similarity_threshold: float = 0.7,
    ) -> ContextResult:
        """
        Find code chunks semantically similar to a natural language query.

        Use for:
        - "Find code that handles user authentication"
        - "Where is the database connection configured?"
        - "Show me error handling patterns"
        """
        # Generate query embedding
        response = await self.openai.embeddings.create(
            model=self.embedding_model,
            input=query,
        )
        query_embedding = response.data[0].embedding

        # Build query with filters
        sql = """
            SELECT
                c.id::text as chunk_id,
                f.path as file_path,
                f.language,
                c.content,
                c.node_type,
                c.start_line,
                c.end_line,
                c.parent_context,
                c.parent_route,
                c.metadata,
                1 - (e.embedding <=> $1::vector) as similarity
            FROM embeddings e
            JOIN chunks c ON c.id = e.chunk_id
            JOIN files f ON f.id = c.file_id
            WHERE 1 - (e.embedding <=> $1::vector) > $2
        """
        params = [query_embedding, similarity_threshold]
        param_idx = 3

        if repository_id:
            sql += f" AND f.repository_id = ${param_idx}"
            params.append(repository_id)
            param_idx += 1

        if languages:
            sql += f" AND f.language = ANY(${param_idx})"
            params.append(languages)
            param_idx += 1

        sql += f" ORDER BY similarity DESC LIMIT ${param_idx}"
        params.append(limit)

        async with self.db.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        chunks = [
            ContextChunk(
                chunk_id=row['chunk_id'],
                file_path=row['file_path'],
                language=row['language'],
                content=row['content'],
                node_type=row['node_type'],
                start_line=row['start_line'],
                end_line=row['end_line'],
                parent_context=row['parent_context'],
                parent_route=row['parent_route'] or [],
                relevance_score=float(row['similarity']),
                metadata=row['metadata'] or {},
            )
            for row in rows
        ]

        return ContextResult(
            chunks=chunks,
            total_tokens=self._estimate_tokens(chunks),
            query_type="semantic_search",
        )

    async def find_symbol(
        self,
        symbol_name: str,
        repository_id: str | None = None,
        kind: str | None = None,  # function, class, method
        fuzzy: bool = False,
        limit: int = 10,
    ) -> ContextResult:
        """
        Find code by symbol name.

        Use for:
        - "Find the UserService class"
        - "Show me the authenticate function"
        - "Where is processPayment defined?"
        """
        async with self.db.acquire() as conn:
            if fuzzy:
                # Fuzzy trigram search
                sql = """
                    SELECT
                        c.id::text as chunk_id,
                        f.path as file_path,
                        f.language,
                        c.content,
                        c.node_type,
                        c.start_line,
                        c.end_line,
                        c.parent_context,
                        c.parent_route,
                        c.metadata,
                        similarity(s.name, $1) as relevance
                    FROM symbols s
                    JOIN chunks c ON c.id = s.chunk_id
                    JOIN files f ON f.id = c.file_id
                    WHERE s.name % $1
                """
            else:
                # Exact match (case-insensitive)
                sql = """
                    SELECT
                        c.id::text as chunk_id,
                        f.path as file_path,
                        f.language,
                        c.content,
                        c.node_type,
                        c.start_line,
                        c.end_line,
                        c.parent_context,
                        c.parent_route,
                        c.metadata,
                        1.0 as relevance
                    FROM symbols s
                    JOIN chunks c ON c.id = s.chunk_id
                    JOIN files f ON f.id = c.file_id
                    WHERE LOWER(s.name) = LOWER($1)
                """

            params = [symbol_name]
            param_idx = 2

            if repository_id:
                sql += f" AND f.repository_id = ${param_idx}"
                params.append(repository_id)
                param_idx += 1

            if kind:
                sql += f" AND s.kind = ${param_idx}"
                params.append(kind)
                param_idx += 1

            sql += f" ORDER BY relevance DESC LIMIT ${param_idx}"
            params.append(limit)

            rows = await conn.fetch(sql, *params)

        chunks = [self._row_to_chunk(row) for row in rows]

        return ContextResult(
            chunks=chunks,
            total_tokens=self._estimate_tokens(chunks),
            query_type="symbol_search",
        )

    async def get_related_code(
        self,
        chunk_id: str,
        relationship_types: list[str] | None = None,
        direction: Literal["incoming", "outgoing", "both"] = "both",
        depth: int = 1,
        limit: int = 20,
    ) -> ContextResult:
        """
        Find code related to a specific chunk via the xref graph.

        Use for:
        - "What calls this function?"
        - "What does this class depend on?"
        - "Show me code that imports this module"
        """
        relationship_types = relationship_types or [
            "CALLS", "IMPORTS", "INHERITS", "REFERENCES", "DEFINES"
        ]

        async with self.db.acquire() as conn:
            # Use recursive CTE for multi-hop traversal
            sql = """
                WITH RECURSIVE related AS (
                    -- Base case: direct relationships
                    SELECT
                        CASE
                            WHEN e.source_chunk_id = $1::uuid THEN e.target_chunk_id
                            ELSE e.source_chunk_id
                        END as chunk_id,
                        e.edge_type,
                        1 as depth,
                        CASE
                            WHEN e.source_chunk_id = $1::uuid THEN 'outgoing'
                            ELSE 'incoming'
                        END as direction
                    FROM edges e
                    WHERE (e.source_chunk_id = $1::uuid OR e.target_chunk_id = $1::uuid)
                      AND e.edge_type = ANY($2)
                      AND ($3 = 'both'
                           OR ($3 = 'outgoing' AND e.source_chunk_id = $1::uuid)
                           OR ($3 = 'incoming' AND e.target_chunk_id = $1::uuid))

                    UNION

                    -- Recursive case: follow edges up to depth
                    SELECT
                        CASE
                            WHEN e.source_chunk_id = r.chunk_id THEN e.target_chunk_id
                            ELSE e.source_chunk_id
                        END,
                        e.edge_type,
                        r.depth + 1,
                        r.direction
                    FROM edges e
                    JOIN related r ON (e.source_chunk_id = r.chunk_id OR e.target_chunk_id = r.chunk_id)
                    WHERE r.depth < $4
                      AND e.edge_type = ANY($2)
                )
                SELECT DISTINCT
                    c.id::text as chunk_id,
                    f.path as file_path,
                    f.language,
                    c.content,
                    c.node_type,
                    c.start_line,
                    c.end_line,
                    c.parent_context,
                    c.parent_route,
                    c.metadata,
                    MIN(r.depth)::float / $4 as relevance  -- Closer = more relevant
                FROM related r
                JOIN chunks c ON c.id = r.chunk_id
                JOIN files f ON f.id = c.file_id
                WHERE r.chunk_id != $1::uuid
                GROUP BY c.id, f.path, f.language, c.content, c.node_type,
                         c.start_line, c.end_line, c.parent_context, c.parent_route, c.metadata
                ORDER BY relevance
                LIMIT $5
            """

            rows = await conn.fetch(
                sql, chunk_id, relationship_types, direction, depth, limit
            )

        chunks = [self._row_to_chunk(row) for row in rows]

        return ContextResult(
            chunks=chunks,
            total_tokens=self._estimate_tokens(chunks),
            query_type="graph_traversal",
        )

    async def get_file_chunks(
        self,
        file_path: str,
        repository_id: str,
        node_types: list[str] | None = None,
    ) -> ContextResult:
        """
        Get all chunks from a specific file.

        Use for:
        - "Show me all functions in auth.py"
        - "What classes are in this file?"
        """
        async with self.db.acquire() as conn:
            sql = """
                SELECT
                    c.id::text as chunk_id,
                    f.path as file_path,
                    f.language,
                    c.content,
                    c.node_type,
                    c.start_line,
                    c.end_line,
                    c.parent_context,
                    c.parent_route,
                    c.metadata,
                    1.0 as relevance
                FROM chunks c
                JOIN files f ON f.id = c.file_id
                WHERE f.path = $1 AND f.repository_id = $2
            """
            params = [file_path, repository_id]

            if node_types:
                sql += " AND c.node_type = ANY($3)"
                params.append(node_types)

            sql += " ORDER BY c.start_line"

            rows = await conn.fetch(sql, *params)

        chunks = [self._row_to_chunk(row) for row in rows]

        return ContextResult(
            chunks=chunks,
            total_tokens=self._estimate_tokens(chunks),
            query_type="file_chunks",
        )

    async def hybrid_search(
        self,
        query: str,
        repository_id: str | None = None,
        semantic_weight: float = 0.7,
        symbol_weight: float = 0.3,
        limit: int = 10,
    ) -> ContextResult:
        """
        Combine semantic search with symbol matching.

        Best for general "find relevant code" queries.
        """
        # Run both searches
        semantic_result = await self.semantic_search(
            query, repository_id, limit=limit * 2
        )
        symbol_result = await self.find_symbol(
            query, repository_id, fuzzy=True, limit=limit * 2
        )

        # Merge and re-rank
        seen_ids = set()
        merged = []

        for chunk in semantic_result.chunks:
            if chunk.chunk_id not in seen_ids:
                chunk.relevance_score *= semantic_weight
                merged.append(chunk)
                seen_ids.add(chunk.chunk_id)

        for chunk in symbol_result.chunks:
            if chunk.chunk_id in seen_ids:
                # Boost if found in both
                for m in merged:
                    if m.chunk_id == chunk.chunk_id:
                        m.relevance_score += chunk.relevance_score * symbol_weight
                        break
            else:
                chunk.relevance_score *= symbol_weight
                merged.append(chunk)
                seen_ids.add(chunk.chunk_id)

        # Sort by combined score and limit
        merged.sort(key=lambda c: c.relevance_score, reverse=True)
        chunks = merged[:limit]

        return ContextResult(
            chunks=chunks,
            total_tokens=self._estimate_tokens(chunks),
            query_type="hybrid_search",
        )

    def _row_to_chunk(self, row) -> ContextChunk:
        return ContextChunk(
            chunk_id=row['chunk_id'],
            file_path=row['file_path'],
            language=row['language'],
            content=row['content'],
            node_type=row['node_type'],
            start_line=row['start_line'],
            end_line=row['end_line'],
            parent_context=row['parent_context'],
            parent_route=row['parent_route'] or [],
            relevance_score=float(row['relevance']),
            metadata=row['metadata'] or {},
        )

    def _estimate_tokens(self, chunks: list[ContextChunk]) -> int:
        """Rough token estimate (4 chars ≈ 1 token)."""
        return sum(len(c.content) // 4 for c in chunks)
```

### AI Agent API Endpoints

```python
# api/agent_routes.py

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from services.context_service import AIContextService, ContextResult


router = APIRouter(prefix="/agent", tags=["AI Agent Context"])


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., description="Natural language query")
    repository_id: str | None = None
    languages: list[str] | None = None
    limit: int = Field(default=10, le=50)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class SymbolSearchRequest(BaseModel):
    symbol_name: str
    repository_id: str | None = None
    kind: str | None = Field(None, description="function, class, method, etc.")
    fuzzy: bool = False
    limit: int = Field(default=10, le=50)


class RelatedCodeRequest(BaseModel):
    chunk_id: str
    relationship_types: list[str] | None = None
    direction: str = Field(default="both", pattern="^(incoming|outgoing|both)$")
    depth: int = Field(default=1, ge=1, le=5)
    limit: int = Field(default=20, le=100)


class HybridSearchRequest(BaseModel):
    query: str
    repository_id: str | None = None
    semantic_weight: float = Field(default=0.7, ge=0.0, le=1.0)
    symbol_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    limit: int = Field(default=10, le=50)


@router.post("/search/semantic", response_model=ContextResult)
async def semantic_search(
    request: SemanticSearchRequest,
    context_service: AIContextService = Depends(),
):
    """
    Semantic code search using vector similarity.

    Best for natural language queries like:
    - "authentication logic"
    - "database error handling"
    - "API rate limiting"
    """
    return await context_service.semantic_search(
        query=request.query,
        repository_id=request.repository_id,
        languages=request.languages,
        limit=request.limit,
        similarity_threshold=request.similarity_threshold,
    )


@router.post("/search/symbol", response_model=ContextResult)
async def symbol_search(
    request: SymbolSearchRequest,
    context_service: AIContextService = Depends(),
):
    """
    Find code by symbol/function/class name.

    Best for specific lookups like:
    - "UserService"
    - "authenticate"
    - "handleRequest"
    """
    return await context_service.find_symbol(
        symbol_name=request.symbol_name,
        repository_id=request.repository_id,
        kind=request.kind,
        fuzzy=request.fuzzy,
        limit=request.limit,
    )


@router.post("/related", response_model=ContextResult)
async def get_related_code(
    request: RelatedCodeRequest,
    context_service: AIContextService = Depends(),
):
    """
    Find code related to a specific chunk via the dependency graph.

    Use after finding a chunk to explore:
    - What calls this function?
    - What does this depend on?
    - What inherits from this class?
    """
    return await context_service.get_related_code(
        chunk_id=request.chunk_id,
        relationship_types=request.relationship_types,
        direction=request.direction,
        depth=request.depth,
        limit=request.limit,
    )


@router.post("/search/hybrid", response_model=ContextResult)
async def hybrid_search(
    request: HybridSearchRequest,
    context_service: AIContextService = Depends(),
):
    """
    Combined semantic + symbol search.

    Best general-purpose search for AI agents.
    """
    return await context_service.hybrid_search(
        query=request.query,
        repository_id=request.repository_id,
        semantic_weight=request.semantic_weight,
        symbol_weight=request.symbol_weight,
        limit=request.limit,
    )


@router.get("/file/{repository_id}/{file_path:path}", response_model=ContextResult)
async def get_file_context(
    repository_id: str,
    file_path: str,
    node_types: list[str] = Query(default=None),
    context_service: AIContextService = Depends(),
):
    """
    Get all chunks from a specific file.
    """
    return await context_service.get_file_chunks(
        file_path=file_path,
        repository_id=repository_id,
        node_types=node_types,
    )
```

### Real-time Frontend Subscription (Supabase)

```typescript
// frontend/src/hooks/useRealtimeCode.ts

import { useEffect, useState, useCallback } from 'react';
import { createClient, RealtimeChannel } from '@supabase/supabase-js';
import type { ASTNode, CodeChunk } from '../types/ast';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

interface UseRealtimeCodeOptions {
  repositoryId: string;
  filePath?: string;
}

interface RealtimeCodeState {
  file: {
    id: string;
    path: string;
    content: string;
    language: string;
  } | null;
  chunks: CodeChunk[];
  loading: boolean;
  error: Error | null;
}

export function useRealtimeCode({ repositoryId, filePath }: UseRealtimeCodeOptions) {
  const [state, setState] = useState<RealtimeCodeState>({
    file: null,
    chunks: [],
    loading: true,
    error: null,
  });

  // Subscribe to file changes
  useEffect(() => {
    if (!filePath) return;

    let channel: RealtimeChannel;

    const setupSubscription = async () => {
      // Initial fetch
      const { data: file, error: fileError } = await supabase
        .from('files')
        .select('id, path, content, language')
        .eq('repository_id', repositoryId)
        .eq('path', filePath)
        .single();

      if (fileError) {
        setState(prev => ({ ...prev, error: fileError, loading: false }));
        return;
      }

      // Fetch chunks for this file
      const { data: chunks, error: chunksError } = await supabase
        .from('chunks')
        .select('*')
        .eq('file_id', file.id)
        .order('start_line');

      if (chunksError) {
        setState(prev => ({ ...prev, error: chunksError, loading: false }));
        return;
      }

      setState({
        file,
        chunks: chunks.map(transformChunk),
        loading: false,
        error: null,
      });

      // Subscribe to real-time updates
      channel = supabase
        .channel(`file:${file.id}`)
        .on(
          'postgres_changes',
          {
            event: '*',
            schema: 'public',
            table: 'files',
            filter: `id=eq.${file.id}`,
          },
          (payload) => {
            if (payload.eventType === 'UPDATE') {
              setState(prev => ({
                ...prev,
                file: payload.new as any,
              }));
            }
          }
        )
        .on(
          'postgres_changes',
          {
            event: '*',
            schema: 'public',
            table: 'chunks',
            filter: `file_id=eq.${file.id}`,
          },
          async () => {
            // Refetch all chunks on any change
            const { data } = await supabase
              .from('chunks')
              .select('*')
              .eq('file_id', file.id)
              .order('start_line');

            if (data) {
              setState(prev => ({
                ...prev,
                chunks: data.map(transformChunk),
              }));
            }
          }
        )
        .subscribe();
    };

    setupSubscription();

    return () => {
      if (channel) {
        supabase.removeChannel(channel);
      }
    };
  }, [repositoryId, filePath]);

  // Update file content (triggers re-indexing on backend)
  const updateContent = useCallback(
    async (newContent: string) => {
      if (!state.file) return;

      // Call backend API to update (this triggers the indexing pipeline)
      const response = await fetch('/api/files/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          repository_id: repositoryId,
          file_path: filePath,
          content: newContent,
          language: state.file.language,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to update file');
      }

      // The real-time subscription will automatically update the state
    },
    [state.file, repositoryId, filePath]
  );

  return {
    ...state,
    updateContent,
  };
}

function transformChunk(row: any): CodeChunk {
  return {
    id: row.chunk_id,
    node_type: row.node_type,
    content: row.content,
    start_line: row.start_line,
    end_line: row.end_line,
    parent_context: row.parent_context,
    parent_route: row.parent_route || [],
    metadata: row.metadata || {},
  };
}
```

### Updated Dependencies for Platform Architecture

```toml
# pyproject.toml for Code Intelligence Platform

[project]
name = "code-intelligence-platform"
version = "0.1.0"
dependencies = [
    # Core parsing
    "treesitter-chunker>=2.0.1",

    # API
    "fastapi>=0.100.0",
    "uvicorn>=0.22.0",
    "pydantic>=2.0",

    # Database
    "asyncpg>=0.28.0",          # Async PostgreSQL
    "pgvector>=0.2.0",          # Vector operations

    # Embeddings
    "openai>=1.0.0",            # OpenAI API
    # OR for local embeddings:
    # "sentence-transformers>=2.2.0",

    # Background tasks
    "celery>=5.3.0",            # Task queue
    "redis>=5.0.0",             # Celery backend

    # Utilities
    "httpx>=0.24.0",            # Async HTTP
    "tenacity>=8.0.0",          # Retries
]
```

### Docker Compose for Full Platform

```yaml
# docker-compose.yml

version: '3.8'

services:
  # PostgreSQL with pgvector
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: codebase
      POSTGRES_USER: codebase
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U codebase"]
      interval: 5s
      timeout: 5s
      retries: 5

  # Redis for Celery
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  # API Server
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql://codebase:${POSTGRES_PASSWORD}@postgres:5432/codebase
      REDIS_URL: redis://redis:6379/0
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    volumes:
      - grammar_cache:/root/.cache/treesitter-chunker

  # Indexing Worker
  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A worker worker --loglevel=info
    environment:
      DATABASE_URL: postgresql://codebase:${POSTGRES_PASSWORD}@postgres:5432/codebase
      REDIS_URL: redis://redis:6379/0
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    depends_on:
      - postgres
      - redis
    volumes:
      - grammar_cache:/root/.cache/treesitter-chunker

  # Frontend
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
      NEXT_PUBLIC_SUPABASE_URL: ${SUPABASE_URL}
      NEXT_PUBLIC_SUPABASE_ANON_KEY: ${SUPABASE_ANON_KEY}
    ports:
      - "3000:3000"
    depends_on:
      - api

volumes:
  postgres_data:
  redis_data:
  grammar_cache:
```

### Human-in-the-Loop Context Augmentation

A critical feature for collaborative AI-human systems is allowing humans to **augment context** by interacting with the code visualization. This creates a feedback loop where human expertise enhances AI understanding.

#### Interaction Model

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        HUMAN CONTEXT AUGMENTATION                            │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      VISUAL INTERACTIONS                             │   │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │   │
│   │  │   CLICK     │  │  MULTI-     │  │   LASSO     │  │  EXPAND/   │ │   │
│   │  │  (select)   │  │  SELECT     │  │  (region)   │  │  COLLAPSE  │ │   │
│   │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬──────┘ │   │
│   └─────────┼────────────────┼────────────────┼────────────────┼─────────┘   │
│             │                │                │                │             │
│             └────────────────┴────────────────┴────────────────┘             │
│                                      │                                       │
│                                      ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    CONTEXT ACTIONS                                   │   │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │   │
│   │  │  ANNOTATE   │  │    TAG      │  │   DISCUSS   │  │    PIN     │ │   │
│   │  │  "This is   │  │  #critical  │  │  "How does  │  │  (persist) │ │   │
│   │  │   the auth  │  │  #security  │  │   this      │  │            │ │   │
│   │  │   entry"    │  │  #tech-debt │  │   work?"    │  │            │ │   │
│   │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│                                      ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    STORED IN DATABASE                                │   │
│   │                                                                      │   │
│   │   annotations, selections, conversations, pins → chunks linkage     │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│                                      ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                 AVAILABLE TO AI AGENTS                               │   │
│   │                                                                      │   │
│   │   "What has the team flagged as security-critical?"                 │   │
│   │   "Show me code the humans discussed recently"                      │   │
│   │   "What context did the developer provide about auth?"              │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Extended Database Schema for Human Context

```sql
-- Human annotations on code chunks
CREATE TABLE annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id UUID REFERENCES chunks(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,  -- Who created this

    -- Annotation content
    content TEXT NOT NULL,
    annotation_type TEXT NOT NULL,  -- 'note', 'question', 'explanation', 'warning'

    -- Position within chunk (optional, for inline annotations)
    start_offset INTEGER,  -- Byte offset within chunk
    end_offset INTEGER,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_resolved BOOLEAN DEFAULT FALSE  -- For questions/issues
);

CREATE INDEX idx_annotations_chunk ON annotations(chunk_id);
CREATE INDEX idx_annotations_user ON annotations(user_id);
CREATE INDEX idx_annotations_type ON annotations(annotation_type);

-- Tags for categorization (many-to-many with chunks)
CREATE TABLE tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    color TEXT,  -- Hex color for UI
    description TEXT,
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE chunk_tags (
    chunk_id UUID REFERENCES chunks(id) ON DELETE CASCADE,
    tag_id UUID REFERENCES tags(id) ON DELETE CASCADE,
    tagged_by UUID NOT NULL,
    tagged_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (chunk_id, tag_id)
);

CREATE INDEX idx_chunk_tags_tag ON chunk_tags(tag_id);

-- Saved selections (pinned context sets)
CREATE TABLE selections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    name TEXT NOT NULL,
    description TEXT,

    -- Selection can be shared
    is_public BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE selection_chunks (
    selection_id UUID REFERENCES selections(id) ON DELETE CASCADE,
    chunk_id UUID REFERENCES chunks(id) ON DELETE CASCADE,

    -- Order and notes for this chunk in the selection
    position INTEGER NOT NULL,
    note TEXT,  -- Why this chunk is included

    PRIMARY KEY (selection_id, chunk_id)
);

-- Conversations attached to code
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT,

    -- Can be attached to a chunk, file, or selection
    chunk_id UUID REFERENCES chunks(id) ON DELETE SET NULL,
    file_id UUID REFERENCES files(id) ON DELETE SET NULL,
    selection_id UUID REFERENCES selections(id) ON DELETE SET NULL,

    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_resolved BOOLEAN DEFAULT FALSE
);

CREATE TABLE conversation_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    user_id UUID,  -- NULL for AI responses

    role TEXT NOT NULL,  -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,

    -- Messages can reference specific chunks
    referenced_chunks UUID[],

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_conversations_chunk ON conversations(chunk_id);
CREATE INDEX idx_conversations_file ON conversations(file_id);
CREATE INDEX idx_conv_messages_conv ON conversation_messages(conversation_id);

-- Embeddings for annotations (for semantic search of human context)
CREATE TABLE annotation_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    annotation_id UUID REFERENCES annotations(id) ON DELETE CASCADE,
    embedding vector(1536) NOT NULL,
    model TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(annotation_id, model)
);

CREATE INDEX idx_annotation_embeddings_vector ON annotation_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);
```

#### Context Augmentation Service

```python
# services/context_augmentation_service.py

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import asyncpg
from openai import AsyncOpenAI


@dataclass
class Annotation:
    id: str
    chunk_id: str
    user_id: str
    content: str
    annotation_type: str
    created_at: datetime


@dataclass
class Selection:
    id: str
    name: str
    description: str | None
    chunk_ids: list[str]
    notes: dict[str, str]  # chunk_id -> note


@dataclass
class ConversationContext:
    conversation_id: str
    messages: list[dict]
    referenced_chunks: list[str]
    attached_to: dict  # {"type": "chunk"|"file"|"selection", "id": "..."}


class ContextAugmentationService:
    """
    Service for managing human-provided context augmentation.

    Humans can:
    - Annotate code chunks with notes, questions, explanations
    - Tag chunks for categorization
    - Create saved selections (pinned context sets)
    - Have conversations attached to code
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        openai_client: AsyncOpenAI,
        embedding_model: str = "text-embedding-3-small",
    ):
        self.db = db_pool
        self.openai = openai_client
        self.embedding_model = embedding_model

    # --- Annotations ---

    async def create_annotation(
        self,
        chunk_id: str,
        user_id: str,
        content: str,
        annotation_type: Literal["note", "question", "explanation", "warning"],
        start_offset: int | None = None,
        end_offset: int | None = None,
    ) -> Annotation:
        """Add a human annotation to a code chunk."""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO annotations
                    (chunk_id, user_id, content, annotation_type, start_offset, end_offset)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id, created_at
                """,
                chunk_id, user_id, content, annotation_type, start_offset, end_offset
            )

            annotation_id = row['id']

            # Generate and store embedding for the annotation
            embedding_response = await self.openai.embeddings.create(
                model=self.embedding_model,
                input=content,
            )

            await conn.execute(
                """
                INSERT INTO annotation_embeddings (annotation_id, embedding, model)
                VALUES ($1, $2, $3)
                """,
                annotation_id,
                embedding_response.data[0].embedding,
                self.embedding_model,
            )

            return Annotation(
                id=str(annotation_id),
                chunk_id=chunk_id,
                user_id=user_id,
                content=content,
                annotation_type=annotation_type,
                created_at=row['created_at'],
            )

    async def get_annotations_for_chunk(
        self,
        chunk_id: str,
    ) -> list[Annotation]:
        """Get all annotations for a specific chunk."""
        async with self.db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, chunk_id, user_id, content, annotation_type, created_at
                FROM annotations
                WHERE chunk_id = $1
                ORDER BY created_at DESC
                """,
                chunk_id
            )

        return [
            Annotation(
                id=str(row['id']),
                chunk_id=str(row['chunk_id']),
                user_id=str(row['user_id']),
                content=row['content'],
                annotation_type=row['annotation_type'],
                created_at=row['created_at'],
            )
            for row in rows
        ]

    # --- Tags ---

    async def tag_chunk(
        self,
        chunk_id: str,
        tag_name: str,
        user_id: str,
    ) -> None:
        """Add a tag to a chunk."""
        async with self.db.acquire() as conn:
            # Get or create tag
            tag_id = await conn.fetchval(
                """
                INSERT INTO tags (name, created_by)
                VALUES ($1, $2)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
                """,
                tag_name.lower(), user_id
            )

            # Link tag to chunk
            await conn.execute(
                """
                INSERT INTO chunk_tags (chunk_id, tag_id, tagged_by)
                VALUES ($1, $2, $3)
                ON CONFLICT DO NOTHING
                """,
                chunk_id, tag_id, user_id
            )

    async def get_chunks_by_tag(
        self,
        tag_name: str,
        repository_id: str | None = None,
    ) -> list[dict]:
        """Get all chunks with a specific tag."""
        async with self.db.acquire() as conn:
            sql = """
                SELECT
                    c.id::text as chunk_id,
                    c.content,
                    c.node_type,
                    f.path as file_path,
                    c.start_line,
                    c.end_line
                FROM chunk_tags ct
                JOIN tags t ON t.id = ct.tag_id
                JOIN chunks c ON c.id = ct.chunk_id
                JOIN files f ON f.id = c.file_id
                WHERE LOWER(t.name) = LOWER($1)
            """
            params = [tag_name]

            if repository_id:
                sql += " AND f.repository_id = $2"
                params.append(repository_id)

            rows = await conn.fetch(sql, *params)

        return [dict(row) for row in rows]

    # --- Selections (Pinned Context Sets) ---

    async def create_selection(
        self,
        user_id: str,
        name: str,
        chunk_ids: list[str],
        description: str | None = None,
        notes: dict[str, str] | None = None,
    ) -> Selection:
        """Create a saved selection of chunks."""
        notes = notes or {}

        async with self.db.acquire() as conn:
            async with conn.transaction():
                selection_id = await conn.fetchval(
                    """
                    INSERT INTO selections (user_id, name, description)
                    VALUES ($1, $2, $3)
                    RETURNING id
                    """,
                    user_id, name, description
                )

                for position, chunk_id in enumerate(chunk_ids):
                    await conn.execute(
                        """
                        INSERT INTO selection_chunks (selection_id, chunk_id, position, note)
                        VALUES ($1, $2, $3, $4)
                        """,
                        selection_id, chunk_id, position, notes.get(chunk_id)
                    )

        return Selection(
            id=str(selection_id),
            name=name,
            description=description,
            chunk_ids=chunk_ids,
            notes=notes,
        )

    async def get_selection(self, selection_id: str) -> Selection | None:
        """Get a saved selection by ID."""
        async with self.db.acquire() as conn:
            selection_row = await conn.fetchrow(
                "SELECT id, name, description FROM selections WHERE id = $1",
                selection_id
            )

            if not selection_row:
                return None

            chunk_rows = await conn.fetch(
                """
                SELECT chunk_id::text, note
                FROM selection_chunks
                WHERE selection_id = $1
                ORDER BY position
                """,
                selection_id
            )

        return Selection(
            id=str(selection_row['id']),
            name=selection_row['name'],
            description=selection_row['description'],
            chunk_ids=[row['chunk_id'] for row in chunk_rows],
            notes={row['chunk_id']: row['note'] for row in chunk_rows if row['note']},
        )

    # --- Conversations ---

    async def create_conversation(
        self,
        user_id: str,
        title: str | None = None,
        chunk_id: str | None = None,
        file_id: str | None = None,
        selection_id: str | None = None,
    ) -> str:
        """Start a conversation attached to code."""
        async with self.db.acquire() as conn:
            conversation_id = await conn.fetchval(
                """
                INSERT INTO conversations (title, chunk_id, file_id, selection_id, created_by)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                title, chunk_id, file_id, selection_id, user_id
            )

        return str(conversation_id)

    async def add_message(
        self,
        conversation_id: str,
        role: Literal["user", "assistant", "system"],
        content: str,
        user_id: str | None = None,
        referenced_chunks: list[str] | None = None,
    ) -> str:
        """Add a message to a conversation."""
        async with self.db.acquire() as conn:
            message_id = await conn.fetchval(
                """
                INSERT INTO conversation_messages
                    (conversation_id, user_id, role, content, referenced_chunks)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                conversation_id, user_id, role, content, referenced_chunks
            )

            # Update conversation timestamp
            await conn.execute(
                "UPDATE conversations SET updated_at = NOW() WHERE id = $1",
                conversation_id
            )

        return str(message_id)

    async def get_conversation_context(
        self,
        conversation_id: str,
    ) -> ConversationContext | None:
        """Get full conversation context for AI."""
        async with self.db.acquire() as conn:
            conv_row = await conn.fetchrow(
                """
                SELECT id, chunk_id, file_id, selection_id
                FROM conversations
                WHERE id = $1
                """,
                conversation_id
            )

            if not conv_row:
                return None

            message_rows = await conn.fetch(
                """
                SELECT role, content, referenced_chunks
                FROM conversation_messages
                WHERE conversation_id = $1
                ORDER BY created_at
                """,
                conversation_id
            )

        # Determine what the conversation is attached to
        attached_to = {}
        if conv_row['chunk_id']:
            attached_to = {"type": "chunk", "id": str(conv_row['chunk_id'])}
        elif conv_row['file_id']:
            attached_to = {"type": "file", "id": str(conv_row['file_id'])}
        elif conv_row['selection_id']:
            attached_to = {"type": "selection", "id": str(conv_row['selection_id'])}

        # Collect all referenced chunks
        all_referenced = set()
        messages = []
        for row in message_rows:
            messages.append({
                "role": row['role'],
                "content": row['content'],
            })
            if row['referenced_chunks']:
                all_referenced.update(row['referenced_chunks'])

        return ConversationContext(
            conversation_id=str(conv_row['id']),
            messages=messages,
            referenced_chunks=list(all_referenced),
            attached_to=attached_to,
        )
```

#### AI Agent Access to Human Context

```python
# services/context_service.py (extended)

class AIContextService:
    # ... previous methods ...

    async def search_annotations(
        self,
        query: str,
        repository_id: str | None = None,
        annotation_types: list[str] | None = None,
        limit: int = 10,
    ) -> ContextResult:
        """
        Search human annotations semantically.

        Use for:
        - "What has the team noted about authentication?"
        - "Show me questions developers asked about this code"
        - "Find warnings about security"
        """
        # Generate query embedding
        response = await self.openai.embeddings.create(
            model=self.embedding_model,
            input=query,
        )
        query_embedding = response.data[0].embedding

        sql = """
            SELECT
                c.id::text as chunk_id,
                f.path as file_path,
                f.language,
                c.content,
                c.node_type,
                c.start_line,
                c.end_line,
                c.parent_context,
                c.parent_route,
                c.metadata,
                a.content as annotation,
                a.annotation_type,
                1 - (ae.embedding <=> $1::vector) as similarity
            FROM annotation_embeddings ae
            JOIN annotations a ON a.id = ae.annotation_id
            JOIN chunks c ON c.id = a.chunk_id
            JOIN files f ON f.id = c.file_id
            WHERE 1 - (ae.embedding <=> $1::vector) > 0.6
        """
        params = [query_embedding]
        param_idx = 2

        if repository_id:
            sql += f" AND f.repository_id = ${param_idx}"
            params.append(repository_id)
            param_idx += 1

        if annotation_types:
            sql += f" AND a.annotation_type = ANY(${param_idx})"
            params.append(annotation_types)
            param_idx += 1

        sql += f" ORDER BY similarity DESC LIMIT ${param_idx}"
        params.append(limit)

        async with self.db.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        chunks = []
        for row in rows:
            chunk = self._row_to_chunk(row)
            # Enrich with annotation data
            chunk.metadata['annotation'] = {
                'content': row['annotation'],
                'type': row['annotation_type'],
            }
            chunks.append(chunk)

        return ContextResult(
            chunks=chunks,
            total_tokens=self._estimate_tokens(chunks),
            query_type="annotation_search",
        )

    async def get_tagged_context(
        self,
        tags: list[str],
        repository_id: str | None = None,
        limit: int = 50,
    ) -> ContextResult:
        """
        Get code chunks by human-assigned tags.

        Use for:
        - "Show me all #security-critical code"
        - "What's tagged as #needs-review?"
        - "Find #api-endpoints"
        """
        sql = """
            SELECT DISTINCT
                c.id::text as chunk_id,
                f.path as file_path,
                f.language,
                c.content,
                c.node_type,
                c.start_line,
                c.end_line,
                c.parent_context,
                c.parent_route,
                c.metadata,
                array_agg(t.name) as tags,
                1.0 as relevance
            FROM chunk_tags ct
            JOIN tags t ON t.id = ct.tag_id
            JOIN chunks c ON c.id = ct.chunk_id
            JOIN files f ON f.id = c.file_id
            WHERE LOWER(t.name) = ANY($1)
        """
        params = [[tag.lower() for tag in tags]]
        param_idx = 2

        if repository_id:
            sql += f" AND f.repository_id = ${param_idx}"
            params.append(repository_id)
            param_idx += 1

        sql += """
            GROUP BY c.id, f.path, f.language, c.content, c.node_type,
                     c.start_line, c.end_line, c.parent_context, c.parent_route, c.metadata
            LIMIT $""" + str(param_idx)
        params.append(limit)

        async with self.db.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        chunks = []
        for row in rows:
            chunk = self._row_to_chunk(row)
            chunk.metadata['tags'] = row['tags']
            chunks.append(chunk)

        return ContextResult(
            chunks=chunks,
            total_tokens=self._estimate_tokens(chunks),
            query_type="tagged_context",
        )

    async def get_selection_context(
        self,
        selection_id: str,
    ) -> ContextResult:
        """
        Get all chunks in a human-curated selection.

        Use when humans have pre-selected relevant context.
        """
        sql = """
            SELECT
                c.id::text as chunk_id,
                f.path as file_path,
                f.language,
                c.content,
                c.node_type,
                c.start_line,
                c.end_line,
                c.parent_context,
                c.parent_route,
                c.metadata,
                sc.note as selection_note,
                sc.position,
                1.0 as relevance
            FROM selection_chunks sc
            JOIN chunks c ON c.id = sc.chunk_id
            JOIN files f ON f.id = c.file_id
            WHERE sc.selection_id = $1
            ORDER BY sc.position
        """

        async with self.db.acquire() as conn:
            rows = await conn.fetch(sql, selection_id)

        chunks = []
        for row in rows:
            chunk = self._row_to_chunk(row)
            if row['selection_note']:
                chunk.metadata['selection_note'] = row['selection_note']
            chunks.append(chunk)

        return ContextResult(
            chunks=chunks,
            total_tokens=self._estimate_tokens(chunks),
            query_type="selection_context",
        )

    async def get_conversation_with_code(
        self,
        conversation_id: str,
    ) -> dict:
        """
        Get a conversation with all its referenced code.

        Returns conversation history plus the code chunks
        that were discussed.
        """
        async with self.db.acquire() as conn:
            # Get conversation and messages
            conv_row = await conn.fetchrow(
                """
                SELECT c.id, c.title, c.chunk_id, c.file_id, c.selection_id
                FROM conversations c
                WHERE c.id = $1
                """,
                conversation_id
            )

            if not conv_row:
                return None

            messages = await conn.fetch(
                """
                SELECT role, content, referenced_chunks
                FROM conversation_messages
                WHERE conversation_id = $1
                ORDER BY created_at
                """,
                conversation_id
            )

            # Collect all referenced chunk IDs
            referenced_ids = set()
            if conv_row['chunk_id']:
                referenced_ids.add(str(conv_row['chunk_id']))

            for msg in messages:
                if msg['referenced_chunks']:
                    referenced_ids.update(msg['referenced_chunks'])

            # Fetch the actual chunks
            if referenced_ids:
                chunks = await conn.fetch(
                    """
                    SELECT
                        c.id::text as chunk_id,
                        f.path as file_path,
                        c.content,
                        c.node_type,
                        c.start_line,
                        c.end_line
                    FROM chunks c
                    JOIN files f ON f.id = c.file_id
                    WHERE c.id = ANY($1::uuid[])
                    """,
                    list(referenced_ids)
                )
            else:
                chunks = []

        return {
            "conversation_id": str(conv_row['id']),
            "title": conv_row['title'],
            "messages": [
                {"role": m['role'], "content": m['content']}
                for m in messages
            ],
            "referenced_code": [dict(c) for c in chunks],
        }
```

#### Frontend Components for Context Augmentation

```tsx
// frontend/src/components/ContextAugmentation/AnnotationPanel.tsx

import { useState } from 'react';
import { useASTStore } from '../../stores/astStore';

interface AnnotationPanelProps {
  chunkId: string;
  onClose: () => void;
}

export function AnnotationPanel({ chunkId, onClose }: AnnotationPanelProps) {
  const [content, setContent] = useState('');
  const [type, setType] = useState<'note' | 'question' | 'explanation' | 'warning'>('note');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      await fetch('/api/annotations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chunk_id: chunkId,
          content,
          annotation_type: type,
        }),
      });
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="annotation-panel">
      <h4>Add Annotation</h4>

      <div className="annotation-type-selector">
        {(['note', 'question', 'explanation', 'warning'] as const).map((t) => (
          <button
            key={t}
            className={`type-btn ${type === t ? 'active' : ''}`}
            onClick={() => setType(t)}
          >
            {t === 'note' && '📝'}
            {t === 'question' && '❓'}
            {t === 'explanation' && '💡'}
            {t === 'warning' && '⚠️'}
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder={
          type === 'note' ? 'Add a note about this code...' :
          type === 'question' ? 'What would you like to know?' :
          type === 'explanation' ? 'Explain what this code does...' :
          'What should others watch out for?'
        }
        rows={4}
      />

      <div className="annotation-actions">
        <button onClick={onClose}>Cancel</button>
        <button
          onClick={handleSubmit}
          disabled={!content.trim() || isSubmitting}
          className="primary"
        >
          {isSubmitting ? 'Saving...' : 'Save Annotation'}
        </button>
      </div>
    </div>
  );
}
```

```tsx
// frontend/src/components/ContextAugmentation/SelectionBuilder.tsx

import { useState, useCallback } from 'react';
import type { CodeChunk } from '../../types/ast';

interface SelectionBuilderProps {
  selectedChunks: CodeChunk[];
  onSave: (name: string, description: string, notes: Record<string, string>) => void;
  onClear: () => void;
}

export function SelectionBuilder({
  selectedChunks,
  onSave,
  onClear
}: SelectionBuilderProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [isExpanded, setIsExpanded] = useState(true);

  const handleNoteChange = useCallback((chunkId: string, note: string) => {
    setNotes(prev => ({ ...prev, [chunkId]: note }));
  }, []);

  if (selectedChunks.length === 0) {
    return (
      <div className="selection-builder empty">
        <p>Click chunks in the tree or editor to build a context selection</p>
        <p className="hint">Hold Cmd/Ctrl to multi-select</p>
      </div>
    );
  }

  return (
    <div className="selection-builder">
      <div className="selection-header">
        <h4>Context Selection ({selectedChunks.length} items)</h4>
        <button onClick={() => setIsExpanded(!isExpanded)}>
          {isExpanded ? '▼' : '▶'}
        </button>
      </div>

      {isExpanded && (
        <>
          <div className="selection-items">
            {selectedChunks.map((chunk, index) => (
              <div key={chunk.id} className="selection-item">
                <div className="item-header">
                  <span className="item-number">{index + 1}</span>
                  <span className="item-type">{chunk.node_type}</span>
                  <span className="item-location">
                    {chunk.parent_route.join(' → ')}
                  </span>
                </div>
                <input
                  type="text"
                  placeholder="Why is this relevant? (optional)"
                  value={notes[chunk.id] || ''}
                  onChange={(e) => handleNoteChange(chunk.id, e.target.value)}
                />
              </div>
            ))}
          </div>

          <div className="selection-save">
            <input
              type="text"
              placeholder="Selection name..."
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <textarea
              placeholder="Description (optional)..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
            />
            <div className="save-actions">
              <button onClick={onClear}>Clear</button>
              <button
                onClick={() => onSave(name, description, notes)}
                disabled={!name.trim()}
                className="primary"
              >
                Save Selection
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
```

```tsx
// frontend/src/components/ContextAugmentation/CodeConversation.tsx

import { useState, useEffect, useRef } from 'react';
import type { CodeChunk } from '../../types/ast';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  referencedChunks?: string[];
}

interface CodeConversationProps {
  attachedTo: {
    type: 'chunk' | 'file' | 'selection';
    id: string;
    name?: string;
  };
  initialContext?: CodeChunk[];
}

export function CodeConversation({ attachedTo, initialContext }: CodeConversationProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Initialize conversation
  useEffect(() => {
    const initConversation = async () => {
      const response = await fetch('/api/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          [`${attachedTo.type}_id`]: attachedTo.id,
          title: `Discussion: ${attachedTo.name || attachedTo.id}`,
        }),
      });
      const data = await response.json();
      setConversationId(data.id);
    };

    initConversation();
  }, [attachedTo]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || !conversationId) return;

    const userMessage: Message = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // Send message to backend (which will query AI with code context)
      const response = await fetch(`/api/conversations/${conversationId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          role: 'user',
          content: input,
          referenced_chunks: initialContext?.map(c => c.id),
        }),
      });

      const data = await response.json();

      // Add AI response
      const assistantMessage: Message = {
        role: 'assistant',
        content: data.response,
        referencedChunks: data.referenced_chunks,
      };
      setMessages(prev => [...prev, assistantMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="code-conversation">
      <div className="conversation-header">
        <h4>Discussion</h4>
        <span className="attached-to">
          Attached to: {attachedTo.type} - {attachedTo.name || attachedTo.id}
        </span>
      </div>

      <div className="conversation-messages">
        {initialContext && initialContext.length > 0 && (
          <div className="context-summary">
            <strong>Context:</strong> {initialContext.length} code chunks selected
          </div>
        )}

        {messages.map((msg, index) => (
          <div key={index} className={`message ${msg.role}`}>
            <div className="message-content">{msg.content}</div>
            {msg.referencedChunks && msg.referencedChunks.length > 0 && (
              <div className="referenced-chunks">
                Referenced {msg.referencedChunks.length} code chunks
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="message assistant loading">
            Thinking...
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="conversation-input">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about this code..."
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
        />
        <button onClick={handleSend} disabled={isLoading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}
```

#### Updated State Management for Selections

```typescript
// frontend/src/stores/selectionStore.ts

import { create } from 'zustand';
import type { CodeChunk } from '../types/ast';

interface SelectionState {
  // Currently selected chunks (for building a selection)
  selectedChunks: CodeChunk[];

  // Saved selections
  savedSelections: Array<{
    id: string;
    name: string;
    chunkCount: number;
  }>;

  // Actions
  toggleChunkSelection: (chunk: CodeChunk) => void;
  addToSelection: (chunk: CodeChunk) => void;
  removeFromSelection: (chunkId: string) => void;
  clearSelection: () => void;

  // Multi-select with Cmd/Ctrl
  isMultiSelectMode: boolean;
  setMultiSelectMode: (enabled: boolean) => void;
}

export const useSelectionStore = create<SelectionState>((set, get) => ({
  selectedChunks: [],
  savedSelections: [],
  isMultiSelectMode: false,

  toggleChunkSelection: (chunk) => {
    const { selectedChunks, isMultiSelectMode } = get();
    const exists = selectedChunks.some(c => c.id === chunk.id);

    if (exists) {
      set({ selectedChunks: selectedChunks.filter(c => c.id !== chunk.id) });
    } else if (isMultiSelectMode) {
      set({ selectedChunks: [...selectedChunks, chunk] });
    } else {
      set({ selectedChunks: [chunk] });
    }
  },

  addToSelection: (chunk) => {
    const { selectedChunks } = get();
    if (!selectedChunks.some(c => c.id === chunk.id)) {
      set({ selectedChunks: [...selectedChunks, chunk] });
    }
  },

  removeFromSelection: (chunkId) => {
    set({ selectedChunks: get().selectedChunks.filter(c => c.id !== chunkId) });
  },

  clearSelection: () => set({ selectedChunks: [] }),

  setMultiSelectMode: (enabled) => set({ isMultiSelectMode: enabled }),
}));

// Hook to handle keyboard modifiers
export function useMultiSelectKeyboard() {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Meta' || e.key === 'Control') {
        useSelectionStore.getState().setMultiSelectMode(true);
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.key === 'Meta' || e.key === 'Control') {
        useSelectionStore.getState().setMultiSelectMode(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, []);
}
```

#### API Routes for Human Context

```python
# api/context_routes.py

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from services.context_augmentation_service import ContextAugmentationService

router = APIRouter(prefix="/context", tags=["Human Context"])


class CreateAnnotationRequest(BaseModel):
    chunk_id: str
    content: str
    annotation_type: str
    start_offset: int | None = None
    end_offset: int | None = None


class TagChunkRequest(BaseModel):
    chunk_id: str
    tag_name: str


class CreateSelectionRequest(BaseModel):
    name: str
    description: str | None = None
    chunk_ids: list[str]
    notes: dict[str, str] | None = None


class CreateConversationRequest(BaseModel):
    title: str | None = None
    chunk_id: str | None = None
    file_id: str | None = None
    selection_id: str | None = None


class SendMessageRequest(BaseModel):
    role: str
    content: str
    referenced_chunks: list[str] | None = None


@router.post("/annotations")
async def create_annotation(
    request: CreateAnnotationRequest,
    user_id: str = Depends(get_current_user_id),
    service: ContextAugmentationService = Depends(),
):
    """Add an annotation to a code chunk."""
    return await service.create_annotation(
        chunk_id=request.chunk_id,
        user_id=user_id,
        content=request.content,
        annotation_type=request.annotation_type,
        start_offset=request.start_offset,
        end_offset=request.end_offset,
    )


@router.get("/annotations/{chunk_id}")
async def get_annotations(
    chunk_id: str,
    service: ContextAugmentationService = Depends(),
):
    """Get all annotations for a chunk."""
    return await service.get_annotations_for_chunk(chunk_id)


@router.post("/tags")
async def tag_chunk(
    request: TagChunkRequest,
    user_id: str = Depends(get_current_user_id),
    service: ContextAugmentationService = Depends(),
):
    """Add a tag to a chunk."""
    await service.tag_chunk(
        chunk_id=request.chunk_id,
        tag_name=request.tag_name,
        user_id=user_id,
    )
    return {"status": "tagged"}


@router.get("/tags/{tag_name}/chunks")
async def get_chunks_by_tag(
    tag_name: str,
    repository_id: str | None = None,
    service: ContextAugmentationService = Depends(),
):
    """Get all chunks with a specific tag."""
    return await service.get_chunks_by_tag(tag_name, repository_id)


@router.post("/selections")
async def create_selection(
    request: CreateSelectionRequest,
    user_id: str = Depends(get_current_user_id),
    service: ContextAugmentationService = Depends(),
):
    """Save a selection of chunks."""
    return await service.create_selection(
        user_id=user_id,
        name=request.name,
        description=request.description,
        chunk_ids=request.chunk_ids,
        notes=request.notes,
    )


@router.get("/selections/{selection_id}")
async def get_selection(
    selection_id: str,
    service: ContextAugmentationService = Depends(),
):
    """Get a saved selection."""
    return await service.get_selection(selection_id)


@router.post("/conversations")
async def create_conversation(
    request: CreateConversationRequest,
    user_id: str = Depends(get_current_user_id),
    service: ContextAugmentationService = Depends(),
):
    """Start a new conversation attached to code."""
    conversation_id = await service.create_conversation(
        user_id=user_id,
        title=request.title,
        chunk_id=request.chunk_id,
        file_id=request.file_id,
        selection_id=request.selection_id,
    )
    return {"id": conversation_id}


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    user_id: str = Depends(get_current_user_id),
    service: ContextAugmentationService = Depends(),
    ai_service: AIContextService = Depends(),
):
    """Send a message in a conversation and get AI response."""
    # Store user message
    await service.add_message(
        conversation_id=conversation_id,
        role="user",
        content=request.content,
        user_id=user_id,
        referenced_chunks=request.referenced_chunks,
    )

    # Get conversation context for AI
    context = await service.get_conversation_context(conversation_id)

    # Get relevant code chunks
    code_context = []
    if context.referenced_chunks:
        for chunk_id in context.referenced_chunks[:10]:  # Limit context
            chunk_result = await ai_service.get_chunk_by_id(chunk_id)
            if chunk_result:
                code_context.append(chunk_result)

    # Generate AI response (you'd integrate your LLM here)
    ai_response = await generate_ai_response(
        messages=context.messages,
        code_context=code_context,
    )

    # Store AI response
    await service.add_message(
        conversation_id=conversation_id,
        role="assistant",
        content=ai_response.content,
        referenced_chunks=ai_response.referenced_chunks,
    )

    return {
        "response": ai_response.content,
        "referenced_chunks": ai_response.referenced_chunks,
    }
```

### Summary: When to Use Each Architecture

| Architecture | Use Case | Complexity |
|--------------|----------|------------|
| **Part 1: WebSocket-based** | Single-user tool, learning, IDE extension | Low |
| **Part 2: DB-backed Platform** | Multi-user, AI agents, persistent analysis | Medium-High |

**Part 2 is the right choice when:**
- Code needs to persist across sessions
- Multiple consumers (humans + AI agents) need access
- Semantic search is required
- You're building a platform/service, not a tool
- Cross-repository analysis is needed
- You need audit trails or versioning

---

## Next Steps

1. **Clone the template**: Start with the project structure above
2. **Install treesitter-chunker**: `pip install treesitter-chunker>=2.0.1`
3. **Implement the backend services**: Start with `ASTService`
4. **Build the React frontend**: Start with `TreeView` component
5. **Add WebSocket support**: For real-time updates
6. **Iterate on features**: Use the feature matrix as a guide

### Useful Resources

- [treesitter-chunker Documentation](./README.md)
- [Tree-sitter Documentation](https://tree-sitter.github.io/tree-sitter/)
- [Monaco Editor React](https://github.com/suren-atoyan/monaco-react)
- [React Flow](https://reactflow.dev/) - For graph visualization
- [D3.js](https://d3js.org/) - Alternative visualization library

---

## Appendix: treesitter-chunker Quick Reference

### Core Functions

```python
from chunker import (
    # Parsing
    get_parser,           # Get tree-sitter parser for language
    list_languages,       # List available languages

    # Chunking
    chunk_file,           # Chunk a file
    chunk_text,           # Chunk source text

    # Graph
    build_xref,           # Build cross-reference graph
    graph_cut,            # Extract subgraph
)

from chunker.incremental import DefaultIncrementalProcessor
from chunker.types import CodeChunk
```

### CodeChunk Fields

```python
@dataclass
class CodeChunk:
    node_id: str          # Unique SHA1 identifier
    chunk_id: str         # Stable chunk ID
    language: str         # Language name
    file_path: str        # Source file
    node_type: str        # AST node type
    content: str          # Code content
    start_line: int       # 1-indexed
    end_line: int         # 1-indexed
    byte_start: int       # Byte offset
    byte_end: int         # Byte offset
    parent_context: str   # Parent scope name
    parent_route: list    # ["module", "Class", "method"]
    metadata: dict        # Rich metadata
```

### Supported Languages (Built-in)

Python, JavaScript, TypeScript, TSX, Rust, C, C++, Go, Java, Kotlin, Scala, Ruby, PHP, Swift, Dart, Haskell, OCaml, Elixir, Clojure, R, Julia, MATLAB, SQL, HTML, CSS, Vue, Svelte, YAML, TOML, JSON, XML, Dockerfile, NASM, WebAssembly, Zig, and more.

---

*This guide was generated for treesitter-chunker v2.0.1. Check the [repository](https://github.com/Consiliency/treesitter-chunker) for updates.*
