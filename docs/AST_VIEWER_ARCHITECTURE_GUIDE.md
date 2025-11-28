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
