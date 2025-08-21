"""Comprehensive troubleshooting database system for Phase 1.7.

This module provides a sophisticated troubleshooting database that stores, indexes,
and retrieves solutions for common and uncommon errors in the treesitter-chunker.
It includes fuzzy search capabilities, analytics, and multiple solution types.

Features:
- Comprehensive error cataloging with multiple solution types
- Advanced search with fuzzy matching and similarity scoring
- Analytics and pattern identification
- Success rate tracking and user feedback integration
- Import/export functionality with backup/restore capabilities
- Efficient indexing for large databases
- Multi-language support and customizable categories

Classes:
    TroubleshootingCategory: Enumeration of error categories
    SolutionType: Types of solutions available
    TroubleshootingEntry: Individual troubleshooting entries
    Solution: Individual solution with metadata
    TroubleshootingDatabase: Main database with CRUD operations
    TroubleshootingSearchEngine: Advanced search capabilities
    TroubleshootingAnalytics: Analytics and insights generation
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import pickle
import re
import sqlite3
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Third-party imports with fallbacks
try:
    from fuzzywuzzy import fuzz, process

    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize

    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False

# Set up logging
logger = logging.getLogger(__name__)


class TroubleshootingCategory(Enum):
    """Categories for troubleshooting entries."""

    SYNTAX_ERROR = "syntax_error"
    COMPATIBILITY_ERROR = "compatibility_error"
    GRAMMAR_ERROR = "grammar_error"
    INSTALLATION_ERROR = "installation_error"
    CONFIGURATION_ERROR = "configuration_error"
    PERFORMANCE_ERROR = "performance_error"
    MEMORY_ERROR = "memory_error"
    NETWORK_ERROR = "network_error"
    FILE_SYSTEM_ERROR = "file_system_error"
    DEPENDENCY_ERROR = "dependency_error"
    VERSION_ERROR = "version_error"
    ENCODING_ERROR = "encoding_error"
    PERMISSIONS_ERROR = "permissions_error"
    RUNTIME_ERROR = "runtime_error"
    UNKNOWN_ERROR = "unknown_error"


class SolutionType(Enum):
    """Types of solutions available."""

    QUICK_FIX = "quick_fix"
    DETAILED_GUIDE = "detailed_guide"
    WORKAROUND = "workaround"
    CONFIGURATION_CHANGE = "configuration_change"
    CODE_MODIFICATION = "code_modification"
    DEPENDENCY_UPDATE = "dependency_update"
    SYSTEM_REQUIREMENT = "system_requirement"
    ALTERNATIVE_APPROACH = "alternative_approach"
    DOCUMENTATION_LINK = "documentation_link"
    COMMUNITY_SOLUTION = "community_solution"


@dataclass
class Solution:
    """Individual solution with metadata and tracking."""

    solution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    solution_type: SolutionType = SolutionType.QUICK_FIX
    steps: list[str] = field(default_factory=list)
    code_examples: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    difficulty_level: int = 1  # 1-5 scale
    estimated_time: str = "5 minutes"
    success_rate: float = 0.0
    feedback_count: int = 0
    positive_feedback: int = 0
    tags: set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    created_by: str = "system"
    language_specific: str | None = None

    def __post_init__(self) -> None:
        """Validate solution data after initialization."""
        if not self.title:
            raise ValueError("Solution title cannot be empty")
        if not self.description:
            raise ValueError("Solution description cannot be empty")
        if (
            not isinstance(self.difficulty_level, int)
            or not 1 <= self.difficulty_level <= 5
        ):
            raise ValueError("Difficulty level must be an integer between 1 and 5")
        if (
            not isinstance(self.success_rate, (int, float))
            or not 0 <= self.success_rate <= 1
        ):
            raise ValueError("Success rate must be a float between 0 and 1")

    def add_feedback(self, positive: bool) -> None:
        """Add user feedback to the solution."""
        self.feedback_count += 1
        if positive:
            self.positive_feedback += 1
        self.success_rate = self.positive_feedback / self.feedback_count
        self.updated_at = datetime.now(UTC)

    def calculate_effectiveness_score(self) -> float:
        """Calculate overall effectiveness score based on success rate and feedback."""
        if self.feedback_count == 0:
            return 0.5  # Neutral score for no feedback

        # Base success rate
        base_score = self.success_rate

        # Confidence factor based on feedback count
        confidence = min(1.0, self.feedback_count / 10.0)

        # Adjust for difficulty (easier solutions get slight boost)
        difficulty_factor = 1.0 - (self.difficulty_level - 1) * 0.05

        return base_score * confidence * difficulty_factor

    def to_dict(self) -> dict[str, Any]:
        """Convert solution to dictionary for serialization."""
        return {
            "solution_id": self.solution_id,
            "title": self.title,
            "description": self.description,
            "solution_type": self.solution_type.value,
            "steps": self.steps,
            "code_examples": self.code_examples,
            "links": self.links,
            "prerequisites": self.prerequisites,
            "difficulty_level": self.difficulty_level,
            "estimated_time": self.estimated_time,
            "success_rate": self.success_rate,
            "feedback_count": self.feedback_count,
            "positive_feedback": self.positive_feedback,
            "tags": list(self.tags),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
            "language_specific": self.language_specific,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Solution:
        """Create solution from dictionary."""
        solution = cls(
            solution_id=data["solution_id"],
            title=data["title"],
            description=data["description"],
            solution_type=SolutionType(data["solution_type"]),
            steps=data["steps"],
            code_examples=data["code_examples"],
            links=data["links"],
            prerequisites=data["prerequisites"],
            difficulty_level=data["difficulty_level"],
            estimated_time=data["estimated_time"],
            success_rate=data["success_rate"],
            feedback_count=data["feedback_count"],
            positive_feedback=data["positive_feedback"],
            tags=set(data["tags"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            created_by=data["created_by"],
            language_specific=data.get("language_specific"),
        )
        return solution


@dataclass
class TroubleshootingEntry:
    """A comprehensive troubleshooting entry with multiple solutions."""

    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    category: TroubleshootingCategory = TroubleshootingCategory.UNKNOWN_ERROR
    error_patterns: list[str] = field(default_factory=list)
    symptoms: list[str] = field(default_factory=list)
    causes: list[str] = field(default_factory=list)
    solutions: list[Solution] = field(default_factory=list)
    related_entries: set[str] = field(default_factory=set)
    keywords: set[str] = field(default_factory=set)
    languages: set[str] = field(default_factory=set)
    severity: int = 3  # 1-5 scale (1=low, 5=critical)
    frequency: int = 0  # How often this problem occurs
    view_count: int = 0
    resolution_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    created_by: str = "system"

    def __post_init__(self) -> None:
        """Validate entry data after initialization."""
        if not self.title:
            raise ValueError("Entry title cannot be empty")
        if not self.description:
            raise ValueError("Entry description cannot be empty")
        if not isinstance(self.severity, int) or not 1 <= self.severity <= 5:
            raise ValueError("Severity must be an integer between 1 and 5")

        # Auto-generate keywords from title and description if not provided
        if not self.keywords:
            self.keywords = self._extract_keywords()

    def _extract_keywords(self) -> set[str]:
        """Extract keywords from title and description."""
        text = f"{self.title} {self.description}".lower()

        # Basic keyword extraction
        words = re.findall(r"\b\w+\b", text)

        # Filter out common words
        if NLTK_AVAILABLE:
            try:
                stop_words = set(stopwords.words("english"))
                words = [w for w in words if w not in stop_words and len(w) > 2]
            except:
                # Fallback if NLTK data not available
                common_words = {
                    "the",
                    "and",
                    "or",
                    "but",
                    "in",
                    "on",
                    "at",
                    "to",
                    "for",
                    "of",
                    "with",
                    "by",
                }
                words = [w for w in words if w not in common_words and len(w) > 2]
        else:
            common_words = {
                "the",
                "and",
                "or",
                "but",
                "in",
                "on",
                "at",
                "to",
                "for",
                "of",
                "with",
                "by",
            }
            words = [w for w in words if w not in common_words and len(w) > 2]

        return set(words[:20])  # Limit to top 20 keywords

    def add_solution(self, solution: Solution) -> None:
        """Add a solution to this entry."""
        if solution not in self.solutions:
            self.solutions.append(solution)
            self.updated_at = datetime.now(UTC)

    def remove_solution(self, solution_id: str) -> bool:
        """Remove a solution by ID."""
        for i, solution in enumerate(self.solutions):
            if solution.solution_id == solution_id:
                self.solutions.pop(i)
                self.updated_at = datetime.now(UTC)
                return True
        return False

    def get_best_solution(self) -> Solution | None:
        """Get the most effective solution based on success rate and feedback."""
        if not self.solutions:
            return None

        return max(self.solutions, key=lambda s: s.calculate_effectiveness_score())

    def record_view(self) -> None:
        """Record that this entry was viewed."""
        self.view_count += 1

    def record_resolution(self) -> None:
        """Record that this entry led to a successful resolution."""
        self.resolution_count += 1

    def calculate_relevance_score(self, query_terms: set[str]) -> float:
        """Calculate relevance score for search queries."""
        if not query_terms:
            return 0.0

        # Check title match (higher weight)
        title_words = set(self.title.lower().split())
        title_matches = len(title_words.intersection(query_terms))
        title_score = title_matches / len(query_terms) * 2.0

        # Check keyword match
        keyword_matches = len(self.keywords.intersection(query_terms))
        keyword_score = keyword_matches / len(query_terms) * 1.5

        # Check description match
        desc_words = set(self.description.lower().split())
        desc_matches = len(desc_words.intersection(query_terms))
        desc_score = desc_matches / len(query_terms) * 1.0

        # Check error pattern match
        pattern_score = 0.0
        for pattern in self.error_patterns:
            pattern_words = set(pattern.lower().split())
            pattern_matches = len(pattern_words.intersection(query_terms))
            pattern_score += pattern_matches / len(query_terms) * 1.2

        # Boost score based on popularity and success rate
        popularity_boost = min(1.0, (self.view_count + self.resolution_count) / 100.0)

        total_score = (title_score + keyword_score + desc_score + pattern_score) * (
            1.0 + popularity_boost
        )
        return min(10.0, total_score)  # Cap at 10

    def to_dict(self) -> dict[str, Any]:
        """Convert entry to dictionary for serialization."""
        return {
            "entry_id": self.entry_id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "error_patterns": self.error_patterns,
            "symptoms": self.symptoms,
            "causes": self.causes,
            "solutions": [solution.to_dict() for solution in self.solutions],
            "related_entries": list(self.related_entries),
            "keywords": list(self.keywords),
            "languages": list(self.languages),
            "severity": self.severity,
            "frequency": self.frequency,
            "view_count": self.view_count,
            "resolution_count": self.resolution_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TroubleshootingEntry:
        """Create entry from dictionary."""
        entry = cls(
            entry_id=data["entry_id"],
            title=data["title"],
            description=data["description"],
            category=TroubleshootingCategory(data["category"]),
            error_patterns=data["error_patterns"],
            symptoms=data["symptoms"],
            causes=data["causes"],
            related_entries=set(data["related_entries"]),
            keywords=set(data["keywords"]),
            languages=set(data["languages"]),
            severity=data["severity"],
            frequency=data["frequency"],
            view_count=data["view_count"],
            resolution_count=data["resolution_count"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            created_by=data["created_by"],
        )

        # Load solutions if present
        for solution_data in data.get("solutions", []):
            entry.solutions.append(Solution.from_dict(solution_data))

        return entry


class TroubleshootingSearchEngine:
    """Advanced search engine with fuzzy matching and similarity scoring."""

    def __init__(self, entries: list[TroubleshootingEntry]):
        """Initialize search engine with entries."""
        self.entries = entries
        self.keyword_index = self._build_keyword_index()
        self.pattern_index = self._build_pattern_index()

    def _build_keyword_index(self) -> dict[str, set[str]]:
        """Build an index of keywords to entry IDs."""
        index = defaultdict(set)
        for entry in self.entries:
            for keyword in entry.keywords:
                index[keyword.lower()].add(entry.entry_id)
        return dict(index)

    def _build_pattern_index(self) -> dict[str, set[str]]:
        """Build an index of error patterns to entry IDs."""
        index = defaultdict(set)
        for entry in self.entries:
            for pattern in entry.error_patterns:
                # Create n-grams for better matching
                words = pattern.lower().split()
                for i in range(len(words)):
                    for j in range(i + 1, min(i + 4, len(words) + 1)):
                        ngram = " ".join(words[i:j])
                        index[ngram].add(entry.entry_id)
        return dict(index)

    def search(
        self,
        query: str,
        category: TroubleshootingCategory | None = None,
        language: str | None = None,
        max_results: int = 10,
        min_score: float = 0.1,
    ) -> list[tuple[TroubleshootingEntry, float]]:
        """
        Perform comprehensive search with scoring.

        Args:
            query: Search query string
            category: Optional category filter
            language: Optional language filter
            max_results: Maximum number of results to return
            min_score: Minimum relevance score threshold

        Returns:
            List of (entry, score) tuples sorted by relevance
        """
        if not query.strip():
            return []

        query_terms = set(query.lower().split())
        candidates = set()

        # Find candidate entries using indexes
        for term in query_terms:
            # Exact keyword matches
            if term in self.keyword_index:
                candidates.update(self.keyword_index[term])

            # Pattern matches
            for pattern, entry_ids in self.pattern_index.items():
                if term in pattern:
                    candidates.update(entry_ids)

            # Fuzzy keyword matches
            if FUZZY_AVAILABLE:
                for keyword in self.keyword_index:
                    if fuzz.ratio(term, keyword) > 80:
                        candidates.update(self.keyword_index[keyword])

        # If no candidates found, fall back to all entries
        if not candidates:
            candidates = {entry.entry_id for entry in self.entries}

        # Score and filter candidates
        results = []
        for entry in self.entries:
            if entry.entry_id not in candidates:
                continue

            # Apply filters
            if category and entry.category != category:
                continue
            if language and language not in entry.languages and entry.languages:
                continue

            # Calculate relevance score
            score = self._calculate_comprehensive_score(entry, query, query_terms)

            if score >= min_score:
                results.append((entry, score))

        # Sort by score and limit results
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:max_results]

    def _calculate_comprehensive_score(
        self,
        entry: TroubleshootingEntry,
        query: str,
        query_terms: set[str],
    ) -> float:
        """Calculate comprehensive relevance score."""
        # Base relevance score
        relevance = entry.calculate_relevance_score(query_terms)

        # Fuzzy string matching
        fuzzy_score = 0.0
        if FUZZY_AVAILABLE:
            title_fuzzy = fuzz.partial_ratio(query.lower(), entry.title.lower()) / 100.0
            desc_fuzzy = (
                fuzz.partial_ratio(query.lower(), entry.description.lower()) / 100.0
            )
            fuzzy_score = max(title_fuzzy, desc_fuzzy) * 0.5

        # Pattern matching score
        pattern_score = 0.0
        for pattern in entry.error_patterns:
            similarity = self._string_similarity(query.lower(), pattern.lower())
            pattern_score = max(pattern_score, similarity)

        # Quality and popularity boosts
        solution_quality = 0.0
        if entry.solutions:
            avg_effectiveness = sum(
                s.calculate_effectiveness_score() for s in entry.solutions
            ) / len(entry.solutions)
            solution_quality = avg_effectiveness * 0.3

        popularity = (
            min(1.0, entry.view_count / 1000.0 + entry.resolution_count / 100.0) * 0.2
        )

        # Severity boost (higher severity = more important)
        severity_boost = entry.severity / 10.0

        total_score = (
            relevance
            + fuzzy_score
            + pattern_score
            + solution_quality
            + popularity
            + severity_boost
        )
        return total_score

    def _string_similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity using sequence matcher."""
        return SequenceMatcher(None, s1, s2).ratio()

    def find_similar_entries(
        self,
        entry: TroubleshootingEntry,
        max_results: int = 5,
    ) -> list[tuple[TroubleshootingEntry, float]]:
        """Find entries similar to the given entry."""
        results = []

        for other in self.entries:
            if other.entry_id == entry.entry_id:
                continue

            # Calculate similarity based on multiple factors
            keyword_overlap = len(entry.keywords.intersection(other.keywords))
            keyword_similarity = keyword_overlap / max(
                len(entry.keywords),
                len(other.keywords),
                1,
            )

            category_match = 1.0 if entry.category == other.category else 0.0

            language_overlap = len(entry.languages.intersection(other.languages))
            language_similarity = (
                language_overlap / max(len(entry.languages), len(other.languages), 1)
                if entry.languages or other.languages
                else 0.5
            )

            title_similarity = self._string_similarity(
                entry.title.lower(),
                other.title.lower(),
            )

            total_similarity = (
                keyword_similarity * 0.4
                + category_match * 0.3
                + language_similarity * 0.2
                + title_similarity * 0.1
            )

            if total_similarity > 0.3:
                results.append((other, total_similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:max_results]


class TroubleshootingDatabase:
    """Main troubleshooting database with CRUD operations and indexing."""

    def __init__(self, db_path: Path | None = None, in_memory: bool = False):
        """
        Initialize troubleshooting database.

        Args:
            db_path: Path to SQLite database file
            in_memory: Use in-memory database for testing
        """
        self.db_path = db_path or Path("troubleshooting.db")
        self.in_memory = in_memory
        self.entries: dict[str, TroubleshootingEntry] = {}
        self.search_engine: TroubleshootingSearchEngine | None = None

        # Initialize database
        self._init_database()
        self._load_entries()
        self._rebuild_search_index()

        logger.info(
            f"Initialized troubleshooting database with {len(self.entries)} entries",
        )

    def _init_database(self) -> None:
        """Initialize SQLite database schema."""
        db_path = ":memory:" if self.in_memory else str(self.db_path)

        with sqlite3.connect(db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS entries (
                    entry_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    error_patterns TEXT,
                    symptoms TEXT,
                    causes TEXT,
                    related_entries TEXT,
                    keywords TEXT,
                    languages TEXT,
                    severity INTEGER,
                    frequency INTEGER,
                    view_count INTEGER,
                    resolution_count INTEGER,
                    created_at TEXT,
                    updated_at TEXT,
                    created_by TEXT
                );
                
                CREATE TABLE IF NOT EXISTS solutions (
                    solution_id TEXT PRIMARY KEY,
                    entry_id TEXT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    solution_type TEXT,
                    steps TEXT,
                    code_examples TEXT,
                    links TEXT,
                    prerequisites TEXT,
                    difficulty_level INTEGER,
                    estimated_time TEXT,
                    success_rate REAL,
                    feedback_count INTEGER,
                    positive_feedback INTEGER,
                    tags TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    created_by TEXT,
                    language_specific TEXT,
                    FOREIGN KEY (entry_id) REFERENCES entries (entry_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_entries_category ON entries(category);
                CREATE INDEX IF NOT EXISTS idx_entries_severity ON entries(severity);
                CREATE INDEX IF NOT EXISTS idx_entries_view_count ON entries(view_count);
                CREATE INDEX IF NOT EXISTS idx_solutions_entry_id ON solutions(entry_id);
                CREATE INDEX IF NOT EXISTS idx_solutions_success_rate ON solutions(success_rate);
            """,
            )

    def _load_entries(self) -> None:
        """Load entries from database."""
        if self.in_memory:
            return  # No persistent storage for in-memory database

        db_path = str(self.db_path)

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Load entries
                cursor.execute("SELECT * FROM entries")
                for row in cursor.fetchall():
                    entry_data = dict(row)

                    # Parse JSON fields
                    for field in [
                        "error_patterns",
                        "symptoms",
                        "causes",
                        "related_entries",
                        "keywords",
                        "languages",
                    ]:
                        entry_data[field] = json.loads(entry_data[field] or "[]")

                    # Convert related_entries and keywords to sets
                    entry_data["related_entries"] = set(entry_data["related_entries"])
                    entry_data["keywords"] = set(entry_data["keywords"])
                    entry_data["languages"] = set(entry_data["languages"])

                    entry = TroubleshootingEntry.from_dict(entry_data)

                    # Load solutions for this entry
                    cursor.execute(
                        "SELECT * FROM solutions WHERE entry_id = ?",
                        (entry.entry_id,),
                    )
                    for solution_row in cursor.fetchall():
                        solution_data = dict(solution_row)

                        # Parse JSON fields
                        for field in [
                            "steps",
                            "code_examples",
                            "links",
                            "prerequisites",
                            "tags",
                        ]:
                            solution_data[field] = json.loads(
                                solution_data[field] or "[]",
                            )

                        solution_data["tags"] = set(solution_data["tags"])
                        solution = Solution.from_dict(solution_data)
                        entry.solutions.append(solution)

                    self.entries[entry.entry_id] = entry

        except sqlite3.Error as e:
            logger.error(f"Error loading entries from database: {e}")

    def _save_entry(self, entry: TroubleshootingEntry) -> None:
        """Save entry to database."""
        if self.in_memory:
            return  # No persistent storage for in-memory database

        db_path = str(self.db_path)

        try:
            with sqlite3.connect(db_path) as conn:
                # Save entry
                conn.execute(
                    """
                    INSERT OR REPLACE INTO entries (
                        entry_id, title, description, category, error_patterns,
                        symptoms, causes, related_entries, keywords, languages,
                        severity, frequency, view_count, resolution_count,
                        created_at, updated_at, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        entry.entry_id,
                        entry.title,
                        entry.description,
                        entry.category.value,
                        json.dumps(entry.error_patterns),
                        json.dumps(entry.symptoms),
                        json.dumps(entry.causes),
                        json.dumps(list(entry.related_entries)),
                        json.dumps(list(entry.keywords)),
                        json.dumps(list(entry.languages)),
                        entry.severity,
                        entry.frequency,
                        entry.view_count,
                        entry.resolution_count,
                        entry.created_at.isoformat(),
                        entry.updated_at.isoformat(),
                        entry.created_by,
                    ),
                )

                # Delete existing solutions for this entry
                conn.execute(
                    "DELETE FROM solutions WHERE entry_id = ?",
                    (entry.entry_id,),
                )

                # Save solutions
                for solution in entry.solutions:
                    conn.execute(
                        """
                        INSERT INTO solutions (
                            solution_id, entry_id, title, description, solution_type,
                            steps, code_examples, links, prerequisites, difficulty_level,
                            estimated_time, success_rate, feedback_count, positive_feedback,
                            tags, created_at, updated_at, created_by, language_specific
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            solution.solution_id,
                            entry.entry_id,
                            solution.title,
                            solution.description,
                            solution.solution_type.value,
                            json.dumps(solution.steps),
                            json.dumps(solution.code_examples),
                            json.dumps(solution.links),
                            json.dumps(solution.prerequisites),
                            solution.difficulty_level,
                            solution.estimated_time,
                            solution.success_rate,
                            solution.feedback_count,
                            solution.positive_feedback,
                            json.dumps(list(solution.tags)),
                            solution.created_at.isoformat(),
                            solution.updated_at.isoformat(),
                            solution.created_by,
                            solution.language_specific,
                        ),
                    )

        except sqlite3.Error as e:
            logger.error(f"Error saving entry to database: {e}")
            raise

    def _delete_entry_from_db(self, entry_id: str) -> None:
        """Delete entry from database."""
        if self.in_memory:
            return  # No persistent storage for in-memory database

        db_path = str(self.db_path)

        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("DELETE FROM solutions WHERE entry_id = ?", (entry_id,))
                conn.execute("DELETE FROM entries WHERE entry_id = ?", (entry_id,))
        except sqlite3.Error as e:
            logger.error(f"Error deleting entry from database: {e}")
            raise

    def _rebuild_search_index(self) -> None:
        """Rebuild search index for efficient searching."""
        self.search_engine = TroubleshootingSearchEngine(list(self.entries.values()))

    def add_entry(self, entry: TroubleshootingEntry) -> bool:
        """
        Add a new troubleshooting entry.

        Args:
            entry: TroubleshootingEntry to add

        Returns:
            True if added successfully, False if entry already exists
        """
        if entry.entry_id in self.entries:
            logger.warning(f"Entry with ID {entry.entry_id} already exists")
            return False

        try:
            self.entries[entry.entry_id] = entry
            self._save_entry(entry)
            self._rebuild_search_index()
            logger.info(f"Added new troubleshooting entry: {entry.title}")
            return True
        except Exception as e:
            logger.error(f"Error adding entry: {e}")
            # Remove from memory if database save failed
            if entry.entry_id in self.entries:
                del self.entries[entry.entry_id]
            raise

    def update_entry(self, entry: TroubleshootingEntry) -> bool:
        """
        Update an existing troubleshooting entry.

        Args:
            entry: Updated TroubleshootingEntry

        Returns:
            True if updated successfully, False if entry doesn't exist
        """
        if entry.entry_id not in self.entries:
            logger.warning(f"Entry with ID {entry.entry_id} does not exist")
            return False

        try:
            entry.updated_at = datetime.now(UTC)
            self.entries[entry.entry_id] = entry
            self._save_entry(entry)
            self._rebuild_search_index()
            logger.info(f"Updated troubleshooting entry: {entry.title}")
            return True
        except Exception as e:
            logger.error(f"Error updating entry: {e}")
            raise

    def delete_entry(self, entry_id: str) -> bool:
        """
        Delete a troubleshooting entry.

        Args:
            entry_id: ID of entry to delete

        Returns:
            True if deleted successfully, False if entry doesn't exist
        """
        if entry_id not in self.entries:
            logger.warning(f"Entry with ID {entry_id} does not exist")
            return False

        try:
            del self.entries[entry_id]
            self._delete_entry_from_db(entry_id)
            self._rebuild_search_index()
            logger.info(f"Deleted troubleshooting entry: {entry_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting entry: {e}")
            raise

    def get_entry(self, entry_id: str) -> TroubleshootingEntry | None:
        """Get entry by ID."""
        entry = self.entries.get(entry_id)
        if entry:
            entry.record_view()
            self.update_entry(entry)
        return entry

    def search(self, query: str, **kwargs) -> list[tuple[TroubleshootingEntry, float]]:
        """Search for troubleshooting entries."""
        if not self.search_engine:
            self._rebuild_search_index()

        return self.search_engine.search(query, **kwargs)

    def get_entries_by_category(
        self,
        category: TroubleshootingCategory,
    ) -> list[TroubleshootingEntry]:
        """Get all entries in a specific category."""
        return [entry for entry in self.entries.values() if entry.category == category]

    def get_entries_by_language(self, language: str) -> list[TroubleshootingEntry]:
        """Get all entries for a specific language."""
        return [
            entry
            for entry in self.entries.values()
            if language in entry.languages or not entry.languages
        ]

    def get_popular_entries(self, limit: int = 10) -> list[TroubleshootingEntry]:
        """Get most viewed entries."""
        return sorted(
            self.entries.values(),
            key=lambda e: e.view_count + e.resolution_count * 2,
            reverse=True,
        )[:limit]

    def get_recent_entries(self, limit: int = 10) -> list[TroubleshootingEntry]:
        """Get most recently updated entries."""
        return sorted(self.entries.values(), key=lambda e: e.updated_at, reverse=True)[
            :limit
        ]

    def export_database(self, file_path: Path, format: str = "json") -> bool:
        """
        Export database to file.

        Args:
            file_path: Path to export file
            format: Export format ("json" or "pickle")

        Returns:
            True if exported successfully
        """
        try:
            data = {
                "entries": [entry.to_dict() for entry in self.entries.values()],
                "metadata": {
                    "export_time": datetime.now(UTC).isoformat(),
                    "total_entries": len(self.entries),
                    "format_version": "1.0",
                },
            }

            if format.lower() == "json":
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            elif format.lower() == "pickle":
                with open(file_path, "wb") as f:
                    pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
            else:
                raise ValueError(f"Unsupported export format: {format}")

            logger.info(f"Exported database to {file_path} in {format} format")
            return True

        except Exception as e:
            logger.error(f"Error exporting database: {e}")
            return False

    def import_database(
        self,
        file_path: Path,
        format: str = "json",
        merge: bool = True,
    ) -> bool:
        """
        Import database from file.

        Args:
            file_path: Path to import file
            format: Import format ("json" or "pickle")
            merge: If True, merge with existing data; if False, replace

        Returns:
            True if imported successfully
        """
        try:
            if format.lower() == "json":
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
            elif format.lower() == "pickle":
                with open(file_path, "rb") as f:
                    data = pickle.load(f)
            else:
                raise ValueError(f"Unsupported import format: {format}")

            if not merge:
                self.entries.clear()

            imported_count = 0
            for entry_data in data.get("entries", []):
                try:
                    entry = TroubleshootingEntry.from_dict(entry_data)
                    if entry.entry_id not in self.entries:
                        self.entries[entry.entry_id] = entry
                        self._save_entry(entry)
                        imported_count += 1
                    elif merge:
                        # Update if newer
                        existing = self.entries[entry.entry_id]
                        if entry.updated_at > existing.updated_at:
                            self.entries[entry.entry_id] = entry
                            self._save_entry(entry)
                            imported_count += 1
                except Exception as e:
                    logger.warning(f"Error importing entry: {e}")

            self._rebuild_search_index()
            logger.info(f"Imported {imported_count} entries from {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error importing database: {e}")
            return False

    def backup_database(self, backup_path: Path) -> bool:
        """Create a backup of the database."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_path / f"troubleshooting_backup_{timestamp}.json"

        return self.export_database(backup_file, "json")

    def restore_database(self, backup_path: Path) -> bool:
        """Restore database from backup."""
        return self.import_database(backup_path, "json", merge=False)

    def get_statistics(self) -> dict[str, Any]:
        """Get database statistics."""
        if not self.entries:
            return {}

        total_entries = len(self.entries)
        total_solutions = sum(len(entry.solutions) for entry in self.entries.values())
        total_views = sum(entry.view_count for entry in self.entries.values())
        total_resolutions = sum(
            entry.resolution_count for entry in self.entries.values()
        )

        # Category distribution
        category_counts = Counter(entry.category for entry in self.entries.values())

        # Language distribution
        language_counts = Counter()
        for entry in self.entries.values():
            for language in entry.languages:
                language_counts[language] += 1

        # Severity distribution
        severity_counts = Counter(entry.severity for entry in self.entries.values())

        # Average success rates
        solution_success_rates = [
            solution.success_rate
            for entry in self.entries.values()
            for solution in entry.solutions
            if solution.feedback_count > 0
        ]
        avg_success_rate = (
            sum(solution_success_rates) / len(solution_success_rates)
            if solution_success_rates
            else 0
        )

        return {
            "total_entries": total_entries,
            "total_solutions": total_solutions,
            "total_views": total_views,
            "total_resolutions": total_resolutions,
            "resolution_rate": total_resolutions / max(total_views, 1),
            "avg_solutions_per_entry": total_solutions / total_entries,
            "avg_success_rate": avg_success_rate,
            "category_distribution": dict(category_counts),
            "language_distribution": dict(language_counts.most_common(10)),
            "severity_distribution": dict(severity_counts),
            "most_viewed_entry": (
                max(self.entries.values(), key=lambda e: e.view_count).title
                if self.entries
                else None
            ),
            "most_resolved_entry": (
                max(self.entries.values(), key=lambda e: e.resolution_count).title
                if self.entries
                else None
            ),
        }


class TroubleshootingAnalytics:
    """Analytics and insights generation for troubleshooting data."""

    def __init__(self, database: TroubleshootingDatabase):
        """Initialize analytics with database reference."""
        self.database = database

    def analyze_error_patterns(self) -> dict[str, Any]:
        """Analyze common error patterns and trends."""
        patterns = []
        for entry in self.database.entries.values():
            patterns.extend(entry.error_patterns)

        # Count pattern frequency
        pattern_counts = Counter(patterns)

        # Find common keywords in patterns
        all_words = []
        for pattern in patterns:
            all_words.extend(pattern.lower().split())

        word_counts = Counter(all_words)

        # Remove common words
        common_words = {
            "error",
            "failed",
            "cannot",
            "unable",
            "invalid",
            "missing",
            "not",
            "found",
        }
        filtered_words = {
            word: count
            for word, count in word_counts.items()
            if word not in common_words and len(word) > 2
        }

        return {
            "most_common_patterns": pattern_counts.most_common(10),
            "frequent_keywords": Counter(filtered_words).most_common(20),
            "total_unique_patterns": len(pattern_counts),
            "pattern_diversity": len(pattern_counts) / max(len(patterns), 1),
        }

    def analyze_solution_effectiveness(self) -> dict[str, Any]:
        """Analyze solution effectiveness across different categories."""
        solution_data = []

        for entry in self.database.entries.values():
            for solution in entry.solutions:
                if solution.feedback_count > 0:
                    solution_data.append(
                        {
                            "category": entry.category,
                            "solution_type": solution.solution_type,
                            "success_rate": solution.success_rate,
                            "feedback_count": solution.feedback_count,
                            "difficulty": solution.difficulty_level,
                            "effectiveness": solution.calculate_effectiveness_score(),
                        },
                    )

        if not solution_data:
            return {"error": "No solution data available"}

        # Analyze by category
        category_effectiveness = defaultdict(list)
        for data in solution_data:
            category_effectiveness[data["category"]].append(data["effectiveness"])

        category_avg = {
            category.value: sum(scores) / len(scores)
            for category, scores in category_effectiveness.items()
        }

        # Analyze by solution type
        type_effectiveness = defaultdict(list)
        for data in solution_data:
            type_effectiveness[data["solution_type"]].append(data["effectiveness"])

        type_avg = {
            sol_type.value: sum(scores) / len(scores)
            for sol_type, scores in type_effectiveness.items()
        }

        # Difficulty vs effectiveness correlation
        difficulty_effectiveness = defaultdict(list)
        for data in solution_data:
            difficulty_effectiveness[data["difficulty"]].append(data["effectiveness"])

        difficulty_avg = {
            difficulty: sum(scores) / len(scores)
            for difficulty, scores in difficulty_effectiveness.items()
        }

        return {
            "overall_avg_effectiveness": sum(d["effectiveness"] for d in solution_data)
            / len(solution_data),
            "category_effectiveness": category_avg,
            "solution_type_effectiveness": type_avg,
            "difficulty_effectiveness": difficulty_avg,
            "total_solutions_analyzed": len(solution_data),
            "high_effectiveness_threshold": 0.8,
            "solutions_above_threshold": sum(
                1 for d in solution_data if d["effectiveness"] > 0.8
            ),
        }

    def identify_knowledge_gaps(self) -> dict[str, Any]:
        """Identify areas where more troubleshooting content is needed."""
        # Analyze view vs resolution ratios
        low_resolution_entries = []
        for entry in self.database.entries.values():
            if entry.view_count > 10:  # Only consider entries with significant views
                resolution_rate = entry.resolution_count / entry.view_count
                if resolution_rate < 0.3:  # Low resolution rate
                    low_resolution_entries.append(
                        {
                            "entry_id": entry.entry_id,
                            "title": entry.title,
                            "category": entry.category.value,
                            "view_count": entry.view_count,
                            "resolution_count": entry.resolution_count,
                            "resolution_rate": resolution_rate,
                            "solution_count": len(entry.solutions),
                        },
                    )

        # Find categories with few entries
        category_counts = Counter(
            entry.category for entry in self.database.entries.values()
        )
        total_entries = len(self.database.entries)
        underrepresented_categories = {
            category.value: count
            for category, count in category_counts.items()
            if count < total_entries * 0.05  # Less than 5% of total entries
        }

        # Find language gaps
        language_counts = Counter()
        for entry in self.database.entries.values():
            if entry.languages:
                for language in entry.languages:
                    language_counts[language] += 1
            else:
                language_counts["general"] += 1

        # Common programming languages that might be missing
        expected_languages = {
            "python",
            "javascript",
            "java",
            "go",
            "rust",
            "cpp",
            "c",
            "csharp",
            "ruby",
            "php",
        }
        missing_languages = expected_languages - set(language_counts.keys())

        return {
            "low_resolution_entries": sorted(
                low_resolution_entries,
                key=lambda x: x["view_count"],
                reverse=True,
            )[:10],
            "underrepresented_categories": underrepresented_categories,
            "missing_languages": list(missing_languages),
            "language_coverage": dict(language_counts.most_common()),
            "recommendations": self._generate_gap_recommendations(
                low_resolution_entries,
                underrepresented_categories,
                missing_languages,
            ),
        }

    def _generate_gap_recommendations(
        self,
        low_resolution: list[dict],
        underrepresented: dict,
        missing_languages: list[str],
    ) -> list[str]:
        """Generate recommendations for filling knowledge gaps."""
        recommendations = []

        if low_resolution:
            recommendations.append(
                f"Improve solutions for {len(low_resolution)} high-traffic, low-resolution entries",
            )

        if underrepresented:
            categories = list(underrepresented.keys())[:3]
            recommendations.append(
                f"Add more content for underrepresented categories: {', '.join(categories)}",
            )

        if missing_languages:
            languages = list(missing_languages)[:5]
            recommendations.append(
                f"Create language-specific content for: {', '.join(languages)}",
            )

        return recommendations

    def generate_trending_report(self, days: int = 7) -> dict[str, Any]:
        """Generate a report of trending issues and solutions."""
        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        recent_entries = [
            entry
            for entry in self.database.entries.values()
            if entry.updated_at >= cutoff_date
        ]

        if not recent_entries:
            return {"message": f"No activity in the last {days} days"}

        # Most viewed recent entries
        trending_entries = sorted(
            recent_entries,
            key=lambda e: e.view_count,
            reverse=True,
        )[:10]

        # Most resolved recent entries
        most_resolved = sorted(
            recent_entries,
            key=lambda e: e.resolution_count,
            reverse=True,
        )[:5]

        # New categories trending
        category_activity = Counter(entry.category for entry in recent_entries)

        # Solution types being used
        solution_types = []
        for entry in recent_entries:
            for solution in entry.solutions:
                solution_types.append(solution.solution_type)

        solution_type_counts = Counter(solution_types)

        return {
            "period_days": days,
            "total_recent_activity": len(recent_entries),
            "trending_entries": [
                {
                    "title": entry.title,
                    "category": entry.category.value,
                    "view_count": entry.view_count,
                    "resolution_count": entry.resolution_count,
                }
                for entry in trending_entries
            ],
            "most_resolved_recent": [
                {
                    "title": entry.title,
                    "resolution_count": entry.resolution_count,
                    "view_count": entry.view_count,
                }
                for entry in most_resolved
            ],
            "active_categories": dict(category_activity.most_common()),
            "popular_solution_types": dict(solution_type_counts.most_common()),
        }

    def calculate_database_health_score(self) -> dict[str, Any]:
        """Calculate overall health score of the troubleshooting database."""
        total_entries = len(self.database.entries)
        if total_entries == 0:
            return {"health_score": 0, "status": "empty"}

        # Coverage score (0-25 points)
        category_coverage = len(
            set(entry.category for entry in self.database.entries.values()),
        )
        max_categories = len(TroubleshootingCategory)
        coverage_score = (category_coverage / max_categories) * 25

        # Solution quality score (0-25 points)
        solutions_with_feedback = [
            solution
            for entry in self.database.entries.values()
            for solution in entry.solutions
            if solution.feedback_count > 0
        ]

        if solutions_with_feedback:
            avg_success_rate = sum(
                s.success_rate for s in solutions_with_feedback
            ) / len(solutions_with_feedback)
            quality_score = avg_success_rate * 25
        else:
            quality_score = 0

        # Activity score (0-25 points)
        total_views = sum(entry.view_count for entry in self.database.entries.values())
        total_resolutions = sum(
            entry.resolution_count for entry in self.database.entries.values()
        )

        if total_views > 0:
            resolution_rate = total_resolutions / total_views
            activity_score = min(25, resolution_rate * 50)  # Cap at 25
        else:
            activity_score = 0

        # Content richness score (0-25 points)
        avg_solutions_per_entry = (
            sum(len(entry.solutions) for entry in self.database.entries.values())
            / total_entries
        )
        avg_patterns_per_entry = (
            sum(len(entry.error_patterns) for entry in self.database.entries.values())
            / total_entries
        )

        richness_score = min(
            25,
            (avg_solutions_per_entry * 5) + (avg_patterns_per_entry * 2),
        )

        total_score = coverage_score + quality_score + activity_score + richness_score

        # Determine status
        if total_score >= 80:
            status = "excellent"
        elif total_score >= 60:
            status = "good"
        elif total_score >= 40:
            status = "fair"
        elif total_score >= 20:
            status = "poor"
        else:
            status = "critical"

        return {
            "health_score": round(total_score, 2),
            "status": status,
            "component_scores": {
                "coverage": round(coverage_score, 2),
                "quality": round(quality_score, 2),
                "activity": round(activity_score, 2),
                "richness": round(richness_score, 2),
            },
            "metrics": {
                "total_entries": total_entries,
                "category_coverage": f"{category_coverage}/{max_categories}",
                "avg_solutions_per_entry": round(avg_solutions_per_entry, 2),
                "total_views": total_views,
                "total_resolutions": total_resolutions,
                "resolution_rate": round(total_resolutions / max(total_views, 1), 3),
            },
        }


def create_sample_troubleshooting_data() -> list[TroubleshootingEntry]:
    """Create sample troubleshooting data for testing and initial population."""
    entries = []

    # Python syntax errors
    python_syntax = TroubleshootingEntry(
        title="Python SyntaxError: invalid syntax",
        description="Common Python syntax errors that prevent code parsing",
        category=TroubleshootingCategory.SYNTAX_ERROR,
        error_patterns=[
            "SyntaxError: invalid syntax",
            "SyntaxError: unexpected EOF while parsing",
            "IndentationError: expected an indented block",
        ],
        symptoms=[
            "Code fails to parse",
            "Unexpected syntax error messages",
            "Indentation-related errors",
        ],
        causes=[
            "Missing colons after if/for/while statements",
            "Incorrect indentation",
            "Unmatched parentheses or brackets",
            "Python 2/3 syntax differences",
        ],
        languages={"python"},
        severity=3,
        keywords={"python", "syntax", "error", "indentation", "parsing"},
    )

    # Add solutions for Python syntax
    python_syntax.add_solution(
        Solution(
            title="Check for missing colons",
            description="Ensure all control structures end with colons",
            solution_type=SolutionType.QUICK_FIX,
            steps=[
                "Look for if, for, while, def, class statements",
                "Ensure each ends with a colon (:)",
                "Check for proper indentation after the colon",
            ],
            code_examples=[
                "# Correct:\nif condition:\n    do_something()",
                "# Incorrect:\nif condition\n    do_something()",
            ],
            difficulty_level=1,
            estimated_time="2 minutes",
        ),
    )

    python_syntax.add_solution(
        Solution(
            title="Fix indentation errors",
            description="Standardize indentation using 4 spaces",
            solution_type=SolutionType.DETAILED_GUIDE,
            steps=[
                "Configure editor to show whitespace",
                "Replace tabs with 4 spaces",
                "Ensure consistent indentation levels",
                "Use a Python linter like pylint or flake8",
            ],
            difficulty_level=2,
            estimated_time="10 minutes",
        ),
    )

    entries.append(python_syntax)

    # JavaScript version compatibility
    js_compat = TroubleshootingEntry(
        title="JavaScript ES6+ features not recognized",
        description="Modern JavaScript features cause parsing errors",
        category=TroubleshootingCategory.COMPATIBILITY_ERROR,
        error_patterns=[
            "Unexpected token =>",
            "Unexpected token ...",
            "const is not defined",
        ],
        symptoms=[
            "Arrow functions not parsed",
            "Spread operator errors",
            "Template literals not recognized",
        ],
        causes=[
            "Using ES5 parser for ES6+ code",
            "Incorrect JavaScript grammar version",
            "Missing babel configuration",
        ],
        languages={"javascript", "typescript"},
        severity=4,
        keywords={"javascript", "es6", "compatibility", "parser", "modern"},
    )

    js_compat.add_solution(
        Solution(
            title="Update to ES6+ compatible parser",
            description="Configure parser to support modern JavaScript",
            solution_type=SolutionType.CONFIGURATION_CHANGE,
            steps=[
                "Check current JavaScript grammar version",
                "Update to tree-sitter-javascript with ES6+ support",
                "Verify ecmaVersion in parser configuration",
                "Test with modern JavaScript features",
            ],
            difficulty_level=3,
            estimated_time="15 minutes",
        ),
    )

    entries.append(js_compat)

    # Grammar installation error
    grammar_install = TroubleshootingEntry(
        title="Failed to compile grammar: missing build tools",
        description="Grammar compilation fails due to missing system dependencies",
        category=TroubleshootingCategory.INSTALLATION_ERROR,
        error_patterns=[
            "error: Microsoft Visual C++ 14.0 is required",
            "gcc: command not found",
            "make: command not found",
        ],
        symptoms=[
            "Grammar compilation fails",
            "Missing compiler errors",
            "Build system not found",
        ],
        causes=[
            "Missing C/C++ compiler",
            "Missing build tools",
            "Incorrect Python environment",
        ],
        languages=set(),  # General issue
        severity=4,
        keywords={"grammar", "installation", "compiler", "build", "tools"},
    )

    grammar_install.add_solution(
        Solution(
            title="Install Visual Studio Build Tools (Windows)",
            description="Install Microsoft C++ Build Tools for Windows",
            solution_type=SolutionType.SYSTEM_REQUIREMENT,
            steps=[
                "Download Visual Studio Build Tools installer",
                "Select 'C++ build tools' workload",
                "Include Windows 10 SDK",
                "Restart command prompt after installation",
            ],
            links=["https://visualstudio.microsoft.com/visual-cpp-build-tools/"],
            difficulty_level=3,
            estimated_time="30 minutes",
        ),
    )

    grammar_install.add_solution(
        Solution(
            title="Install build-essential (Linux)",
            description="Install essential build tools on Linux systems",
            solution_type=SolutionType.SYSTEM_REQUIREMENT,
            steps=[
                "sudo apt update",
                "sudo apt install build-essential",
                "sudo apt install python3-dev",
                "Verify: gcc --version",
            ],
            code_examples=[
                "sudo apt update && sudo apt install build-essential python3-dev",
            ],
            difficulty_level=2,
            estimated_time="10 minutes",
        ),
    )

    entries.append(grammar_install)

    return entries


def initialize_troubleshooting_system(
    db_path: Path | None = None,
) -> TroubleshootingDatabase:
    """
    Initialize a complete troubleshooting system with sample data.

    Args:
        db_path: Optional path for database file

    Returns:
        Configured TroubleshootingDatabase instance
    """
    # Create database
    database = TroubleshootingDatabase(db_path)

    # Add sample data if database is empty
    if len(database.entries) == 0:
        sample_entries = create_sample_troubleshooting_data()
        for entry in sample_entries:
            database.add_entry(entry)

        logger.info(
            f"Initialized troubleshooting system with {len(sample_entries)} sample entries",
        )
    else:
        logger.info(
            f"Loaded existing troubleshooting system with {len(database.entries)} entries",
        )

    return database


# Example usage and testing functions
if __name__ == "__main__":
    # Initialize system
    db = initialize_troubleshooting_system()

    # Example search
    results = db.search("python syntax error")
    print(f"Found {len(results)} results for 'python syntax error'")

    # Analytics example
    analytics = TroubleshootingAnalytics(db)
    health = analytics.calculate_database_health_score()
    print(f"Database health score: {health['health_score']}/100 ({health['status']})")

    # Get statistics
    stats = db.get_statistics()
    print(f"Total entries: {stats['total_entries']}")
    print(f"Total solutions: {stats['total_solutions']}")
