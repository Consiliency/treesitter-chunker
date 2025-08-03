"""Sliding window fallback system with processor integration.

This module provides a unified fallback system that integrates various text
processors (sliding window, markdown, log, config) with automatic processor
selection based on file type and content.
"""
import importlib
import inspect
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from chunker.chunker_config import ChunkerConfig
from chunker.interfaces.fallback import FallbackConfig
from chunker.processors.config import ConfigProcessor
from chunker.processors.logs import LogProcessor
from chunker.processors.markdown import MarkdownProcessor
from chunker.types import CodeChunk

from .base import FallbackChunker
from .detection.file_type import FileType, FileTypeDetector

logger = logging.getLogger(__name__)


class ProcessorType(Enum):
    """Types of text processors available."""
    SLIDING_WINDOW = "sliding_window"
    MARKDOWN = "markdown"
    LOG = "log"
    CONFIG = "config"
    GENERIC = "generic"
    CUSTOM = "custom"


@dataclass
class ProcessorInfo:
    """Information about a registered processor."""
    name: str
    processor_type: ProcessorType
    processor_class: type["TextProcessor"]
    supported_file_types: set[FileType]
    supported_extensions: set[str]
    priority: int = 50
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)


class TextProcessor(ABC):
    """Base class for all text processors."""

    def __init__(self, config: (dict[str, Any] | None) = None):
        """Initialize processor with configuration."""
        self.config = config or {}

    @staticmethod
    @abstractmethod
    def can_process(content: str, file_path: str) -> bool:
        """Check if this processor can handle the content.

        Args:
            content: File content
            file_path: Path to the file

        Returns:
            True if processor can handle this content
        """

    @staticmethod
    @abstractmethod
    def process(content: str, file_path: str) -> list[CodeChunk]:
        """Process content into chunks.

        Args:
            content: File content
            file_path: Path to the file

        Returns:
            List of code chunks
        """

    def get_metadata(self) -> dict[str, Any]:
        """Get processor metadata.

        Returns:
            Dictionary with processor information
        """
        return {"processor_type": self.__class__.__name__, "config": self.
            config}


class ProcessorRegistry:
    """Registry for managing text processors."""

    def __init__(self):
        """Initialize the processor registry."""
        self._processors: dict[str, ProcessorInfo] = {}
        self._file_type_map: dict[FileType, list[str]] = {}
        self._extension_map: dict[str, list[str]] = {}
        self._processor_cache: dict[str, TextProcessor] = {}

    def register(self, processor_info: ProcessorInfo) -> None:
        """Register a new processor.

        Args:
            processor_info: Information about the processor
        """
        name = processor_info.name
        if name in self._processors:
            logger.warning("Overwriting existing processor: %s", name)
        self._processors[name] = processor_info
        for file_type in processor_info.supported_file_types:
            if file_type not in self._file_type_map:
                self._file_type_map[file_type] = []
            self._file_type_map[file_type].append(name)
        for ext in processor_info.supported_extensions:
            if ext not in self._extension_map:
                self._extension_map[ext] = []
            self._extension_map[ext].append(name)
        logger.info("Registered processor: %s", name)

    def unregister(self, name: str) -> None:
        """Unregister a processor.

        Args:
            name: Processor name
        """
        if name not in self._processors:
            return
        processor_info = self._processors[name]
        for file_type in processor_info.supported_file_types:
            if file_type in self._file_type_map:
                self._file_type_map[file_type].remove(name)
        for ext in processor_info.supported_extensions:
            if ext in self._extension_map:
                self._extension_map[ext].remove(name)
        if name in self._processor_cache:
            del self._processor_cache[name]
        del self._processors[name]
        logger.info("Unregistered processor: %s", name)

    def get_processor(self, name: str) -> (TextProcessor | None):
        """Get a processor instance by name.

        Args:
            name: Processor name

        Returns:
            Processor instance or None
        """
        if name not in self._processors:
            return None
        if name in self._processor_cache:
            return self._processor_cache[name]
        processor_info = self._processors[name]
        if not processor_info.enabled:
            return None
        try:
            processor = processor_info.processor_class(processor_info.config)
            self._processor_cache[name] = processor
            return processor
        except (FileNotFoundError, IndexError, KeyError) as e:
            logger.error("Failed to create processor %s: %s", name, e)
            return None

    def find_processors(self, file_path: str, file_type: (FileType | None) = None,
        ) -> list[str]:
        """Find suitable processors for a file.

        Args:
            file_path: Path to the file
            file_type: Optional file type hint

        Returns:
            List of processor names sorted by priority
        """
        candidates = set()
        if file_type and file_type in self._file_type_map:
            candidates.update(self._file_type_map[file_type])
        ext = os.path.splitext(file_path)[1].lower()
        if ext in self._extension_map:
            candidates.update(self._extension_map[ext])
        enabled_processors = [(name, self._processors[name].priority) for
            name in candidates if self._processors[name].enabled]
        enabled_processors.sort(key=lambda x: x[1], reverse=True)
        return [name for name, _ in enabled_processors]

    def list_processors(self) -> list[ProcessorInfo]:
        """List all registered processors.

        Returns:
            List of processor information
        """
        return list(self._processors.values())


class ProcessorChain:
    """Chain multiple processors for complex file handling."""

    def __init__(self, processors: list[TextProcessor]):
        """Initialize processor chain.

        Args:
            processors: List of processors to chain
        """
        self.processors = processors

    def process(self, content: str, file_path: str) -> list[CodeChunk]:
        """Process content through the chain.

        Args:
            content: File content
            file_path: Path to the file

        Returns:
            Combined list of chunks from all processors
        """
        all_chunks = []
        remaining_content = content
        for processor in self.processors:
            if processor.can_process(remaining_content, file_path):
                chunks = processor.process(remaining_content, file_path)
                all_chunks.extend(chunks)
        return all_chunks


class SlidingWindowFallback(FallbackChunker):
    """Enhanced fallback system with sliding window and processor integration."""

    def __init__(self, config: (FallbackConfig | None) = None, chunker_config:
        (ChunkerConfig | None) = None):
        """Initialize sliding window fallback.

        Args:
            config: Fallback configuration
            chunker_config: Overall chunker configuration
        """
        super().__init__(config)
        self.chunker_config = chunker_config
        self.registry = ProcessorRegistry()
        self.detector = FileTypeDetector()
        self._load_builtin_processors()
        if chunker_config:
            self._load_custom_processors()

    def _load_builtin_processors(self) -> None:
        """Load built-in processors dynamically."""
        try:
            processor_info = ProcessorInfo(name="markdown_processor",
                processor_type=ProcessorType.MARKDOWN, processor_class=self
                ._create_processor_adapter_for_specialized(
                MarkdownProcessor), supported_file_types={FileType.MARKDOWN,
                }, supported_extensions={".md", ".markdown"}, priority=50)
            self.registry.register(processor_info)
            logger.info("Registered MarkdownProcessor")
        except ImportError as e:
            logger.debug("Could not import MarkdownProcessor: %s", e)
        try:
            processor_info = ProcessorInfo(name="log_processor",
                processor_type=ProcessorType.LOG, processor_class=self.
                _create_processor_adapter_for_specialized(LogProcessor),
                supported_file_types={FileType.LOG}, supported_extensions={
                ".log"}, priority=50)
            self.registry.register(processor_info)
            logger.info("Registered LogProcessor")
        except ImportError as e:
            logger.debug("Could not import LogProcessor: %s", e)
        try:
            processor_info = ProcessorInfo(name="config_processor",
                processor_type=ProcessorType.CONFIG, processor_class=self.
                _create_processor_adapter_for_specialized(ConfigProcessor),
                supported_file_types={FileType.CONFIG, FileType.YAML,
                FileType.JSON}, supported_extensions={".ini", ".cfg",
                ".conf", ".yaml", ".yml", ".json", ".toml"}, priority=50)
            self.registry.register(processor_info)
            logger.info("Registered ConfigProcessor")
        except ImportError as e:
            logger.debug("Could not import ConfigProcessor: %s", e)
        processor_modules = [("sliding_window_processor", ProcessorType.
            SLIDING_WINDOW, {FileType.TEXT}, {".txt", ".text"}), (
            "markdown_processor", ProcessorType.MARKDOWN, {FileType.
            MARKDOWN}, {".md", ".markdown"}), ("log_processor",
            ProcessorType.LOG, {FileType.LOG}, {".log"}), (
            "config_processor", ProcessorType.CONFIG, {FileType.CONFIG,
            FileType.YAML, FileType.JSON}, {".ini", ".cfg", ".conf",
            ".yaml", ".yml", ".json", ".toml"})]
        for module_name, proc_type, file_types, extensions in processor_modules:
            try:
                module = importlib.import_module(
                    f"chunker.sliding_window.{module_name}")
                for _name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, TextProcessor,
                        ) and obj != TextProcessor:
                        processor_info = ProcessorInfo(name=module_name +
                            "_sliding", processor_type=proc_type,
                            processor_class=obj, supported_file_types=file_types, supported_extensions=extensions,
                            priority=40)
                        self.registry.register(processor_info)
                        break
            except ImportError as e:
                logger.debug("Could not import %s: %s", module_name, e)
                self._load_strategy_processor(module_name, proc_type,
                    file_types, extensions)

    def _load_strategy_processor(self, name: str, proc_type: ProcessorType,
        file_types: set[FileType], extensions: set[str]) -> None:
        """Load processor from strategies directory."""
        try:
            strategy_map = {"markdown_processor": "markdown",
                "log_processor": "log_chunker"}
            if name in strategy_map:
                module = importlib.import_module(
                    f"chunker.fallback.strategies.{strategy_map[name]}")
                for _class_name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, FallbackChunker,
                        ) and obj != FallbackChunker:
                        adapter_class = self._create_processor_adapter(obj)
                        processor_info = ProcessorInfo(name=name,
                            processor_type=proc_type, processor_class=adapter_class, supported_file_types=file_types,
                            supported_extensions=extensions, priority=40)
                        self.registry.register(processor_info)
                        break
        except ImportError as e:
            logger.debug("Could not load strategy processor %s: %s", name, e)

    def _create_processor_adapter(fallback_class: type[FallbackChunker],
        ) -> type[TextProcessor]:
        """Create a TextProcessor adapter for a FallbackChunker."""

        class ProcessorAdapter(TextProcessor):

            def __init__(self, config: (dict[str, Any] | None) = None):
                super().__init__(config)
                self.fallback = fallback_class()

            def can_process(self, _content: str, file_path: str) -> bool:
                return self.fallback.can_handle(file_path, "")

            def process(self, content: str, file_path: str) -> list[CodeChunk]:
                return self.fallback.chunk_text(content, file_path)
        return ProcessorAdapter

    def _create_processor_adapter_for_specialized(processor_class: type,
        ) -> type[TextProcessor]:
        """Create a TextProcessor adapter for a SpecializedProcessor."""

        class SpecializedProcessorAdapter(TextProcessor):

            def __init__(self, config: (dict[str, Any] | None) = None):
                super().__init__(config)
                self.processor = processor_class(config)

            def can_process(self, content: str, file_path: str) -> bool:
                return self.processor.can_handle(file_path, content)

            def process(self, content: str, file_path: str) -> list[CodeChunk]:
                chunks = self.processor.process(content, file_path)
                code_chunks = []
                for chunk in chunks:
                    if hasattr(chunk, "content"):
                        code_chunk = CodeChunk(language=chunk.chunk_type,
                            file_path=file_path, node_type=chunk.chunk_type,
                            start_line=chunk.start_line, end_line=chunk.
                            end_line, byte_start=chunk.start_byte, byte_end=chunk.end_byte, parent_context=chunk.metadata.
                            get("parent_context", ""), content=chunk.
                            content, metadata=chunk.metadata)
                        code_chunks.append(code_chunk)
                    else:
                        code_chunks.append(chunk)
                return code_chunks
        return SpecializedProcessorAdapter

    def _load_custom_processors(self) -> None:
        """Load custom processors from configuration."""
        if not self.chunker_config:
            return
        processor_config = self.chunker_config.data.get("processors", {})
        for plugin_dir in self.chunker_config.plugin_dirs:
            self._scan_plugin_directory(plugin_dir)
        for proc_name, config in processor_config.items():
            if proc_name in self.registry._processors:
                proc_info = self.registry._processors[proc_name]
                if "enabled" in config:
                    proc_info.enabled = config["enabled"]
                if "priority" in config:
                    proc_info.priority = config["priority"]
                if "config" in config:
                    proc_info.config.update(config["config"])

    @staticmethod
    def _scan_plugin_directory(directory: Path) -> None:
        """Scan directory for processor plugins."""
        if not directory.exists():
            return
        for file_path in directory.glob("*_processor.py"):
            try:
                spec = importlib.util.spec_from_file_location(file_path.
                    stem, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                for _name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, TextProcessor,
                        ) and obj != TextProcessor and hasattr(obj,
                        "processor_info"):
                        info = obj.processor_info()
                        self.registry.register(info)
            except (AttributeError, FileNotFoundError, IndexError) as e:
                logger.error("Failed to load processor from %s: %s",
                    file_path, e)

    @staticmethod
    def chunk_text(content: str, file_path: str, language: (str | None) = None,
        ) -> list[CodeChunk]:
        """Chunk content using appropriate processor.

        Args:
            content: Content to chunk
            file_path: Path to the file
            language: Language hint (if available)

        Returns:
            List of chunks
        """
        file_type = self.detector.detect_file_type(file_path)
        processor_names = self.registry.find_processors(file_path, file_type)
        for proc_name in processor_names:
            processor = self.registry.get_processor(proc_name)
            if processor and processor.can_process(content, file_path):
<<<<<<< HEAD
                logger.info("Using processor '%s' for %s", proc_name, file_path)

=======
                logger.info("Using processor '%s' for %s" % (proc_name,
                    file_path))
>>>>>>> origin/main
                try:
                    chunks = processor.process(content, file_path)
                    for chunk in chunks:
                        if not hasattr(chunk, "metadata"):
                            chunk.metadata = {}
                        chunk.metadata["processor"] = proc_name
                        chunk.metadata["processor_type"
                            ] = self.registry._processors[proc_name
                            ].processor_type.value
                    return chunks
                except (AttributeError, FileNotFoundError, IndexError) as e:
<<<<<<< HEAD
                    logger.error("Processor '%s' failed: %s", proc_name, e)
=======
                    logger.error("Processor '%s' failed: %s" % (proc_name, e))
>>>>>>> origin/main
                    continue
        logger.warning(
<<<<<<< HEAD
            "No suitable processor found for %s, using line-based chunking",
            file_path,
        )
=======
            "No suitable processor found for %s, using line-based chunking", file_path)
>>>>>>> origin/main
        return super().chunk_text(content, file_path, language)

    @staticmethod
    def get_processor_info(file_path: str) -> dict[str, Any]:
        """Get information about which processor would be used.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with processor selection information
        """
        file_type = self.detector.detect_file_type(file_path)
        processor_names = self.registry.find_processors(file_path, file_type)
        return {"file_type": file_type.value, "available_processors":
            processor_names, "processors": [{"name": name, "type": self.
            registry._processors[name].processor_type.value, "priority":
            self.registry._processors[name].priority, "enabled": self.
            registry._processors[name].enabled} for name in processor_names]}

    @staticmethod
    def enable_processor(name: str) -> None:
        """Enable a processor.

        Args:
            name: Processor name
        """
        if name in self.registry._processors:
            self.registry._processors[name].enabled = True

    @staticmethod
    def disable_processor(name: str) -> None:
        """Disable a processor.

        Args:
            name: Processor name
        """
        if name in self.registry._processors:
            self.registry._processors[name].enabled = False

    @staticmethod
    def register_custom_processor(name: str, processor_class: type[
        TextProcessor], file_types: set[FileType], extensions: set[str],
        priority: int = 50) -> None:
        """Register a custom processor at runtime.

        Args:
            name: Processor name
            processor_class: Processor class
            file_types: Supported file types
            extensions: Supported file extensions
            priority: Processor priority
        """
        processor_info = ProcessorInfo(name=name, processor_type=ProcessorType.CUSTOM, processor_class=processor_class,
            supported_file_types=file_types, supported_extensions=extensions, priority=priority)
        self.registry.register(processor_info)

    @staticmethod
    def create_processor_chain(processor_names: list[str]) -> (ProcessorChain |
        None):
        """Create a processor chain for hybrid processing.

        Args:
            processor_names: List of processor names to chain

        Returns:
            ProcessorChain instance or None if any processor not found
        """
        processors = []
        for name in processor_names:
            processor = self.registry.get_processor(name)
            if not processor:
<<<<<<< HEAD
                logger.error("Processor '%s' not found for chain", name)
=======
                logger.error("Processor '%s' not found for chain" % name)
>>>>>>> origin/main
                return None
            processors.append(processor)
        return ProcessorChain(processors)

    @staticmethod
    def can_chunk(_file_path: str) -> bool:
        """Check if this fallback can chunk the given file.

        This is an alias for compatibility with tests and other interfaces.

        Args:
            file_path: Path to the file

        Returns:
            True (sliding window fallback can always chunk text files)
        """
        return True

    @staticmethod
    def chunk_file(file_path: str) -> list[CodeChunk]:
        """Chunk a file by reading its content.

        Args:
            file_path: Path to the file to chunk

        Returns:
            List of code chunks
        """
        with Path(file_path).open(encoding="utf-8") as f:
            content = f.read()
        return self.chunk_text(content, file_path)


class GenericSlidingWindowProcessor(TextProcessor):
    """Generic sliding window processor for any text file."""

    def __init__(self, config: (dict[str, Any] | None) = None):
        """Initialize with configuration.

        Config options:
            window_size: Size of sliding window in characters
            overlap: Overlap between windows in characters
            min_window_size: Minimum window size
            preserve_words: Try to preserve word boundaries
        """
        super().__init__(config)
        self.window_size = self.config.get("window_size", 1000)
        self.overlap = self.config.get("overlap", 100)
        self.min_window_size = self.config.get("min_window_size", 100)
        self.preserve_words = self.config.get("preserve_words", True)

    @staticmethod
    def can_process(_content: str, _file_path: str) -> bool:
        """Can process any text content."""
        return True

    def process(self, content: str, file_path: str) -> list[CodeChunk]:
        """Process content using sliding window."""
        chunks = []
        content_length = len(content)
        if content_length <= self.window_size:
            chunk = CodeChunk(language="text", file_path=file_path,
                node_type="sliding_window", start_line=1, end_line=content.
                count("\n") + 1, byte_start=0, byte_end=content_length,
                parent_context="full_content", content=content)
            return [chunk]
        position = 0
        chunk_index = 0
        while position < content_length:
            window_start = position
            window_end = min(position + self.window_size, content_length)
            if self.preserve_words and window_end < content_length:
                for i in range(window_end, max(window_start, window_end -
                    50), -1):
                    if content[i].isspace():
                        window_end = i
                        break
            window_content = content[window_start:window_end]
            lines_before = content[:window_start].count("\n")
            start_line = lines_before + 1
            end_line = start_line + window_content.count("\n")
            chunk = CodeChunk(language="text", file_path=file_path,
                node_type="sliding_window", start_line=start_line, end_line=end_line, byte_start=window_start, byte_end=window_end,
                parent_context=f"window_{chunk_index}", content=window_content)
            chunks.append(chunk)
            position = window_end - self.overlap
            chunk_index += 1
            if position <= window_start:
                position = window_start + 1
        return chunks


def _create_generic_processor_info() -> ProcessorInfo:
    """Create processor info for generic sliding window."""
    return ProcessorInfo(name="generic_sliding_window", processor_type=ProcessorType.GENERIC, processor_class=GenericSlidingWindowProcessor, supported_file_types=set(FileType),
        supported_extensions=set(), priority=10)
