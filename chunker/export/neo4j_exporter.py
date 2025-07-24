"""Neo4j export implementation for code chunks."""

import csv
from io import StringIO
from pathlib import Path
from typing import Any

from ..types import CodeChunk
from .graph_exporter_base import GraphExporterBase


class Neo4jExporter(GraphExporterBase):
    """Export code chunks for Neo4j graph database import."""

    def __init__(self):
        super().__init__()
        self.node_labels: dict[str, set[str]] = {}  # node_id -> set of labels
        self.cypher_statements: list[str] = []

    def add_chunks(self, chunks: list[CodeChunk]) -> None:
        """Add chunks as nodes with appropriate labels."""
        super().add_chunks(chunks)

        # Assign labels based on chunk types
        for node_id, node in self.nodes.items():
            labels = {"CodeChunk"}  # Base label for all chunks

            chunk_type = (
                node.chunk.metadata.get("chunk_type", node.chunk.node_type)
                if node.chunk.metadata
                else node.chunk.node_type
            )
            if chunk_type:
                # Convert chunk_type to Neo4j label format (PascalCase)
                label = self._to_pascal_case(chunk_type)
                labels.add(label)

            if node.chunk.language:
                # Add language as a label
                labels.add(node.chunk.language.capitalize())

            self.node_labels[node_id] = labels

    def _to_pascal_case(self, snake_str: str) -> str:
        """Convert snake_case to PascalCase for Neo4j labels."""
        components = snake_str.split("_")
        return "".join(x.title() for x in components)

    def _escape_property_value(self, value: Any) -> str:
        """Escape property values for Cypher queries."""
        if isinstance(value, str):
            # Escape single quotes and backslashes
            escaped = value.replace("\\", "\\\\").replace("'", "\\'")
            return f"'{escaped}'"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        # Convert to string and escape
        escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"

    def _generate_node_csv(self) -> tuple[str, str]:
        """Generate CSV content for nodes.

        Returns:
            Tuple of (headers_csv, data_csv)
        """
        # Collect all unique properties
        all_properties = set()
        for node in self.nodes.values():
            all_properties.update(node.properties.keys())

        # Create headers
        headers = ["nodeId:ID", ":LABEL"] + sorted(list(all_properties))

        # Create data rows
        rows = []
        for node_id, node in self.nodes.items():
            labels = ";".join(sorted(self.node_labels.get(node_id, {"CodeChunk"})))
            row = [node_id, labels]

            for prop in sorted(list(all_properties)):
                value = node.properties.get(prop, "")
                # CSV encoding handles escaping
                row.append(value)

            rows.append(row)

        # Generate CSV strings
        header_io = StringIO()
        header_writer = csv.writer(header_io)
        header_writer.writerow(headers)

        data_io = StringIO()
        data_writer = csv.writer(data_io)
        data_writer.writerows(rows)

        return header_io.getvalue().strip(), data_io.getvalue().strip()

    def _generate_relationship_csv(self) -> tuple[str, str]:
        """Generate CSV content for relationships.

        Returns:
            Tuple of (headers_csv, data_csv)
        """
        # Collect all unique properties
        all_properties = set()
        for edge in self.edges:
            all_properties.update(edge.properties.keys())

        # Create headers
        headers = [":START_ID", ":END_ID", ":TYPE"] + sorted(list(all_properties))

        # Create data rows
        rows = []
        for edge in self.edges:
            row = [edge.source_id, edge.target_id, edge.relationship_type]

            for prop in sorted(list(all_properties)):
                value = edge.properties.get(prop, "")
                row.append(value)

            rows.append(row)

        # Generate CSV strings
        header_io = StringIO()
        header_writer = csv.writer(header_io)
        header_writer.writerow(headers)

        data_io = StringIO()
        data_writer = csv.writer(data_io)
        data_writer.writerows(rows)

        return header_io.getvalue().strip(), data_io.getvalue().strip()

    def generate_cypher_statements(self, batch_size: int = 1000) -> list[str]:
        """Generate Cypher statements for creating the graph.

        Args:
            batch_size: Number of operations per transaction

        Returns:
            List of Cypher statements
        """
        statements = []

        # Generate constraint statements
        unique_labels = set()
        for labels in self.node_labels.values():
            unique_labels.update(labels)

        statements.append("// Create constraints for unique node IDs")
        for label in unique_labels:
            # Neo4j 5.x syntax
            statements.append(
                f"CREATE CONSTRAINT {label.lower()}_unique_id IF NOT EXISTS"
                f" FOR (n:{label}) REQUIRE n.nodeId IS UNIQUE;",
            )

        # Generate index statements
        statements.append("\n// Create indexes for better query performance")
        statements.append(
            "CREATE INDEX codechunk_file_path IF NOT EXISTS FOR (n:CodeChunk) ON (n.file_path);",
        )
        statements.append(
            "CREATE INDEX codechunk_node_type IF NOT EXISTS FOR (n:CodeChunk) ON (n.node_type);",
        )
        statements.append(
            "CREATE INDEX codechunk_language IF NOT EXISTS FOR (n:CodeChunk) ON (n.language);",
        )

        # Generate node creation statements
        statements.append("\n// Create nodes")
        for node_id, node in self.nodes.items():
            labels = ":".join(sorted(self.node_labels.get(node_id, {"CodeChunk"})))

            # Build property list
            props = ["nodeId: " + self._escape_property_value(node_id)]
            for key, value in sorted(node.properties.items()):
                if value is not None and value != "":
                    props.append(f"{key}: {self._escape_property_value(value)}")

            cypher = f"CREATE (n:{labels} {{\n  {',\n  '.join(props)}\n}});"
            statements.append(cypher)

        # Generate relationship creation statements
        if self.edges:
            statements.append("\n// Create relationships")
            for edge in self.edges:
                # Build property list for relationship
                if edge.properties:
                    props = []
                    for key, value in sorted(edge.properties.items()):
                        if value is not None:
                            props.append(f"{key}: {self._escape_property_value(value)}")
                    prop_str = " {" + ", ".join(props) + "}"
                else:
                    prop_str = ""

                cypher = (
                    f"MATCH (a:CodeChunk {{nodeId: {self._escape_property_value(edge.source_id)}}}),\n"
                    f"      (b:CodeChunk {{nodeId: {self._escape_property_value(edge.target_id)}}})\n"
                    f"CREATE (a)-[:{edge.relationship_type}{prop_str}]->(b);"
                )
                statements.append(cypher)

        # Add transaction boundaries for batching if needed
        if batch_size and len(self.nodes) + len(self.edges) > batch_size:
            batched_statements = []

            # Collect constraint and index statements
            setup_statements = []
            create_statements = []

            for stmt in statements:
                if "CONSTRAINT" in stmt or "INDEX" in stmt or stmt.startswith("//"):
                    setup_statements.append(stmt)
                else:
                    create_statements.append(stmt)

            # Add setup statements first
            batched_statements.extend(setup_statements)

            # Batch the CREATE statements
            if create_statements:
                batched_statements.append("\n// Batched operations")
                for i in range(0, len(create_statements), batch_size):
                    batch = create_statements[i : i + batch_size]
                    batched_statements.append(f"\n// Batch {i // batch_size + 1}")
                    batched_statements.extend(batch)
                    if i + batch_size < len(create_statements):
                        batched_statements.append(":commit;")

            return batched_statements

        return statements

    def export_string(self, format: str = "cypher", **options) -> str:
        """Export as string in specified format.

        Args:
            format: Export format - "cypher", "csv_nodes", or "csv_relationships"
            **options: Additional options

        Returns:
            Export data as string
        """
        if format == "cypher":
            statements = self.generate_cypher_statements(**options)
            return "\n\n".join(statements)
        if format == "csv_nodes":
            headers, data = self._generate_node_csv()
            return headers + "\n" + data
        if format == "csv_relationships":
            headers, data = self._generate_relationship_csv()
            return headers + "\n" + data
        raise ValueError(f"Unknown format: {format}")

    def export(self, output_path: Path, format: str = "csv", **options) -> None:
        """Export to Neo4j import format.

        Args:
            output_path: Base path for output files
            format: Export format - "csv" or "cypher"
            **options: Additional options
        """
        if format == "csv":
            # Export nodes CSV
            nodes_path = output_path.parent / f"{output_path.stem}_nodes.csv"
            headers, data = self._generate_node_csv()
            nodes_path.write_text(headers + "\n" + data, encoding="utf-8")

            # Export relationships CSV
            if self.edges:
                rels_path = output_path.parent / f"{output_path.stem}_relationships.csv"
                headers, data = self._generate_relationship_csv()
                rels_path.write_text(headers + "\n" + data, encoding="utf-8")

            # Export import command
            import_cmd = self._generate_import_command(
                nodes_path,
                rels_path if self.edges else None,
            )
            cmd_path = output_path.parent / f"{output_path.stem}_import.sh"
            cmd_path.write_text(import_cmd, encoding="utf-8")
            cmd_path.chmod(0o755)  # Make executable

        elif format == "cypher":
            statements = self.generate_cypher_statements(**options)
            output_path.write_text("\n\n".join(statements), encoding="utf-8")
        else:
            raise ValueError(f"Unknown format: {format}")

    def _generate_import_command(
        self,
        nodes_path: Path,
        relationships_path: Path | None,
    ) -> str:
        """Generate neo4j-admin import command."""
        cmd = "#!/bin/bash\n\n"
        cmd += "# Neo4j import command for code chunks\n"
        cmd += "# Adjust paths and database name as needed\n\n"

        cmd += "neo4j-admin import \\\n"
        cmd += "  --database=neo4j \\\n"
        cmd += f"  --nodes={nodes_path.name} \\\n"

        if relationships_path:
            cmd += f"  --relationships={relationships_path.name} \\\n"

        cmd += "  --skip-bad-relationships=true \\\n"
        cmd += "  --skip-duplicate-nodes=true\n"

        return cmd
