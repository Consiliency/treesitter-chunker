"""Compatibility database for Phase 1.7."""

import json
import logging
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .grammar_analyzer import GrammarAnalyzer
from .schema import (
    BreakingChange,
    CompatibilityLevel,
    CompatibilityRule,
    CompatibilitySchema,
    GrammarVersion,
    LanguageVersion,
)

logger = logging.getLogger(__name__)


class CompatibilityDatabase:
    """Main database class for managing compatibility information.

    Supports context manager protocol for safe resource management.

    Example:
        with CompatibilityDatabase(path) as db:
            db.query(...)

    Can also be used directly (backward compatible):
        db = CompatibilityDatabase(path)
        db.query(...)
        del db  # connection closed in __del__
    """

    def __init__(self, db_path: Path | None = None):
        """Initialize the compatibility database.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path) if db_path else Path("compatibility.db")
        self.schema = CompatibilitySchema()
        self.grammar_analyzer = None
        self._conn: sqlite3.Connection | None = None
        self._in_context_manager = False
        self._init_database()
        logger.debug(f"Initialized CompatibilityDatabase at {self.db_path}")

    def __enter__(self) -> "CompatibilityDatabase":
        """Enter context manager, ensure connection is open."""
        self._in_context_manager = True
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager, close connection."""
        self._in_context_manager = False
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Get active connection.

        Returns:
            sqlite3.Connection: The active database connection.

        Raises:
            RuntimeError: If connection is not available.
        """
        if self._conn is None:
            raise RuntimeError(
                "Database connection not available. "
                "Use context manager: with CompatibilityDatabase(path) as db: ...",
            )
        return self._conn

    @conn.setter
    def conn(self, value: sqlite3.Connection | None) -> None:
        """Set the connection (for backward compatibility)."""
        self._conn = value

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Cursor]:
        """Create a transaction with automatic commit/rollback.

        Yields:
            sqlite3.Cursor: Cursor for executing queries.

        Example:
            with db.transaction() as cursor:
                cursor.execute("INSERT INTO ...")
        """
        cursor = self.conn.cursor()
        try:
            yield cursor
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    def _init_database(self) -> None:
        """Initialize the database and create tables."""
        try:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._create_tables()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def _create_tables(self) -> None:
        """Create all necessary database tables."""
        try:
            cursor = self.conn.cursor()

            # Language versions table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS language_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    language TEXT NOT NULL,
                    version TEXT NOT NULL,
                    edition TEXT,
                    build TEXT,
                    features TEXT,
                    release_date TEXT,
                    end_of_life TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(language, version)
                )
            """,
            )

            # Grammar versions table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS grammar_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    language TEXT NOT NULL,
                    version TEXT NOT NULL,
                    grammar_file TEXT NOT NULL,
                    supported_features TEXT,
                    min_language_version TEXT,
                    max_language_version TEXT,
                    breaking_changes TEXT,
                    release_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(language, version)
                )
            """,
            )

            # Compatibility rules table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS compatibility_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    language TEXT NOT NULL,
                    language_version_constraint TEXT NOT NULL,
                    grammar_version_constraint TEXT NOT NULL,
                    compatibility_level TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """,
            )

            # Breaking changes table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS breaking_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    language TEXT NOT NULL,
                    from_version TEXT NOT NULL,
                    to_version TEXT NOT NULL,
                    change_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    impact_level TEXT NOT NULL,
                    migration_guide TEXT,
                    affected_features TEXT,
                    detected_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """,
            )

            # Create indexes for better performance
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_lang_versions ON language_versions(language)",
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_grammar_versions ON grammar_versions(language)",
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_compat_rules ON compatibility_rules(language)",
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_breaking_changes ON breaking_changes(language)",
            )

            self.conn.commit()
            logger.debug("Database tables created successfully")

        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            self.conn.rollback()
            raise

    def add_language_version(self, lang_version: LanguageVersion) -> bool:
        """Add a language version to the database.

        Args:
            lang_version: LanguageVersion object to add

        Returns:
            True if successful, False otherwise
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO language_versions 
                (language, version, edition, build, features, release_date, end_of_life)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    lang_version.language,
                    lang_version.version,
                    lang_version.edition,
                    lang_version.build,
                    json.dumps(lang_version.features),
                    (
                        lang_version.release_date.isoformat()
                        if lang_version.release_date
                        else None
                    ),
                    (
                        lang_version.end_of_life.isoformat()
                        if lang_version.end_of_life
                        else None
                    ),
                ),
            )

            self.conn.commit()
            self.schema.add_language_version(lang_version)
            logger.debug(f"Added language version: {lang_version}")
            return True

        except Exception as e:
            logger.error(f"Error adding language version: {e}")
            self.conn.rollback()
            return False

    def add_grammar_version(self, grammar_version: GrammarVersion) -> bool:
        """Add a grammar version to the database.

        Args:
            grammar_version: GrammarVersion object to add

        Returns:
            True if successful, False otherwise
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO grammar_versions 
                (language, version, grammar_file, supported_features, 
                 min_language_version, max_language_version, breaking_changes, release_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    grammar_version.language,
                    grammar_version.version,
                    grammar_version.grammar_file,
                    json.dumps(grammar_version.supported_features),
                    grammar_version.min_language_version,
                    grammar_version.max_language_version,
                    json.dumps(grammar_version.breaking_changes),
                    (
                        grammar_version.release_date.isoformat()
                        if grammar_version.release_date
                        else None
                    ),
                ),
            )

            self.conn.commit()
            self.schema.add_grammar_version(grammar_version)
            logger.debug(f"Added grammar version: {grammar_version}")
            return True

        except Exception as e:
            logger.error(f"Error adding grammar version: {e}")
            self.conn.rollback()
            return False

    def add_compatibility_rule(self, rule: CompatibilityRule) -> bool:
        """Add a compatibility rule to the database.

        Args:
            rule: CompatibilityRule object to add

        Returns:
            True if successful, False otherwise
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute(
                """
                INSERT INTO compatibility_rules 
                (language, language_version_constraint, grammar_version_constraint, 
                 compatibility_level, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    rule.language,
                    rule.language_version_constraint,
                    rule.grammar_version_constraint,
                    rule.compatibility_level.value,
                    rule.notes,
                    rule.created_at.isoformat(),
                ),
            )

            self.conn.commit()
            self.schema.add_compatibility_rule(rule)
            logger.debug(f"Added compatibility rule: {rule}")
            return True

        except Exception as e:
            logger.error(f"Error adding compatibility rule: {e}")
            self.conn.rollback()
            return False

    def add_breaking_change(self, breaking_change: BreakingChange) -> bool:
        """Add a breaking change to the database.

        Args:
            breaking_change: BreakingChange object to add

        Returns:
            True if successful, False otherwise
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute(
                """
                INSERT INTO breaking_changes 
                (language, from_version, to_version, change_type, description, 
                 impact_level, migration_guide, affected_features, detected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    breaking_change.language,
                    breaking_change.from_version,
                    breaking_change.to_version,
                    breaking_change.change_type,
                    breaking_change.description,
                    breaking_change.impact_level,
                    breaking_change.migration_guide,
                    json.dumps(breaking_change.affected_features),
                    breaking_change.detected_at.isoformat(),
                ),
            )

            self.conn.commit()
            self.schema.add_breaking_change(breaking_change)
            logger.debug(f"Added breaking change: {breaking_change}")
            return True

        except Exception as e:
            logger.error(f"Error adding breaking change: {e}")
            self.conn.rollback()
            return False

    def get_language_versions(self, language: str) -> list[LanguageVersion]:
        """Get all versions for a specific language.

        Args:
            language: The language name

        Returns:
            List of LanguageVersion objects
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT * FROM language_versions WHERE language = ? ORDER BY version
            """,
                (language.lower(),),
            )

            versions = []
            for row in cursor.fetchall():
                lang_version = LanguageVersion(
                    language=row["language"],
                    version=row["version"],
                    edition=row["edition"],
                    build=row["build"],
                    features=json.loads(row["features"]) if row["features"] else [],
                    release_date=(
                        datetime.fromisoformat(row["release_date"])
                        if row["release_date"]
                        else None
                    ),
                    end_of_life=(
                        datetime.fromisoformat(row["end_of_life"])
                        if row["end_of_life"]
                        else None
                    ),
                )
                versions.append(lang_version)

            return versions

        except Exception as e:
            logger.error(f"Error getting language versions: {e}")
            return []

    def get_grammar_versions(self, language: str) -> list[GrammarVersion]:
        """Get all grammar versions for a specific language.

        Args:
            language: The language name

        Returns:
            List of GrammarVersion objects
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT * FROM grammar_versions WHERE language = ? ORDER BY version
            """,
                (language.lower(),),
            )

            versions = []
            for row in cursor.fetchall():
                grammar_version = GrammarVersion(
                    language=row["language"],
                    version=row["version"],
                    grammar_file=row["grammar_file"],
                    supported_features=(
                        json.loads(row["supported_features"])
                        if row["supported_features"]
                        else []
                    ),
                    min_language_version=row["min_language_version"],
                    max_language_version=row["max_language_version"],
                    breaking_changes=(
                        json.loads(row["breaking_changes"])
                        if row["breaking_changes"]
                        else []
                    ),
                    release_date=(
                        datetime.fromisoformat(row["release_date"])
                        if row["release_date"]
                        else None
                    ),
                )
                versions.append(grammar_version)

            return versions

        except Exception as e:
            logger.error(f"Error getting grammar versions: {e}")
            return []

    def find_compatible_grammar(
        self,
        lang_version: LanguageVersion,
    ) -> GrammarVersion | None:
        """Find a compatible grammar for a language version.

        Args:
            lang_version: LanguageVersion to find grammar for

        Returns:
            Compatible GrammarVersion or None
        """
        return self.schema.find_compatible_grammar(lang_version)

    def get_compatibility_level(
        self,
        lang_version: LanguageVersion,
        grammar_version: GrammarVersion,
    ) -> CompatibilityLevel:
        """Get compatibility level between language and grammar versions.

        Args:
            lang_version: LanguageVersion object
            grammar_version: GrammarVersion object

        Returns:
            CompatibilityLevel enum value
        """
        return self.schema.get_compatibility_level(lang_version, grammar_version)

    def get_breaking_changes(
        self,
        language: str,
        from_version: str,
        to_version: str,
    ) -> list[BreakingChange]:
        """Get breaking changes between two versions.

        Args:
            language: The language name
            from_version: Starting version
            to_version: Ending version

        Returns:
            List of BreakingChange objects
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT * FROM breaking_changes 
                WHERE language = ? 
                ORDER BY from_version, to_version
            """,
                (language.lower(),),
            )

            changes = []
            for row in cursor.fetchall():
                # Check if change is in range
                change_from = row["from_version"]
                change_to = row["to_version"]

                # Simple check - could be improved
                if (change_from >= from_version and change_from <= to_version) or (
                    change_to >= from_version and change_to <= to_version
                ):
                    breaking_change = BreakingChange(
                        language=row["language"],
                        from_version=row["from_version"],
                        to_version=row["to_version"],
                        change_type=row["change_type"],
                        description=row["description"],
                        impact_level=row["impact_level"],
                        migration_guide=row["migration_guide"],
                        affected_features=(
                            json.loads(row["affected_features"])
                            if row["affected_features"]
                            else []
                        ),
                        detected_at=(
                            datetime.fromisoformat(row["detected_at"])
                            if row["detected_at"]
                            else datetime.now()
                        ),
                    )
                    changes.append(breaking_change)

            return changes

        except Exception as e:
            logger.error(f"Error getting breaking changes: {e}")
            return []

    def update_compatibility_data(self) -> None:
        """Update compatibility data from grammar analysis."""
        try:
            if not self.grammar_analyzer:
                grammars_dir = Path("chunker/data/grammars/build")
                self.grammar_analyzer = GrammarAnalyzer(grammars_dir)

            # Analyze all grammars
            all_grammars = self.grammar_analyzer.analyze_all_grammars()

            # Add grammar versions to database
            for language, grammar_version in all_grammars.items():
                self.add_grammar_version(grammar_version)

            logger.info(f"Updated compatibility data for {len(all_grammars)} languages")

        except Exception as e:
            logger.error(f"Error updating compatibility data: {e}")

    def export_database(self, output_path: Path) -> None:
        """Export database to JSON or other format.

        Args:
            output_path: Path to write the export file
        """
        try:
            output_path = Path(output_path)

            # Get all data from database
            cursor = self.conn.cursor()

            export_data = {
                "metadata": {
                    "exported_at": datetime.now().isoformat(),
                    "database_path": str(self.db_path),
                },
                "language_versions": [],
                "grammar_versions": [],
                "compatibility_rules": [],
                "breaking_changes": [],
            }

            # Export language versions
            cursor.execute("SELECT * FROM language_versions")
            for row in cursor.fetchall():
                export_data["language_versions"].append(dict(row))

            # Export grammar versions
            cursor.execute("SELECT * FROM grammar_versions")
            for row in cursor.fetchall():
                export_data["grammar_versions"].append(dict(row))

            # Export compatibility rules
            cursor.execute("SELECT * FROM compatibility_rules")
            for row in cursor.fetchall():
                export_data["compatibility_rules"].append(dict(row))

            # Export breaking changes
            cursor.execute("SELECT * FROM breaking_changes")
            for row in cursor.fetchall():
                export_data["breaking_changes"].append(dict(row))

            # Write to file
            with open(output_path, "w") as f:
                json.dump(export_data, f, indent=2, default=str)

            logger.info(f"Exported database to {output_path}")

        except Exception as e:
            logger.error(f"Error exporting database: {e}")
            raise

    def import_database(self, input_path: Path) -> None:
        """Import database from JSON or other format.

        Args:
            input_path: Path to the import file
        """
        try:
            input_path = Path(input_path)

            with open(input_path) as f:
                import_data = json.load(f)

            # Clear existing data
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM language_versions")
            cursor.execute("DELETE FROM grammar_versions")
            cursor.execute("DELETE FROM compatibility_rules")
            cursor.execute("DELETE FROM breaking_changes")

            # Import language versions
            for data in import_data.get("language_versions", []):
                cursor.execute(
                    """
                    INSERT INTO language_versions 
                    (language, version, edition, build, features, release_date, end_of_life)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        data["language"],
                        data["version"],
                        data.get("edition"),
                        data.get("build"),
                        data.get("features"),
                        data.get("release_date"),
                        data.get("end_of_life"),
                    ),
                )

            # Import grammar versions
            for data in import_data.get("grammar_versions", []):
                cursor.execute(
                    """
                    INSERT INTO grammar_versions 
                    (language, version, grammar_file, supported_features, 
                     min_language_version, max_language_version, breaking_changes, release_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        data["language"],
                        data["version"],
                        data["grammar_file"],
                        data.get("supported_features"),
                        data.get("min_language_version"),
                        data.get("max_language_version"),
                        data.get("breaking_changes"),
                        data.get("release_date"),
                    ),
                )

            # Import compatibility rules
            for data in import_data.get("compatibility_rules", []):
                cursor.execute(
                    """
                    INSERT INTO compatibility_rules 
                    (language, language_version_constraint, grammar_version_constraint, 
                     compatibility_level, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        data["language"],
                        data["language_version_constraint"],
                        data["grammar_version_constraint"],
                        data["compatibility_level"],
                        data.get("notes"),
                        data.get("created_at"),
                    ),
                )

            # Import breaking changes
            for data in import_data.get("breaking_changes", []):
                cursor.execute(
                    """
                    INSERT INTO breaking_changes 
                    (language, from_version, to_version, change_type, description, 
                     impact_level, migration_guide, affected_features, detected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        data["language"],
                        data["from_version"],
                        data["to_version"],
                        data["change_type"],
                        data["description"],
                        data["impact_level"],
                        data.get("migration_guide"),
                        data.get("affected_features"),
                        data.get("detected_at"),
                    ),
                )

            self.conn.commit()
            logger.info(f"Imported database from {input_path}")

        except Exception as e:
            logger.error(f"Error importing database: {e}")
            self.conn.rollback()
            raise

    def validate_database(self) -> list[str]:
        """Validate database integrity and return any errors.

        Returns:
            List of validation errors
        """
        errors = []

        try:
            cursor = self.conn.cursor()

            # Check for orphaned references
            cursor.execute(
                """
                SELECT DISTINCT language FROM compatibility_rules
                WHERE language NOT IN (SELECT DISTINCT language FROM language_versions)
            """,
            )
            orphaned = cursor.fetchall()
            for row in orphaned:
                errors.append(
                    f"Compatibility rule references unknown language: {row['language']}",
                )

            # Check for duplicate entries
            cursor.execute(
                """
                SELECT language, version, COUNT(*) as count 
                FROM language_versions 
                GROUP BY language, version 
                HAVING count > 1
            """,
            )
            duplicates = cursor.fetchall()
            for row in duplicates:
                errors.append(
                    f"Duplicate language version: {row['language']} {row['version']}",
                )

            # Validate schema
            schema_errors = self.schema.validate_schema()
            errors.extend(schema_errors)

            if errors:
                logger.warning(f"Database validation found {len(errors)} errors")
            else:
                logger.info("Database validation passed")

        except Exception as e:
            logger.error(f"Error validating database: {e}")
            errors.append(f"Validation error: {e}")

        return errors

    def optimize_database(self) -> None:
        """Optimize database performance."""
        try:
            cursor = self.conn.cursor()

            # Analyze tables for query optimization
            cursor.execute("ANALYZE")

            # Vacuum to reclaim space
            cursor.execute("VACUUM")

            # Reindex
            cursor.execute("REINDEX")

            self.conn.commit()
            logger.info("Database optimized successfully")

        except Exception as e:
            logger.error(f"Error optimizing database: {e}")

    def backup_database(self, backup_path: Path) -> None:
        """Create a backup of the database.

        Args:
            backup_path: Path to save the backup
        """
        try:
            backup_path = Path(backup_path)

            # Close current connection
            if self._conn:
                self._conn.close()

            # Copy database file
            shutil.copy2(self.db_path, backup_path)

            # Reopen connection
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row

            logger.info(f"Database backed up to {backup_path}")

        except Exception as e:
            logger.error(f"Error backing up database: {e}")
            raise

    def restore_database(self, backup_path: Path) -> None:
        """Restore database from backup.

        Args:
            backup_path: Path to the backup file
        """
        try:
            backup_path = Path(backup_path)

            if not backup_path.exists():
                raise FileNotFoundError(f"Backup file not found: {backup_path}")

            # Close current connection
            if self._conn:
                self._conn.close()

            # Copy backup to database location
            shutil.copy2(backup_path, self.db_path)

            # Reopen connection
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row

            # Reinitialize schema
            self.schema = CompatibilitySchema()

            logger.info(f"Database restored from {backup_path}")

        except Exception as e:
            logger.error(f"Error restoring database: {e}")
            raise

    def close(self) -> None:
        """Close database connection and release resources."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __del__(self):
        """Clean up database connection."""
        self.close()


class DatabaseManager:
    """High-level database management operations."""

    def __init__(self, db_path: Path):
        """Initialize the database manager.

        Args:
            db_path: Path to the database file
        """
        self.database = CompatibilityDatabase(db_path)
        self.grammar_analyzer = GrammarAnalyzer(Path("chunker/data/grammars/build"))
        logger.debug("Initialized DatabaseManager")

    def populate_from_grammars(self) -> None:
        """Populate database with data from grammar analysis."""
        try:
            # Analyze all grammars
            all_grammars = self.grammar_analyzer.analyze_all_grammars()

            # Add to database
            for language, grammar_version in all_grammars.items():
                self.database.add_grammar_version(grammar_version)

            logger.info(f"Populated database with {len(all_grammars)} grammars")

        except Exception as e:
            logger.error(f"Error populating from grammars: {e}")

    def add_known_compatibility_data(self) -> None:
        """Add known compatibility data for common language versions."""
        try:
            # Python versions
            python_versions = [
                ("3.6", None, None, ["f-strings", "async"]),
                ("3.7", None, None, ["dataclasses", "annotations"]),
                ("3.8", None, None, ["walrus", "positional-only"]),
                ("3.9", None, None, ["dict-merge", "type-hints"]),
                ("3.10", None, None, ["match", "union-types"]),
                ("3.11", None, None, ["exception-groups", "task-groups"]),
                ("3.12", None, None, ["type-params", "buffer-protocol"]),
            ]

            for version, edition, build, features in python_versions:
                lang_version = LanguageVersion(
                    language="python",
                    version=version,
                    edition=edition,
                    build=build,
                    features=features,
                )
                self.database.add_language_version(lang_version)

            # JavaScript versions
            js_versions = [
                ("ES2015", None, None, ["arrow-functions", "classes", "let-const"]),
                ("ES2016", None, None, ["exponentiation", "array-includes"]),
                ("ES2017", None, None, ["async-await", "object-entries"]),
                ("ES2018", None, None, ["rest-spread", "async-iteration"]),
                ("ES2019", None, None, ["flat-map", "trimming"]),
                ("ES2020", None, None, ["bigint", "nullish-coalescing"]),
                ("ES2021", None, None, ["logical-assignment", "numeric-separators"]),
                ("ES2022", None, None, ["class-fields", "top-level-await"]),
                ("ES2023", None, None, ["array-find-last", "hashbang"]),
            ]

            for version, edition, build, features in js_versions:
                lang_version = LanguageVersion(
                    language="javascript",
                    version=version,
                    edition=edition,
                    build=build,
                    features=features,
                )
                self.database.add_language_version(lang_version)

            # Add compatibility rules
            rule = CompatibilityRule(
                language="python",
                language_version_constraint=">=3.6",
                grammar_version_constraint="*",
                compatibility_level=CompatibilityLevel.FULLY_COMPATIBLE,
                notes="Modern Python versions are fully supported",
            )
            self.database.add_compatibility_rule(rule)

            logger.info("Added known compatibility data")

        except Exception as e:
            logger.error(f"Error adding known compatibility data: {e}")

    def update_breaking_changes(self) -> None:
        """Update breaking changes information."""
        try:
            # Python 2 to 3
            change = BreakingChange(
                language="python",
                from_version="2.7",
                to_version="3.0",
                change_type="syntax",
                description="Print becomes a function, integer division changes",
                impact_level="critical",
                migration_guide="Use 2to3 tool for automatic conversion",
                affected_features=["print", "division", "unicode"],
            )
            self.database.add_breaking_change(change)

            # JavaScript ES5 to ES6
            change = BreakingChange(
                language="javascript",
                from_version="ES5",
                to_version="ES2015",
                change_type="feature",
                description="New syntax features: let/const, arrow functions, classes",
                impact_level="medium",
                migration_guide="Use Babel for backward compatibility",
                affected_features=["variables", "functions", "classes"],
            )
            self.database.add_breaking_change(change)

            logger.info("Updated breaking changes information")

        except Exception as e:
            logger.error(f"Error updating breaking changes: {e}")

    def generate_compatibility_report(self, language: str) -> str:
        """Generate comprehensive compatibility report for a language.

        Args:
            language: The language name

        Returns:
            Formatted report string
        """
        try:
            report = []
            report.append(f"Compatibility Report: {language}")
            report.append("=" * 60)

            # Language versions
            lang_versions = self.database.get_language_versions(language)
            report.append(f"\nLanguage Versions ({len(lang_versions)}):")
            for version in lang_versions:
                report.append(f"  - {version}")

            # Grammar versions
            grammar_versions = self.database.get_grammar_versions(language)
            report.append(f"\nGrammar Versions ({len(grammar_versions)}):")
            for version in grammar_versions:
                report.append(f"  - {version}")

            # Breaking changes
            if lang_versions:
                first_version = lang_versions[0].version
                last_version = lang_versions[-1].version
                changes = self.database.get_breaking_changes(
                    language,
                    first_version,
                    last_version,
                )
                if changes:
                    report.append(f"\nBreaking Changes ({len(changes)}):")
                    for change in changes:
                        report.append(
                            f"  - {change.from_version} -> {change.to_version}: "
                            f"{change.description}",
                        )

            # Validation
            errors = self.database.validate_database()
            if errors:
                report.append(f"\nValidation Issues ({len(errors)}):")
                for error in errors[:5]:  # Show first 5 errors
                    report.append(f"  - {error}")
            else:
                report.append("\nValidation: ✓ No issues found")

            return "\n".join(report)

        except Exception as e:
            logger.error(f"Error generating report for {language}: {e}")
            return f"Error generating report: {e}"

    def get_language_support_matrix(self) -> dict[str, dict[str, Any]]:
        """Get support matrix for all languages.

        Returns:
            Dict with language support information
        """
        matrix = {}

        try:
            # Get all grammars
            all_grammars = self.grammar_analyzer.analyze_all_grammars()

            for language, grammar_version in all_grammars.items():
                lang_versions = self.database.get_language_versions(language)

                matrix[language] = {
                    "grammar_version": grammar_version.version,
                    "language_versions": [v.version for v in lang_versions],
                    "min_supported": grammar_version.min_language_version,
                    "max_supported": grammar_version.max_language_version,
                    "features": grammar_version.supported_features,
                    "fully_compatible": len(lang_versions) > 0,
                }

            logger.debug(f"Generated support matrix for {len(matrix)} languages")

        except Exception as e:
            logger.error(f"Error generating support matrix: {e}")

        return matrix
