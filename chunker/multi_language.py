"""Multi-language project processing implementation."""

from .chunker import chunk_file
from .parser import get_parser, list_languages
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from .interfaces.multi_language import (
    CrossLanguageReference,
    EmbeddedLanguageType,
    LanguageDetector,
    LanguageRegion,
    MultiLanguageProcessor,
    ProjectAnalyzer,
)
from .types import CodeChunk

# Conditional imports - these may not be available in test environment
try:
except ImportError:
    # Define stubs for testing
    def list_languages():
        return ["python", "javascript", "typescript", "java", "go", "rust", "c", "cpp"]

    def get_parser(_language):
        raise ImportError("Tree-sitter parser not available")

    def chunk_file(_file_path, _content, _language):
        raise ImportError("Chunker not available")


class LanguageDetectorImpl(LanguageDetector):
    """Detect programming languages in files and content."""

    # Language file_path extensions mapping
    EXTENSIONS = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
        ".rs": "rust",
        ".go": "go",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".r": "r",
        ".m": "objc",
        ".mm": "objc",
        ".cs": "csharp",
        ".vb": "vb",
        ".fs": "fsharp",
        ".ml": "ocaml",
        ".lua": "lua",
        ".pl": "perl",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "bash",
        ".fish": "bash",
        ".ps1": "powershell",
        ".psm1": "powershell",
        ".html": "html",
        ".htm": "html",
        ".xml": "xml",
        ".css": "css",
        ".scss": "scss",
        ".sass": "sass",
        ".less": "less",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".ini": "ini",
        ".cfg": "ini",
        ".md": "markdown",
        ".markdown": "markdown",
        ".rst": "rst",
        ".tex": "latex",
        ".sql": "sql",
        ".graphql": "graphql",
        ".gql": "graphql",
        ".ipynb": "jupyter",
    }

    # Shebang patterns
    SHEBANG_PATTERNS = {
        r"python[0-9\.]*": "python",
        r"node": "javascript",
        r"ruby": "ruby",
        r"perl": "perl",
        r"bash": "bash",
        r"sh": "bash",
        r"zsh": "bash",
        r"fish": "bash",
        r"lua": "lua",
        r"php": "php",
    }

    # Content patterns for language detection
    CONTENT_PATTERNS = {
        "python": [
            r"^\s*import\s+\w+(?:\s*,\s*\w+)*\s*$",  # Python imports don't end with semicolon
            r"^\s*from\s+[\w\.]+\s+import",
            r"^\s*def\s+\w+\s*\(",
            r"^\s*class\s+\w+\s*[:\(]",
            r'^\s*if\s+__name__\s*==\s*["\']__main__["\']',
            r"^\s*@\w+",  # Decorators
        ],
        "javascript": [
            r"^\s*const\s+\w+\s*=",
            r"^\s*let\s+\w+\s*=",
            r"^\s*var\s+\w+\s*=",
            r"^\s*function\s+\w+\s*\(",
            r"^\s*class\s+\w+\s*[\{]",
            r'^\s*import\s+.*\s+from\s+["\']',
            r"^\s*export\s+(default\s+)?",
        ],
        "typescript": [
            r"^\s*interface\s+\w+\s*[\{]",
            r"^\s*type\s+\w+\s*=",
            r"^\s*enum\s+\w+\s*[\{]",
            r":\s*(string|number|boolean|any|void|never|unknown)\s*[;,\)\}]",
        ],
        "java": [
            r"^\s*package\s+[\w\.]+;",
            r"^\s*import\s+[\w\.]+\.*;?\s*$",  # Java imports end with semicolon
            r"^\s*public\s+class\s+\w+",
            r"^\s*private\s+\w+\s+\w+;",
            r"^\s*public\s+static\s+void\s+main",
            r"^\s*(public|private|protected)\s+\w+\s+\w+\s*[;=\(]",  # Field/method declarations
        ],
        "go": [
            r"^\s*package\s+\w+",
            r"^\s*import\s+\(",
            r"^\s*func\s+\w+\s*\(",
            r"^\s*type\s+\w+\s+struct\s*\{",
            r"^\s*var\s+\w+\s+\w+",
        ],
        "rust": [
            r"^\s*use\s+\w+",
            r"^\s*fn\s+\w+\s*\(",
            r"^\s*struct\s+\w+\s*[\{\(]",
            r"^\s*impl\s+\w+",
            r"^\s*let\s+(mut\s+)?\w+",
            r"^\s*pub\s+(fn|struct|enum|trait)",
        ],
        "ruby": [
            r'^\s*require\s+["\']',
            r'^\s*require_relative\s+["\']',
            r"^\s*def\s+\w+",
            r"^\s*class\s+\w+",
            r"^\s*module\s+\w+",
            r"^\s*attr_(reader|writer|accessor)\s+",
        ],
        "php": [
            r"<\?php",
            r"^\s*namespace\s+[\w\\\\]+;",
            r"^\s*use\s+[\w\\\\]+;",
            r"^\s*class\s+\w+",
            r"^\s*function\s+\w+\s*\(",
            r"\$\w+\s*=",
        ],
    }

    def detect_from_file(self, file_path: str) -> tuple[str, float]:
        """Detect language from file_path path and content."""
        path = Path(file_path)
        confidence = 0.0
        language = None

        # Check file_path extension
        ext = path.suffix.lower()
        if ext in self.EXTENSIONS:
            language = self.EXTENSIONS[ext]
            confidence = 0.8

        # Try to read file_path for content analysis
        try:
            with Path(file_path).open(encoding="utf-8", errors="ignore") as f:
                content = f.read(4096)  # Read first 4KB

            # Check shebang
            if content.startswith("#!"):
                first_line = content.split("\n")[0]
                for pattern, lang in self.SHEBANG_PATTERNS.items():
                    if re.search(pattern, first_line):
                        return (lang, 0.95)

            # If we have a language from extension, verify with content
            if language:
                content_lang, content_conf = self.detect_from_content(
                    content,
                    hint=language,
                )
                if content_lang == language:
                    confidence = min(0.95, confidence + content_conf * 0.2)
                elif content_conf > 0.8:
                    # Content strongly suggests different language
                    language = content_lang
                    confidence = content_conf
            else:
                # No extension match, rely on content
                language, confidence = self.detect_from_content(content)

        except OSError:
            # Can't read file_path, rely on extension
            pass

        if not language:
            language = "text"
            confidence = 0.1

        return (language, confidence)

    def detect_from_content(
        self,
        content: str,
        hint: str | None = None,
    ) -> tuple[str, float]:
        """Detect language from content alone."""
        if not content.strip():
            return ("text", 0.1)

        scores = defaultdict(float)

        # If we have a hint, give it a slight boost
        if hint and hint in self.CONTENT_PATTERNS:
            scores[hint] = 0.2

        # Check content patterns
        for language, patterns in self.CONTENT_PATTERNS.items():
            for pattern in patterns:
                matches = len(re.findall(pattern, content, re.MULTILINE))
                if matches:
                    scores[language] += matches * 0.1

        # Special check for TypeScript (extends JavaScript patterns)
        if "typescript" in scores and "javascript" in scores:
            # TypeScript-specific patterns should boost TS over JS
            scores["typescript"] += scores["javascript"] * 0.5

        # Normalize scores
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                for lang in scores:
                    scores[lang] = min(0.95, scores[lang] / max_score)

            # Get language with highest score
            best_lang = max(scores.items(), key=lambda x: x[1])
            return best_lang

        return ("text", 0.1)

    def detect_multiple(self, content: str) -> list[tuple[str, float]]:
        """Detect multiple languages in content."""
        if not content.strip():
            return [("text", 1.0)]

        # Look for language markers
        language_blocks = []

        # Markdown code blocks
        markdown_blocks = re.findall(r"```(\w+)?\n(.*?)```", content, re.DOTALL)
        for lang, block in markdown_blocks:
            if lang:
                language_blocks.append((lang, len(block)))
            else:
                detected_lang, _ = self.detect_from_content(block)
                language_blocks.append((detected_lang, len(block)))

        # HTML script/style tags
        script_blocks = re.findall(
            r"<script[^>]*>(.*?)</script>",
            content,
            re.DOTALL | re.IGNORECASE,
        )
        for block in script_blocks:
            language_blocks.append(("javascript", len(block)))

        style_blocks = re.findall(
            r"<style[^>]*>(.*?)</style>",
            content,
            re.DOTALL | re.IGNORECASE,
        )
        for block in style_blocks:
            language_blocks.append(("css", len(block)))

        # JSX/TSX detection
        if re.search(r"<[A-Z]\w*[^>]*>", content) and re.search(
            r"(import|export|const|let|var)",
            content,
        ):
            # Likely JSX/TSX
            ts_patterns = len(
                re.findall(r":\s*(string|number|boolean|any|void)\s*[;,\)\}]", content),
            )
            if ts_patterns > 2:
                language_blocks.append(("typescript", len(content)))
            else:
                language_blocks.append(("javascript", len(content)))

        # Calculate percentages
        if language_blocks:
            total_size = sum(size for _, size in language_blocks)
            language_percentages = defaultdict(float)

            for lang, size in language_blocks:
                language_percentages[lang] += size / total_size

            # Sort by percentage
            results = sorted(
                language_percentages.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            return results
        # Fallback to single language detection
        lang, conf = self.detect_from_content(content)
        return [(lang, 1.0)]


class ProjectAnalyzerImpl(ProjectAnalyzer):
    """Analyze multi-language project structure."""

    def __init__(self, detector: LanguageDetector | None = None):
        self.detector = detector or LanguageDetectorImpl()

    def analyze_structure(self, project_path: str) -> dict[str, Any]:
        """Analyze overall project structure."""
        project_root = Path(project_path)
        if not project_root.exists():
            raise ValueError(f"Project path does not exist: {project_path}")

        analysis = {
            "project_path": str(project_root),
            "languages": defaultdict(int),
            "file_count": 0,
            "total_lines": 0,
            "framework_indicators": {},
            "project_type": "unknown",
            "structure": {
                "has_backend": False,
                "has_frontend": False,
                "has_tests": False,
                "has_docs": False,
                "has_config": False,
            },
        }

        # Common framework/project files
        framework_files = {
            "package.json": ["javascript", "node", "npm"],
            "tsconfig.json": ["typescript"],
            "requirements.txt": ["python"],
            "setup.py": ["python"],
            "pyproject.toml": ["python"],
            "Cargo.toml": ["rust"],
            "go.mod": ["go"],
            "pom.xml": ["java", "maven"],
            "build.gradle": ["java", "gradle"],
            "Gemfile": ["ruby"],
            "composer.json": ["php"],
            "CMakeLists.txt": ["cpp", "cmake"],
            "Makefile": ["make"],
            "Dockerfile": ["docker"],
            "docker-compose.yml": ["docker"],
            ".gitignore": ["git"],
        }

        # Walk project directory
        for root, dirs, files in os.walk(project_root):
            # Skip common non-source directories
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d
                not in {
                    "node_modules",
                    "venv",
                    "env",
                    "__pycache__",
                    "target",
                    "build",
                    "dist",
                }
            ]

            rel_path = Path(root).relative_to(project_root)

            for file_path in files:
                file_path = Path(root) / file_path
                analysis["file_count"] += 1

                # Check for framework indicators
                if file_path in framework_files:
                    for indicator in framework_files[file_path]:
                        analysis["framework_indicators"][indicator] = True

                # Detect language
                try:
                    lang, confidence = self.detector.detect_from_file(str(file_path))
                    if confidence > 0.5:
                        analysis["languages"][lang] += 1

                    # Count lines
                    try:
                        with Path(file_path).open(
                            encoding="utf-8",
                            errors="ignore",
                        ) as f:
                            analysis["total_lines"] += sum(1 for _ in f)
                    except (OSError, FileNotFoundError, IndexError):
                        pass

                    # Detect structure patterns
                    path_parts = str(rel_path).lower()
                    if any(
                        part in path_parts
                        for part in ["src", "lib", "app", "backend", "server", "api"]
                    ):
                        analysis["structure"]["has_backend"] = True
                    if any(
                        part in path_parts
                        for part in [
                            "frontend",
                            "client",
                            "web",
                            "static",
                            "public",
                            "src/components",
                        ]
                    ):
                        analysis["structure"]["has_frontend"] = True
                    if any(
                        part in path_parts
                        for part in ["test", "tests", "spec", "__tests__"]
                    ):
                        analysis["structure"]["has_tests"] = True
                    if any(
                        part in path_parts
                        for part in ["docs", "documentation", "README"]
                    ):
                        analysis["structure"]["has_docs"] = True
                    if file_path in framework_files or file_path.endswith(
                        (".json", ".yaml", ".yml", ".toml", ".ini"),
                    ):
                        analysis["structure"]["has_config"] = True

                except (OSError, FileNotFoundError, IndexError):
                    pass

        # Determine project type
        analysis["project_type"] = self._determine_project_type(analysis)

        # Convert defaultdict to regular dict
        analysis["languages"] = dict(analysis["languages"])

        return analysis

    def _determine_project_type(self, analysis: dict[str, Any]) -> str:
        """Determine project type from analysis."""
        indicators = analysis["framework_indicators"]
        structure = analysis["structure"]
        languages = analysis["languages"]

        # Web application
        if structure["has_frontend"] and structure["has_backend"]:
            return "fullstack_webapp"
        if "javascript" in indicators or "typescript" in indicators and "node" in indicators:
                return "node_application"
            return "frontend_webapp"

        # API/Backend
        if structure["has_backend"] and not structure["has_frontend"]:
            return "backend_api"

        # Library/Package
        if any(key in indicators for key in ["npm", "python", "rust", "go"]):
            if analysis["file_count"] < 50:  # Small project
                return "library"

        # Mobile app
        if "swift" in languages or "kotlin" in languages or "java" in languages:
            if (
                "android" in str(analysis["project_path"]).lower()
                or "ios" in str(analysis["project_path"]).lower()
            ):
                return "mobile_app"

        # Data science / ML
        if "python" in languages and "jupyter" in languages:
            return "data_science_project"

        return "general_project"

    def find_api_boundaries(self, chunks: list[CodeChunk]) -> list[dict[str, Any]]:
        """Find API boundaries between components."""
        api_boundaries = []

        # Group chunks by file_path path patterns
        backend_chunks = []
        frontend_chunks = []
        api_chunks = []

        for chunk in chunks:
            path_lower = chunk.file_path.lower()

            # Identify API-related chunks
            if any(
                pattern in path_lower
                for pattern in [
                    "api/",
                    "/api/",
                    "routes/",
                    "controllers/",
                    "endpoints/",
                ]
            ):
                api_chunks.append(chunk)
            elif any(
                pattern in path_lower
                for pattern in ["backend/", "server/", "src/main/"]
            ):
                backend_chunks.append(chunk)
            elif any(
                pattern in path_lower
                for pattern in ["frontend/", "client/", "src/components/", "pages/"]
            ):
                frontend_chunks.append(chunk)

            # Look for API definitions in content
            if chunk.language in ["python", "javascript", "typescript", "java", "go"]:
                # REST API patterns
                rest_patterns = [
                    r"@(app|router)\.(get|post|put|delete|patch|route)\(",
                    r"@(Get|Post|Put|Delete|Patch)Mapping",
                    r"router\.(get|post|put|delete|patch)\(",
                    r"http\.(Get|Post|Put|Delete|Patch)\(",
                ]

                for pattern in rest_patterns:
                    if re.search(pattern, chunk.content):
                        # Extract endpoint
                        endpoint_match = re.search(
                            r'["\']([/\w\-\{\}:]+)["\']',
                            chunk.content,
                        )
                        if endpoint_match:
                            api_boundaries.append(
                                {
                                    "type": "rest_endpoint",
                                    "chunk_id": chunk.chunk_id,
                                    "endpoint": endpoint_match.group(1),
                                    "method": "detected",
                                    "language": chunk.language,
                                    "file_path": chunk.file_path,
                                },
                            )

                # GraphQL patterns
                graphql_patterns = [
                    r"type\s+Query\s*\{",
                    r"type\s+Mutation\s*\{",
                    r"@(Query|Mutation|Resolver)",
                ]

                for pattern in graphql_patterns:
                    if re.search(pattern, chunk.content):
                        api_boundaries.append(
                            {
                                "type": "graphql_schema",
                                "chunk_id": chunk.chunk_id,
                                "language": chunk.language,
                                "file_path": chunk.file_path,
                            },
                        )

        # Find RPC/gRPC definitions
        for chunk in chunks:
            if chunk.language in ["proto", "protobuf"] or ".proto" in chunk.file_path:
                api_boundaries.append(
                    {
                        "type": "grpc_service",
                        "chunk_id": chunk.chunk_id,
                        "file_path": chunk.file_path,
                    },
                )

        return api_boundaries

    def suggest_chunk_grouping(
        self,
        chunks: list[CodeChunk],
    ) -> dict[str, list[CodeChunk]]:
        """Suggest how to group chunks for processing."""
        groupings = defaultdict(list)

        # Group by feature/component based on file_path paths
        for chunk in chunks:
            # Extract feature name from path
            path_parts = Path(chunk.file_path).parts

            # Common feature patterns
            feature = None
            for i, part in enumerate(path_parts):
                if part in ["features", "modules", "components", "services", "domains"] and i + 1 < len(path_parts):
                        feature = path_parts[i + 1]
                        break

            if feature:
                groupings[f"feature_{feature}"].append(chunk)
            # Group by top-level directory
            elif len(path_parts) > 1:
                groupings[f"module_{path_parts[0]}"].append(chunk)
            else:
                groupings["root"].append(chunk)

        # Group by language for cross-language analysis
        for chunk in chunks:
            groupings[f"lang_{chunk.language}"].append(chunk)

        # Group by node type
        for chunk in chunks:
            groupings[f"type_{chunk.node_type}"].append(chunk)

        return dict(groupings)


class MultiLanguageProcessorImpl(MultiLanguageProcessor):
    """Process projects with multiple languages."""

    def __init__(
        self,
        detector: LanguageDetector | None = None,
        analyzer: ProjectAnalyzer | None = None,
    ):
        self.detector = detector or LanguageDetectorImpl()
        self.analyzer = analyzer or ProjectAnalyzerImpl(self.detector)
        try:
            self._supported_languages = set(list_languages())
        except (TypeError, ValueError):
            # If tree-sitter library is not available, use a default set
            self._supported_languages = {
                "python",
                "javascript",
                "typescript",
                "java",
                "go",
                "rust",
                "c",
                "cpp",
                "ruby",
                "php",
                "swift",
                "kotlin",
                "csharp",
            }

    def detect_project_languages(self, project_path: str) -> dict[str, float]:
        """Detect languages used in project with confidence scores."""
        analysis = self.analyzer.analyze_structure(project_path)
        total_files = sum(analysis["languages"].values())

        if total_files == 0:
            return {}

        # Calculate percentages
        language_percentages = {}
        for lang, count in analysis["languages"].items():
            percentage = count / total_files
            language_percentages[lang] = percentage

        return language_percentages

    def identify_language_regions(
        self,
        file_path: str,
        content: str,
    ) -> list[LanguageRegion]:
        """Identify regions of different languages within a file_path."""
        regions = []
        lines = content.split("\n")

        # Detect primary language
        primary_lang, _ = self.detector.detect_from_file(file_path)

        # Special handling for mixed-language files
        if file_path.endswith((".jsx", ".tsx")):
            # JSX/TSX files
            regions.extend(self._identify_jsx_regions(content, primary_lang))
        elif file_path.endswith((".html", ".htm")):
            # HTML files
            regions.extend(self._identify_html_regions(content))
        elif file_path.endswith(".md"):
            # Markdown files
            regions.extend(self._identify_markdown_regions(content))
        elif file_path.endswith(".ipynb"):
            # Jupyter notebooks
            regions.extend(self._identify_notebook_regions(content))
        else:
            # Check for embedded languages in regular files
            regions.extend(self._identify_embedded_regions(content, primary_lang))

        # If no regions found, treat entire file_path as one region
        if not regions and content.strip():
            regions.append(
                LanguageRegion(
                    language=primary_lang,
                    start_pos=0,
                    end_pos=len(content),
                    start_line=1,
                    end_line=len(lines),
                    embedding_type=None,
                    parent_language=None,
                ),
            )

        return regions

    def _identify_jsx_regions(
        self,
        content: str,
        base_language: str,
    ) -> list[LanguageRegion]:
        """Identify JSX/TSX regions."""
        regions = []
        lines = content.split("\n")

        # JSX is essentially JavaScript/TypeScript with embedded HTML-like syntax
        # For simplicity, treat the entire file_path as the base language
        regions.append(
            LanguageRegion(
                language=base_language,
                start_pos=0,
                end_pos=len(content),
                start_line=1,
                end_line=len(lines),
                embedding_type=EmbeddedLanguageType.TEMPLATE,
                parent_language=None,
            ),
        )

        # Find embedded CSS in style props
        style_pattern = r"style\s*=\s*\{\{([^}]+)\}\}"
        for match in re.finditer(style_pattern, content):
            start_line = content[: match.start()].count("\n") + 1
            end_line = content[: match.end()].count("\n") + 1
            regions.append(
                LanguageRegion(
                    language="css",
                    start_pos=match.start(1),
                    end_pos=match.end(1),
                    start_line=start_line,
                    end_line=end_line,
                    embedding_type=EmbeddedLanguageType.STYLE,
                    parent_language=base_language,
                ),
            )

        return regions

    def _identify_html_regions(self, content: str) -> list[LanguageRegion]:
        """Identify regions in HTML files."""
        regions = []

        # Main HTML region
        regions.append(
            LanguageRegion(
                language="html",
                start_pos=0,
                end_pos=len(content),
                start_line=1,
                end_line=content.count("\n") + 1,
                embedding_type=None,
                parent_language=None,
            ),
        )

        # Find script tags
        script_pattern = r"<script[^>]*>(.*?)</script>"
        for match in re.finditer(script_pattern, content, re.DOTALL | re.IGNORECASE):
            start_line = content[: match.start(1)].count("\n") + 1
            end_line = content[: match.end(1)].count("\n") + 1
            regions.append(
                LanguageRegion(
                    language="javascript",
                    start_pos=match.start(1),
                    end_pos=match.end(1),
                    start_line=start_line,
                    end_line=end_line,
                    embedding_type=EmbeddedLanguageType.SCRIPT,
                    parent_language="html",
                ),
            )

        # Find style tags
        style_pattern = r"<style[^>]*>(.*?)</style>"
        for match in re.finditer(style_pattern, content, re.DOTALL | re.IGNORECASE):
            start_line = content[: match.start(1)].count("\n") + 1
            end_line = content[: match.end(1)].count("\n") + 1
            regions.append(
                LanguageRegion(
                    language="css",
                    start_pos=match.start(1),
                    end_pos=match.end(1),
                    start_line=start_line,
                    end_line=end_line,
                    embedding_type=EmbeddedLanguageType.STYLE,
                    parent_language="html",
                ),
            )

        return regions

    def _identify_markdown_regions(self, content: str) -> list[LanguageRegion]:
        """Identify regions in Markdown files."""
        regions = []

        # Main markdown region
        regions.append(
            LanguageRegion(
                language="markdown",
                start_pos=0,
                end_pos=len(content),
                start_line=1,
                end_line=content.count("\n") + 1,
                embedding_type=None,
                parent_language=None,
            ),
        )

        # Find code blocks
        code_block_pattern = r"```(\w+)?\n(.*?)```"
        for match in re.finditer(code_block_pattern, content, re.DOTALL):
            language = match.group(1) or "text"
            start_line = content[: match.start(2)].count("\n") + 1
            end_line = content[: match.end(2)].count("\n") + 1

            regions.append(
                LanguageRegion(
                    language=language,
                    start_pos=match.start(2),
                    end_pos=match.end(2),
                    start_line=start_line,
                    end_line=end_line,
                    embedding_type=EmbeddedLanguageType.DOCUMENTATION,
                    parent_language="markdown",
                ),
            )

        return regions

    def _identify_notebook_regions(self, content: str) -> list[LanguageRegion]:
        """Identify regions in Jupyter notebooks."""
        regions = []

        try:
            notebook = json.loads(content)
            current_pos = 0
            current_line = 1

            for cell in notebook.get("cells", []):
                cell_type = cell.get("cell_type", "code")
                source = cell.get("source", [])
                if isinstance(source, list):
                    source = "".join(source)

                if cell_type == "code":
                    # Detect language from kernel or metadata
                    language = "python"  # Default
                    if "language_info" in notebook.get("metadata", {}):
                        language = notebook["metadata"]["language_info"].get(
                            "name",
                            "python",
                        )

                    lines_in_cell = source.count("\n") + 1
                    regions.append(
                        LanguageRegion(
                            language=language,
                            start_pos=current_pos,
                            end_pos=current_pos + len(source),
                            start_line=current_line,
                            end_line=current_line + lines_in_cell - 1,
                            embedding_type=EmbeddedLanguageType.SCRIPT,
                            parent_language="jupyter",
                        ),
                    )
                elif cell_type == "markdown":
                    lines_in_cell = source.count("\n") + 1
                    regions.append(
                        LanguageRegion(
                            language="markdown",
                            start_pos=current_pos,
                            end_pos=current_pos + len(source),
                            start_line=current_line,
                            end_line=current_line + lines_in_cell - 1,
                            embedding_type=EmbeddedLanguageType.DOCUMENTATION,
                            parent_language="jupyter",
                        ),
                    )

                current_pos += len(source)
                current_line += source.count("\n") + 1

        except json.JSONDecodeError:
            # Not valid JSON, treat as text
            regions.append(
                LanguageRegion(
                    language="text",
                    start_pos=0,
                    end_pos=len(content),
                    start_line=1,
                    end_line=content.count("\n") + 1,
                    embedding_type=None,
                    parent_language=None,
                ),
            )

        return regions

    def _identify_embedded_regions(
        self,
        content: str,
        primary_language: str,
    ) -> list[LanguageRegion]:
        """Identify embedded language regions in regular source files."""
        regions = []

        # SQL in strings
        sql_pattern = r'["\'](\s*SELECT\s+.*?\s+FROM\s+.*?)["\']'
        for match in re.finditer(sql_pattern, content, re.IGNORECASE | re.DOTALL):
            start_line = content[: match.start(1)].count("\n") + 1
            end_line = content[: match.end(1)].count("\n") + 1
            regions.append(
                LanguageRegion(
                    language="sql",
                    start_pos=match.start(1),
                    end_pos=match.end(1),
                    start_line=start_line,
                    end_line=end_line,
                    embedding_type=EmbeddedLanguageType.QUERY,
                    parent_language=primary_language,
                ),
            )

        # GraphQL in strings
        graphql_pattern = r'gql`([^`]+)`|graphql\(["\']([^"\']+)["\']\)'
        for match in re.finditer(graphql_pattern, content):
            group = match.group(1) or match.group(2)
            if group:
                start_line = content[: match.start()].count("\n") + 1
                end_line = content[: match.end()].count("\n") + 1
                regions.append(
                    LanguageRegion(
                        language="graphql",
                        start_pos=match.start(),
                        end_pos=match.end(),
                        start_line=start_line,
                        end_line=end_line,
                        embedding_type=EmbeddedLanguageType.QUERY,
                        parent_language=primary_language,
                    ),
                )

        # JSON in strings - use a more flexible pattern
        # Look for strings that start with { or [ and try to parse as JSON
        string_pattern = r'["\'](\{.*?\}|\[.*?\])["\']'
        for match in re.finditer(string_pattern, content, re.DOTALL):
            try:
                json.loads(match.group(1))
                start_line = content[: match.start(1)].count("\n") + 1
                end_line = content[: match.end(1)].count("\n") + 1
                regions.append(
                    LanguageRegion(
                        language="json",
                        start_pos=match.start(1),
                        end_pos=match.end(1),
                        start_line=start_line,
                        end_line=end_line,
                        embedding_type=EmbeddedLanguageType.CONFIGURATION,
                        parent_language=primary_language,
                    ),
                )
            except (FileNotFoundError, OSError):
                pass

        return regions

    def process_mixed_file(
        self,
        file_path: str,
        primary_language: str,
        content: str | None = None,
    ) -> list[CodeChunk]:
        """Process files with embedded languages."""
        if content is None:
            with Path(file_path).open(encoding="utf-8") as f:
                content = f.read()

        chunks = []
        regions = self.identify_language_regions(file_path, content)

        for region in regions:
            # Skip if language not supported by tree-sitter
            if region.language not in self._supported_languages:
                continue

            # Extract region content
            region_content = content[region.start_pos : region.end_pos]

            try:
                # Use tree-sitter to parse the region if available
                parser = get_parser(region.language)
                parser.parse(region_content.encode())

                # Create chunks from the parsed tree
                region_chunks = chunk_file(
                    file_path=file_path,
                    content=region_content,
                    language=region.language,
                )

                # Adjust chunk positions to match the original file_path
                for chunk in region_chunks:
                    chunk.start_line += region.start_line - 1
                    chunk.end_line += region.start_line - 1
                    chunk.byte_start += region.start_pos
                    chunk.byte_end += region.start_pos

                    # Add metadata about embedding
                    if region.embedding_type:
                        chunk.metadata["embedding_type"] = region.embedding_type.value
                    if region.parent_language:
                        chunk.metadata["parent_language"] = region.parent_language

                    chunks.append(chunk)

            except (FileNotFoundError, IndexError, KeyError) as e:
                # Fallback: create a single chunk for the region
                chunk = CodeChunk(
                    language=region.language,
                    file_path=file_path,
                    node_type="region",
                    start_line=region.start_line,
                    end_line=region.end_line,
                    byte_start=region.start_pos,
                    byte_end=region.end_pos,
                    parent_context="",
                    content=region_content,
                    metadata={
                        "embedding_type": (
                            region.embedding_type.value
                            if region.embedding_type
                            else None
                        ),
                        "parent_language": region.parent_language,
                        "parse_error": str(e),
                    },
                )
                chunks.append(chunk)

        return chunks

    def extract_embedded_code(
        self,
        content: str,
        host_language: str,
        target_language: str,
    ) -> list[tuple[str, int, int]]:
        """Extract embedded code snippets."""
        snippets = []

        # Language-specific extraction patterns
        if host_language == "html" and target_language == "javascript":
            # Extract from script tags
            pattern = r"<script[^>]*>(.*?)</script>"
            for match in re.finditer(pattern, content, re.DOTALL | re.IGNORECASE):
                snippets.append((match.group(1), match.start(1), match.end(1)))

            # Extract from event handlers
            event_pattern = r'on\w+\s*=\s*["\']([^"\']+)["\']'
            for match in re.finditer(event_pattern, content):
                snippets.append((match.group(1), match.start(1), match.end(1)))

        elif host_language == "html" and target_language == "css":
            # Extract from style tags
            pattern = r"<style[^>]*>(.*?)</style>"
            for match in re.finditer(pattern, content, re.DOTALL | re.IGNORECASE):
                snippets.append((match.group(1), match.start(1), match.end(1)))

            # Extract from style attributes
            style_pattern = r'style\s*=\s*["\']([^"\']+)["\']'
            for match in re.finditer(style_pattern, content):
                snippets.append((match.group(1), match.start(1), match.end(1)))

        elif host_language == "markdown" and target_language:
            # Extract code blocks with specific language
            pattern = rf"```{target_language}\n(.*?)```"
            for match in re.finditer(pattern, content, re.DOTALL):
                snippets.append((match.group(1), match.start(1), match.end(1)))

        elif target_language == "sql":
            # Extract SQL queries from strings
            sql_patterns = [
                r'["\'](\s*SELECT\s+.*?\s+FROM\s+.*?)["\']',
                r'["\'](\s*INSERT\s+INTO\s+.*?)["\']',
                r'["\'](\s*UPDATE\s+.*?\s+SET\s+.*?)["\']',
                r'["\'](\s*DELETE\s+FROM\s+.*?)["\']',
            ]
            for pattern in sql_patterns:
                for match in re.finditer(pattern, content, re.IGNORECASE | re.DOTALL):
                    snippets.append((match.group(1), match.start(1), match.end(1)))

        elif target_language == "graphql":
            # Extract GraphQL queries
            patterns = [
                r"gql`([^`]+)`",
                r'graphql\(["\']([^"\']+)["\']\)',
                r'query\s*=\s*["\']([^"\']+)["\']',
            ]
            for pattern in patterns:
                for match in re.finditer(pattern, content):
                    snippets.append((match.group(1), match.start(1), match.end(1)))

        return snippets

    def cross_language_references(
        self,
        chunks: list[CodeChunk],
    ) -> list[CrossLanguageReference]:
        """Find references across language boundaries."""
        references = []

        # Index chunks by various attributes for faster lookup
        chunks_by_name = defaultdict(list)
        api_endpoints = defaultdict(list)
        imports_exports = defaultdict(list)

        # First pass: build indices
        for chunk in chunks:
            # Extract names (functions, classes, etc.)
            if chunk.node_type in [
                "function_definition",
                "class_definition",
                "method_definition",
            ]:
                # Simple name extraction (would be better with proper AST)
                name_match = re.search(r"(?:function|class|def)\s+(\w+)", chunk.content)
                if name_match:
                    name = name_match.group(1)
                    chunks_by_name[name].append(chunk)

            # Extract API endpoints
            if chunk.language in ["python", "javascript", "typescript", "java"]:
                # REST endpoints
                endpoint_patterns = [
                    r'["\']([/\w\-\{\}:]+)["\']',  # URL paths
                    r'@\w+\(["\']([/\w\-\{\}:]+)["\']',  # Decorators
                ]
                for pattern in endpoint_patterns:
                    for match in re.finditer(pattern, chunk.content):
                        path = match.group(1)
                        if path.startswith("/"):
                            api_endpoints[path].append(chunk)

            # Extract imports/exports
            if chunk.language in ["javascript", "typescript", "python"]:
                import_patterns = [
                    r'import\s+.*?\s+from\s+["\']([^"\']+)["\']',
                    r"from\s+([^\s]+)\s+import",
                    r'require\(["\']([^"\']+)["\']\)',
                ]
                for pattern in import_patterns:
                    for match in re.finditer(pattern, chunk.content):
                        module = match.group(1)
                        imports_exports[module].append(chunk)

        # Second pass: find cross-references
        for chunk in chunks:
            # Find API calls
            if chunk.language in ["javascript", "typescript"]:
                # Look for fetch/axios calls
                api_call_patterns = [
                    r'fetch\(["\']([/\w\-\{\}:]+)["\']',
                    r"fetch\(`([/\w\-\{\}:]+)",  # Template literals
                    r'axios\.\w+\(["\']([/\w\-\{\}:]+)["\']',
                    r"axios\.\w+\(`([/\w\-\{\}:]+)",  # Template literals
                    r'\$\.ajax\(.*?url:\s*["\']([/\w\-\{\}:]+)["\']',
                ]
                for pattern in api_call_patterns:
                    for match in re.finditer(pattern, chunk.content):
                        endpoint = match.group(1)
                        if endpoint in api_endpoints:
                            for target_chunk in api_endpoints[endpoint]:
                                if target_chunk.language != chunk.language:
                                    references.append(
                                        CrossLanguageReference(
                                            source_chunk=chunk,
                                            target_chunk=target_chunk,
                                            reference_type="api_call",
                                            confidence=0.8,
                                        ),
                                    )

            # Find shared types/interfaces
            if chunk.node_type in [
                "interface_declaration",
                "type_alias_declaration",
                "struct_declaration",
                "class_definition",
            ]:
                # Extract type/class/struct name
                type_patterns = [
                    r"(?:interface|type|class|struct)\s+(\w+)",
                    r"type\s+(\w+)\s+struct",  # Go style
                ]

                type_name = None
                for pattern in type_patterns:
                    match = re.search(pattern, chunk.content)
                    if match:
                        type_name = match.group(1)
                        break

                if type_name:
                    # Look for same type in other languages
                    for other_chunk in chunks:
                        if (
                            other_chunk != chunk
                            and other_chunk.language != chunk.language
                        ):
                            # Check if the other chunk also defines a type with the same name
                            if other_chunk.node_type in [
                                "interface_declaration",
                                "type_alias_declaration",
                                "struct_declaration",
                                "class_definition",
                            ]:
                                for pattern in type_patterns:
                                    other_match = re.search(
                                        pattern,
                                        other_chunk.content,
                                    )
                                    if (
                                        other_match
                                        and other_match.group(1) == type_name
                                    ):
                                        references.append(
                                            CrossLanguageReference(
                                                source_chunk=chunk,
                                                target_chunk=other_chunk,
                                                reference_type="shared_type",
                                                confidence=0.6,
                                            ),
                                        )
                                        break

            # Find database references
            if "sql" in chunk.content.lower() or "query" in chunk.content.lower():
                # Look for table names
                table_patterns = [
                    r"FROM\s+(\w+)",
                    r"INSERT\s+INTO\s+(\w+)",
                    r"UPDATE\s+(\w+)",
                    r"CREATE\s+TABLE\s+(\w+)",
                ]
                for pattern in table_patterns:
                    for match in re.finditer(pattern, chunk.content, re.IGNORECASE):
                        table_name = match.group(1)
                        # Look for same table in other chunks
                        for other_chunk in chunks:
                            if (
                                other_chunk != chunk
                                and table_name in other_chunk.content
                            ) and other_chunk.language != chunk.language:
                                references.append(
                                    CrossLanguageReference(
                                        source_chunk=chunk,
                                        target_chunk=other_chunk,
                                        reference_type="database_reference",
                                        confidence=0.5,
                                    ),
                                )

        return references

    def group_by_feature(self, chunks: list[CodeChunk]) -> dict[str, list[CodeChunk]]:
        """Group chunks from different languages by feature."""
        feature_groups = defaultdict(list)

        # Strategy 1: Group by file_path path patterns
        path_features = {}
        for chunk in chunks:
            path = Path(chunk.file_path)
            parts = path.parts

            # Look for feature indicators in path
            feature_name = None
            for i, part in enumerate(parts):
                if part in ["features", "modules", "components", "domains", "services"] and i + 1 < len(parts):
                        feature_name = parts[i + 1]
                        break

            if feature_name:
                path_features[chunk.chunk_id] = feature_name
                feature_groups[feature_name].append(chunk)

        # Strategy 2: Group by naming patterns
        name_patterns = defaultdict(list)
        for chunk in chunks:
            # Extract entity names
            if chunk.node_type in ["class_definition", "function_definition"]:
                name_match = re.search(r"(?:class|function|def)\s+(\w+)", chunk.content)
                if name_match:
                    name = name_match.group(1)
                    # Extract feature from name (e.g., UserController -> User)
                    base_name = re.sub(
                        r"(Controller|Service|Repository|Component|Model|View)$",
                        "",
                        name,
                    )
                    name_patterns[base_name.lower()].append(chunk)

        # Merge name-based groups into feature groups
        for base_name, name_chunks in name_patterns.items():
            if len(name_chunks) > 1:  # Only if multiple chunks share the pattern
                # Check if this overlaps with existing features
                merged = False
                for feature_name, feature_chunks in feature_groups.items():
                    if any(chunk in feature_chunks for chunk in name_chunks):
                        # Merge into existing feature
                        for chunk in name_chunks:
                            if chunk not in feature_chunks:
                                feature_chunks.append(chunk)
                        merged = True
                        break

                if not merged:
                    feature_groups[f"entity_{base_name}"] = name_chunks

        # Strategy 3: Group by cross-references
        references = self.cross_language_references(chunks)
        reference_groups = defaultdict(set)

        for ref in references:
            # Find which features these chunks belong to
            source_feature = None
            target_feature = None

            for feature, feature_chunks in feature_groups.items():
                if ref.source_chunk in feature_chunks:
                    source_feature = feature
                if ref.target_chunk in feature_chunks:
                    target_feature = feature

            # If they're in different features but connected, note the connection
            if source_feature and target_feature and source_feature != target_feature:
                reference_groups[source_feature].add(target_feature)
                reference_groups[target_feature].add(source_feature)

        # Add metadata about related features
        for feature, related in reference_groups.items():
            if feature in feature_groups:
                for chunk in feature_groups[feature]:
                    chunk.metadata["related_features"] = list(related)

        return dict(feature_groups)
