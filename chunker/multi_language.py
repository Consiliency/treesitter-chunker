"""Multi-language project processing implementation."""

import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, ClassVar

from .core import chunk_file
from .interfaces.multi_language import (
    CrossLanguageReference,
    EmbeddedLanguageType,
    LanguageDetector,
    LanguageRegion,
    MultiLanguageProcessor,
    ProjectAnalyzer,
)
from .parser import get_parser, list_languages
from .types import CodeChunk

try:
    pass
except ImportError:

    def list_languages():
        return ["python", "javascript", "typescript", "java", "go", "rust", "c", "cpp"]

    def get_parser(_language):
        raise ImportError("Tree-sitter parser not available")

    def chunk_file(_file_path, _content, _language):
        raise ImportError("Chunker not available")


class LanguageDetectorImpl(LanguageDetector):
    """Detect programming languages in files and content."""

    EXTENSIONS: ClassVar[dict[str, str]] = {
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
    SHEBANG_PATTERNS: ClassVar[dict[str, str]] = {
        "python[0-9\\.]*": "python",
        "node": "javascript",
        "ruby": "ruby",
        "perl": "perl",
        "bash": "bash",
        "sh": "bash",
        "zsh": "bash",
        "fish": "bash",
        "lua": "lua",
        "php": "php",
    }
    CONTENT_PATTERNS: ClassVar[dict[str, list[str]]] = {
        "python": [
            "^\\s*import\\s+\\w+(?:\\s*,\\s*\\w+)*\\s*$",
            "^\\s*from\\s+[\\w\\.]+\\s+import",
            "^\\s*def\\s+\\w+\\s*\\(",
            "^\\s*class\\s+\\w+\\s*[:\\(]",
            "^\\s*if\\s+__name__\\s*==\\s*[\"\\']__main__[\"\\']",
            "^\\s*@\\w+",
        ],
        "javascript": [
            "^\\s*const\\s+\\w+\\s*=",
            "^\\s*let\\s+\\w+\\s*=",
            "^\\s*var\\s+\\w+\\s*=",
            "^\\s*function\\s+\\w+\\s*\\(",
            "^\\s*class\\s+\\w+\\s*[\\{]",
            "^\\s*import\\s+.*\\s+from\\s+[\"\\']",
            "^\\s*export\\s+(default\\s+)?",
        ],
        "typescript": [
            "^\\s*interface\\s+\\w+\\s*[\\{]",
            "^\\s*type\\s+\\w+\\s*=",
            "^\\s*enum\\s+\\w+\\s*[\\{]",
            ":\\s*(string|number|boolean|any|void|never|unknown)\\s*[;,\\)\\}]",
        ],
        "java": [
            "^\\s*package\\s+[\\w\\.]+;",
            "^\\s*import\\s+[\\w\\.]+\\.*;?\\s*$",
            "^\\s*public\\s+class\\s+\\w+",
            "^\\s*private\\s+\\w+\\s+\\w+;",
            "^\\s*public\\s+static\\s+void\\s+main",
            "^\\s*(public|private|protected)\\s+\\w+\\s+\\w+\\s*[;=\\(]",
        ],
        "go": [
            "^\\s*package\\s+\\w+",
            "^\\s*import\\s+\\(",
            "^\\s*func\\s+\\w+\\s*\\(",
            "^\\s*type\\s+\\w+\\s+struct\\s*\\{",
            "^\\s*var\\s+\\w+\\s+\\w+",
        ],
        "rust": [
            "^\\s*use\\s+\\w+",
            "^\\s*fn\\s+\\w+\\s*\\(",
            "^\\s*struct\\s+\\w+\\s*[\\{\\(]",
            "^\\s*impl\\s+\\w+",
            "^\\s*let\\s+(mut\\s+)?\\w+",
            "^\\s*pub\\s+(fn|struct|enum|trait)",
        ],
        "ruby": [
            "^\\s*require\\s+[\"\\']",
            "^\\s*require_relative\\s+[\"\\']",
            "^\\s*def\\s+\\w+",
            "^\\s*class\\s+\\w+",
            "^\\s*module\\s+\\w+",
            "^\\s*attr_(reader|writer|accessor)\\s+",
        ],
        "php": [
            "<\\?php",
            "^\\s*namespace\\s+[\\w\\\\\\\\]+;",
            "^\\s*use\\s+[\\w\\\\\\\\]+;",
            "^\\s*class\\s+\\w+",
            "^\\s*function\\s+\\w+\\s*\\(",
            "\\$\\w+\\s*=",
        ],
    }

    def detect_from_file(self, file_path: str) -> tuple[str, float]:
        """Detect language from file_path path and content."""
        path = Path(file_path)
        confidence = 0.0
        language = None
        ext = path.suffix.lower()
        if ext in self.EXTENSIONS:
            language = self.EXTENSIONS[ext]
            confidence = 0.8
        try:
            with Path(file_path).open(encoding="utf-8", errors="ignore") as f:
                content = f.read(4096)
            if content.startswith("#!"):
                first_line = content.split("\n")[0]
                for pattern, lang in self.SHEBANG_PATTERNS.items():
                    if re.search(pattern, first_line):
                        return lang, 0.95
            if language:
                content_lang, content_conf = self.detect_from_content(
                    content,
                    hint=language,
                )
                if content_lang == language:
                    confidence = min(0.95, confidence + content_conf * 0.2)
                elif content_conf > 0.8:
                    language = content_lang
                    confidence = content_conf
            else:
                language, confidence = self.detect_from_content(content)
        except OSError:
            pass
        if not language:
            language = "text"
            confidence = 0.1
        return language, confidence

    def detect_from_content(
        self,
        content: str,
        hint: str | None = None,
    ) -> tuple[str, float]:
        """Detect language from content alone."""
        if not content.strip():
            return "text", 0.1
        scores = defaultdict(float)
        if hint and hint in self.CONTENT_PATTERNS:
            scores[hint] = 0.2
        for language, patterns in self.CONTENT_PATTERNS.items():
            for pattern in patterns:
                matches = len(re.findall(pattern, content, re.MULTILINE))
                if matches:
                    scores[language] += matches * 0.1
        if "typescript" in scores and "javascript" in scores:
            scores["typescript"] += scores["javascript"] * 0.5
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                for lang in scores:
                    scores[lang] = min(0.95, scores[lang] / max_score)
            best_lang = max(scores.items(), key=lambda x: x[1])
            return best_lang
        return "text", 0.1

    def detect_multiple(self, content: str) -> list[tuple[str, float]]:
        """Detect multiple languages in content."""
        if not content.strip():
            return [("text", 1.0)]
        language_blocks = []
        markdown_blocks = re.findall(r"```(\\w+)?\\n(.*?)```", content, re.DOTALL)
        for lang, block in markdown_blocks:
            if lang:
                language_blocks.append((lang, len(block)))
            else:
                detected_lang, _ = self.detect_from_content(block)
                language_blocks.append((detected_lang, len(block)))
        script_blocks = re.findall(
            r"<script[^>]*>(.*?)</script>",
            content,
            re.DOTALL | re.IGNORECASE,
        )
        language_blocks.extend(("javascript", len(block)) for block in script_blocks)
        style_blocks = re.findall(
            r"<style[^>]*>(.*?)</style>",
            content,
            re.DOTALL | re.IGNORECASE,
        )
        language_blocks.extend(("css", len(block)) for block in style_blocks)
        if re.search(r"<[A-Z]\\w*[^>]*>", content) and re.search(
            r"(import|export|const|let|var)",
            content,
        ):
            ts_patterns = len(
                re.findall(
                    r":\\s*(string|number|boolean|any|void)\\s*[;,\\)\\}]",
                    content,
                ),
            )
            if ts_patterns > 2:
                language_blocks.append(("typescript", len(content)))
            else:
                language_blocks.append(("javascript", len(content)))
        if language_blocks:
            total_size = sum(size for _, size in language_blocks)
            language_percentages = defaultdict(float)
            for lang, size in language_blocks:
                language_percentages[lang] += size / total_size
            results = sorted(
                language_percentages.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            return results
        lang, _conf = self.detect_from_content(content)
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
        for root, dirs, files in os.walk(project_root):
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
            for filename in files:
                file_path = Path(root) / filename
                analysis["file_count"] += 1
                if file_path in framework_files:
                    for indicator in framework_files[file_path]:
                        analysis["framework_indicators"][indicator] = True
                try:
                    lang, confidence = self.detector.detect_from_file(str(file_path))
                    if confidence > 0.5:
                        analysis["languages"][lang] += 1
                    try:
                        with Path(file_path).open(
                            encoding="utf-8",
                            errors="ignore",
                        ) as f:
                            analysis["total_lines"] += sum(1 for _ in f)
                    except (OSError, FileNotFoundError, IndexError):
                        pass
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
        analysis["project_type"] = self._determine_project_type(analysis)
        analysis["languages"] = dict(analysis["languages"])
        return analysis

    @staticmethod
    def _determine_project_type(analysis: dict[str, Any]) -> str:
        """Determine project type from analysis."""
        indicators = analysis["framework_indicators"]
        structure = analysis["structure"]
        languages = analysis["languages"]

        # Check project types in priority order
        type_checks = [
            (
                lambda: structure["has_frontend"] and structure["has_backend"],
                "fullstack_webapp",
            ),
            (
                lambda: structure["has_frontend"]
                and MultiLanguageProcessor._is_node_app(indicators),
                "node_application",
            ),
            (lambda: structure["has_frontend"], "frontend_webapp"),
            (
                lambda: structure["has_backend"] and not structure["has_frontend"],
                "backend_api",
            ),
            (
                lambda: MultiLanguageProcessor._is_library(indicators, analysis),
                "library",
            ),
            (
                lambda: MultiLanguageProcessor._is_mobile_app(languages, analysis),
                "mobile_app",
            ),
            (
                lambda: "python" in languages and "jupyter" in languages,
                "data_science_project",
            ),
        ]

        for check_func, project_type in type_checks:
            if check_func():
                return project_type

        return "general_project"

    @staticmethod
    def _is_node_app(indicators: dict) -> bool:
        """Check if project is a Node application."""
        return "javascript" in indicators or (
            "typescript" in indicators and "node" in indicators
        )

    @staticmethod
    def _is_library(indicators: dict, analysis: dict) -> bool:
        """Check if project is a library."""
        return (
            any(key in indicators for key in ["npm", "python", "rust", "go"])
            and analysis["file_count"] < 50
        )

    @staticmethod
    def _is_mobile_app(languages: dict, analysis: dict) -> bool:
        """Check if project is a mobile app."""
        has_mobile_lang = (
            "swift" in languages or "kotlin" in languages or "java" in languages
        )
        project_path_str = str(analysis["project_path"]).lower()
        has_mobile_path = "android" in project_path_str or "ios" in project_path_str
        return has_mobile_lang and has_mobile_path

    @staticmethod
    def find_api_boundaries(chunks: list[CodeChunk]) -> list[dict[str, Any]]:
        """Find API boundaries between components."""
        api_boundaries = []
        backend_chunks = []
        frontend_chunks = []
        api_chunks = []
        for chunk in chunks:
            path_lower = chunk.file_path.lower()
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
            if chunk.language in {"python", "javascript", "typescript", "java", "go"}:
                rest_patterns = [
                    "@(app|router)\\.(get|post|put|delete|patch|route)\\(",
                    "@(Get|Post|Put|Delete|Patch)Mapping",
                    "router\\.(get|post|put|delete|patch)\\(",
                    "http\\.(Get|Post|Put|Delete|Patch)\\(",
                ]
                for pattern in rest_patterns:
                    if re.search(pattern, chunk.content):
                        endpoint_match = re.search(
                            r"[\"']([/\w\-\{\}:]+)[\"']",
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
                graphql_patterns = [
                    "type\\s+Query\\s*\\{",
                    "type\\s+Mutation\\s*\\{",
                    "@(Query|Mutation|Resolver)",
                ]
                api_boundaries.extend(
                    {
                        "type": "graphql_schema",
                        "chunk_id": chunk.chunk_id,
                        "language": chunk.language,
                        "file_path": chunk.file_path,
                    }
                    for pattern in graphql_patterns
                    if re.search(pattern, chunk.content)
                )
        api_boundaries.extend(
            {
                "type": "grpc_service",
                "chunk_id": chunk.chunk_id,
                "file_path": chunk.file_path,
            }
            for chunk in chunks
            if chunk.language in {"proto", "protobuf"} or ".proto" in chunk.file_path
        )
        return api_boundaries

    @classmethod
    def suggest_chunk_grouping(
        cls,
        chunks: list[CodeChunk],
    ) -> dict[str, list[CodeChunk]]:
        """Suggest how to group chunks for processing."""
        groupings = defaultdict(list)
        for chunk in chunks:
            path_parts = Path(chunk.file_path).parts
            feature = None
            for i, part in enumerate(path_parts):
                if part in {
                    "features",
                    "modules",
                    "components",
                    "services",
                    "domains",
                } and i + 1 < len(path_parts):
                    feature = path_parts[i + 1]
                    break
            if feature:
                groupings[f"feature_{feature}"].append(chunk)
            elif len(path_parts) > 1:
                groupings[f"module_{path_parts[0]}"].append(chunk)
            else:
                groupings["root"].append(chunk)
        for chunk in chunks:
            groupings[f"lang_{chunk.language}"].append(chunk)
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
        primary_lang, _ = self.detector.detect_from_file(file_path)
        if file_path.endswith((".jsx", ".tsx")):
            regions.extend(self._identify_jsx_regions(content, primary_lang))
        elif file_path.endswith((".html", ".htm")):
            regions.extend(self._identify_html_regions(content))
        elif file_path.endswith(".md"):
            regions.extend(self._identify_markdown_regions(content))
        elif file_path.endswith(".ipynb"):
            regions.extend(self._identify_notebook_regions(content))
        else:
            regions.extend(self._identify_embedded_regions(content, primary_lang))
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

    @classmethod
    def _identify_jsx_regions(
        cls,
        content: str,
        base_language: str,
    ) -> list[LanguageRegion]:
        """Identify JSX/TSX regions."""
        regions = []
        lines = content.split("\n")
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
        style_pattern = r"style\\s*=\\s*\\{\\{([^}]+)\\}\\}"
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

    @classmethod
    def _identify_html_regions(cls, content: str) -> list[LanguageRegion]:
        """Identify regions in HTML files."""
        regions = []
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
        script_pattern = "<script[^>]*>(.*?)</script>"
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
        style_pattern = "<style[^>]*>(.*?)</style>"
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

    @classmethod
    def _identify_markdown_regions(cls, content: str) -> list[LanguageRegion]:
        """Identify regions in Markdown files."""
        regions = []
        regions.append(
            LanguageRegion(
                language="markdown",
                start_pos=0,
                end_pos=len(content),
                start_line=1,
                end_line=content.count(
                    "\n",
                )
                + 1,
                embedding_type=None,
                parent_language=None,
            ),
        )
        code_block_pattern = r"```(\\w+)?\\n(.*?)```"
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

    @classmethod
    def _identify_notebook_regions(cls, content: str) -> list[LanguageRegion]:
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
                    language = "python"
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

    @classmethod
    def _identify_embedded_regions(
        cls,
        content: str,
        primary_language: str,
    ) -> list[LanguageRegion]:
        """Identify embedded language regions in regular source files."""
        regions = []
        sql_pattern = "[\"\\'](\\s*SELECT\\s+.*?\\s+FROM\\s+.*?)[\"\\']"
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
        graphql_pattern = "gql`([^`]+)`|graphql\\([\"\\']([^\"\\']+)[\"\\']\\)"
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
        string_pattern = "[\"\\'](\\{.*?\\}|\\[.*?\\])[\"\\']"
        # Collect potential JSON regions first
        potential_json_regions = list(re.finditer(string_pattern, content, re.DOTALL))

        # Process JSON validation outside the loop
        for match in potential_json_regions:
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
            except (json.JSONDecodeError, ValueError):  # noqa: PERF203
                # Not valid JSON, skip
                pass
        return regions

    def process_mixed_file(
        self,
        file_path: str,
        _primary_language: str,
        content: str | None = None,
    ) -> list[CodeChunk]:
        """Process files with embedded languages."""
        if content is None:
            with Path(file_path).open(encoding="utf-8") as f:
                content = f.read()
        chunks = []
        regions = self.identify_language_regions(file_path, content)
        for region in regions:
            if region.language not in self._supported_languages:
                continue
            region_content = content[region.start_pos : region.end_pos]
            try:
                parser = get_parser(region.language)
                parser.parse(region_content.encode())
                region_chunks = chunk_file(
                    file_path=file_path,
                    content=region_content,
                    language=region.language,
                )
                for chunk in region_chunks:
                    chunk.start_line += region.start_line - 1
                    chunk.end_line += region.start_line - 1
                    chunk.byte_start += region.start_pos
                    chunk.byte_end += region.start_pos
                    if region.embedding_type:
                        chunk.metadata["embedding_type"] = region.embedding_type.value
                    if region.parent_language:
                        chunk.metadata["parent_language"] = region.parent_language
                    chunks.append(chunk)
            except (FileNotFoundError, IndexError, KeyError) as e:
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

    @staticmethod
    def extract_embedded_code(
        content: str,
        host_language: str,
        target_language: str,
    ) -> list[tuple[str, int, int]]:
        """Extract embedded code snippets."""
        snippets = []
        if host_language == "html" and target_language == "javascript":
            pattern = "<script[^>]*>(.*?)</script>"
            snippets.extend(
                (match.group(1), match.start(1), match.end(1))
                for match in re.finditer(pattern, content, re.DOTALL | re.IGNORECASE)
            )
            event_pattern = "on\\w+\\s*=\\s*[\"\\']([^\"\\']+)[\"\\']"
            snippets.extend(
                (match.group(1), match.start(1), match.end(1))
                for match in re.finditer(event_pattern, content)
            )
        elif host_language == "html" and target_language == "css":
            pattern = "<style[^>]*>(.*?)</style>"
            snippets.extend(
                (match.group(1), match.start(1), match.end(1))
                for match in re.finditer(pattern, content, re.DOTALL | re.IGNORECASE)
            )
            style_pattern = "style\\s*=\\s*[\"\\']([^\"\\']+)[\"\\']"
            snippets.extend(
                (match.group(1), match.start(1), match.end(1))
                for match in re.finditer(style_pattern, content)
            )
        elif host_language == "markdown" and target_language:
            pattern = f"```{target_language}\\n(.*?)```"
            snippets.extend(
                (match.group(1), match.start(1), match.end(1))
                for match in re.finditer(pattern, content, re.DOTALL)
            )
        elif target_language == "sql":
            sql_patterns = [
                "[\"\\'](\\s*SELECT\\s+.*?\\s+FROM\\s+.*?)[\"\\']",
                "[\"\\'](\\s*INSERT\\s+INTO\\s+.*?)[\"\\']",
                "[\"\\'](\\s*UPDATE\\s+.*?\\s+SET\\s+.*?)[\"\\']",
                "[\"\\'](\\s*DELETE\\s+FROM\\s+.*?)[\"\\']",
            ]
            for pattern in sql_patterns:
                snippets.extend(
                    (match.group(1), match.start(1), match.end(1))
                    for match in re.finditer(
                        pattern,
                        content,
                        re.IGNORECASE | re.DOTALL,
                    )
                )
        elif target_language == "graphql":
            patterns = [
                "gql`([^`]+)`",
                "graphql\\([\"\\']([^\"\\']+)[\"\\']\\)",
                "query\\s*=\\s*[\"\\']([^\"\\']+)[\"\\']",
            ]
            for pattern in patterns:
                snippets.extend(
                    (match.group(1), match.start(1), match.end(1))
                    for match in re.finditer(pattern, content)
                )
        return snippets

    @classmethod
    def cross_language_references(
        cls,
        chunks: list[CodeChunk],
    ) -> list[CrossLanguageReference]:
        """Find references across language boundaries."""
        references = []
        chunks_by_name = defaultdict(list)
        api_endpoints = defaultdict(list)
        imports_exports = defaultdict(list)
        for chunk in chunks:
            if chunk.node_type in {
                "function_definition",
                "class_definition",
                "method_definition",
            }:
                name_match = re.search(
                    r"(?:function|class|def)\\s+(\\w+)",
                    chunk.content,
                )
                if name_match:
                    name = name_match.group(1)
                    chunks_by_name[name].append(chunk)
            if chunk.language in {
                "python",
                "javascript",
                "typescript",
                "java",
            }:
                endpoint_patterns = [
                    "[\"\\']([/\\w\\-\\{\\}:]+)[\"\\']",
                    "@\\w+\\([\"\\']([/\\w\\-\\{\\}:]+)[\"\\']",
                ]
                for pattern in endpoint_patterns:
                    for match in re.finditer(pattern, chunk.content):
                        path = match.group(1)
                        if path.startswith("/"):
                            api_endpoints[path].append(chunk)
            if chunk.language in {"javascript", "typescript", "python"}:
                import_patterns = [
                    "import\\s+.*?\\s+from\\s+[\"\\']([^\"\\']+)[\"\\']",
                    "from\\s+([^\\s]+)\\s+import",
                    "require\\([\"\\']([^\"\\']+)[\"\\']\\)",
                ]
                for pattern in import_patterns:
                    for match in re.finditer(pattern, chunk.content):
                        module = match.group(1)
                        imports_exports[module].append(chunk)
        for chunk in chunks:
            if chunk.language in {"javascript", "typescript"}:
                api_call_patterns = [
                    "fetch\\([\"\\']([/\\w\\-\\{\\}:]+)[\"\\']",
                    "fetch\\(`([/\\w\\-\\{\\}:]+)",
                    "axios\\.\\w+\\([\"\\']([/\\w\\-\\{\\}:]+)[\"\\']",
                    "axios\\.\\w+\\(`([/\\w\\-\\{\\}:]+)",
                    "\\$\\.ajax\\(.*?url:\\s*[\"\\']([/\\w\\-\\{\\}:]+)[\"\\']",
                ]
                for pattern in api_call_patterns:
                    for match in re.finditer(pattern, chunk.content):
                        endpoint = match.group(1)
                        if endpoint in api_endpoints:
                            references.extend(
                                CrossLanguageReference(
                                    source_chunk=chunk,
                                    target_chunk=target_chunk,
                                    reference_type="api_call",
                                    confidence=0.8,
                                )
                                for target_chunk in api_endpoints[endpoint]
                                if target_chunk.language != chunk.language
                            )
            if chunk.node_type in {
                "interface_declaration",
                "type_alias_declaration",
                "struct_declaration",
                "class_definition",
            }:
                type_patterns = [
                    "(?:interface|type|class|struct)\\s+(\\w+)",
                    "type\\s+(\\w+)\\s+struct",
                ]
                type_name = None
                for pattern in type_patterns:
                    match = re.search(pattern, chunk.content)
                    if match:
                        type_name = match.group(1)
                        break
                if type_name:
                    for other_chunk in chunks:
                        if (
                            other_chunk != chunk
                            and other_chunk.language != chunk.language
                        ) and other_chunk.node_type in {
                            "interface_declaration",
                            "type_alias_declaration",
                            "struct_declaration",
                            "class_definition",
                        }:
                            for pattern in type_patterns:
                                other_match = re.search(pattern, other_chunk.content)
                                if (
                                    other_match
                                    and other_match.group(
                                        1,
                                    )
                                    == type_name
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
            if "sql" in chunk.content.lower() or "query" in chunk.content.lower():
                table_patterns = [
                    "FROM\\s+(\\w+)",
                    "INSERT\\s+INTO\\s+(\\w+)",
                    "UPDATE\\s+(\\w+)",
                    "CREATE\\s+TABLE\\s+(\\w+)",
                ]
                for pattern in table_patterns:
                    for match in re.finditer(pattern, chunk.content, re.IGNORECASE):
                        table_name = match.group(1)
                        references.extend(
                            CrossLanguageReference(
                                source_chunk=chunk,
                                target_chunk=other_chunk,
                                reference_type="database_reference",
                                confidence=0.5,
                            )
                            for other_chunk in chunks
                            if (
                                other_chunk != chunk
                                and table_name in other_chunk.content
                            )
                            and other_chunk.language != chunk.language
                        )
        return references

    def group_by_feature(self, chunks: list[CodeChunk]) -> dict[str, list[CodeChunk]]:
        """Group chunks from different languages by feature."""
        feature_groups = defaultdict(list)
        path_features = {}
        for chunk in chunks:
            path = Path(chunk.file_path)
            parts = path.parts
            feature_name = None
            for i, part in enumerate(parts):
                if part in {
                    "features",
                    "modules",
                    "components",
                    "domains",
                    "services",
                } and i + 1 < len(parts):
                    feature_name = parts[i + 1]
                    break
            if feature_name:
                path_features[chunk.chunk_id] = feature_name
                feature_groups[feature_name].append(chunk)
        name_patterns = defaultdict(list)
        for chunk in chunks:
            if chunk.node_type in {"class_definition", "function_definition"}:
                name_match = re.search(
                    r"(?:class|function|def)\\s+(\\w+)",
                    chunk.content,
                )
                if name_match:
                    name = name_match.group(1)
                    base_name = re.sub(
                        r"(Controller|Service|Repository|Component|Model|View)$",
                        "",
                        name,
                    )
                    name_patterns[base_name.lower()].append(chunk)
        for base_name, name_chunks in name_patterns.items():
            if len(name_chunks) > 1:
                merged = False
                for feature_chunks in feature_groups.values():
                    if any(chunk in feature_chunks for chunk in name_chunks):
                        for chunk in name_chunks:
                            if chunk not in feature_chunks:
                                feature_chunks.append(chunk)
                        merged = True
                        break
                if not merged:
                    feature_groups[f"entity_{base_name}"] = name_chunks
        references = self.cross_language_references(chunks)
        reference_groups = defaultdict(set)
        for ref in references:
            source_feature = None
            target_feature = None
            for feature, feature_chunks in feature_groups.items():
                if ref.source_chunk in feature_chunks:
                    source_feature = feature
                if ref.target_chunk in feature_chunks:
                    target_feature = feature
            if source_feature and target_feature and source_feature != target_feature:
                reference_groups[source_feature].add(target_feature)
                reference_groups[target_feature].add(source_feature)
        for feature, related in reference_groups.items():
            if feature in feature_groups:
                for chunk in feature_groups[feature]:
                    chunk.metadata["related_features"] = list(related)
        return dict(feature_groups)
