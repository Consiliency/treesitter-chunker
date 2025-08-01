"""Neo4j export implementation for code chunks."""
import csv
from io import StringIO
from pathlib import Path
from typing import Any

from chunker.types import CodeChunk

from .graph_exporter_base import GraphExporterBase


class Neo4jExporter(GraphExporterBase):
    """Export code chunks for Neo4j graph database import."""

    def __init__(self):
        super().__init__()
        self.node_labels: dict[str, set[str]] = {}
        self.cypher_statements: list[str] = []

    def add_chunks(self, chunks: list[CodeChunk]) -> None:
        """Add chunks as nodes with appropriate labels."""
        super().add_chunks(chunks)
        for node_id, node in self.nodes.items():
            labels = {"CodeChunk"}
            chunk_type = node.chunk.metadata.get("chunk_type", node.chunk.
                node_type) if node.chunk.metadata else node.chunk.node_type
            if chunk_type:
                label = self._to_pascal_case(chunk_type)
                labels.add(label)
            if node.chunk.language:
                labels.add(node.chunk.language.capitalize())
            self.node_labels[node_id] = labels

    @staticmethod
    def _to_pascal_case(snake_str: str) -> str:
        """Convert snake_case to PascalCase for Neo4j labels."""
        components = snake_str.split("_")
        return "".join(x.title() for x in components)

    @staticmethod
    def _escape_property_value(value: Any) -> str:
        """Escape property values for Cypher queries."""
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace("'", "\\'")
            return f"'{escaped}'"
        if isinstance(value, int | float):
            return str(value)
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"

    def _generate_node_csv(self) -> tuple[str, str]:
        """Generate CSV content for nodes.

        Returns:
            Tuple of (headers_csv, data_csv)
        """
        all_properties = set()
        for node in self.nodes.values():
            all_properties.update(node.properties.keys())
        headers = ["nodeId:ID", ":LABEL", *sorted(all_properties)]
        rows = []
        for node_id, node in self.nodes.items():
            labels = ";".join(sorted(self.node_labels.get(node_id, {
                "CodeChunk"})))
            row = [node_id, labels]
            for prop in sorted(all_properties):
                value = node.properties.get(prop, "")
                row.append(value)
            rows.append(row)
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
        all_properties = set()
        for edge in self.edges:
            all_properties.update(edge.properties.keys())
        headers = [":START_ID", ":END_ID", ":TYPE", *sorted(all_properties)]
        rows = []
        for edge in self.edges:
            row = [edge.source_id, edge.target_id, edge.relationship_type]
            for prop in sorted(all_properties):
                value = edge.properties.get(prop, "")
                row.append(value)
            rows.append(row)
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
        unique_labels = set()
        for labels in self.node_labels.values():
            unique_labels.update(labels)
        statements.append("// Create constraints for unique node IDs")
        statements.extend(
            f"CREATE CONSTRAINT {label.lower()}_unique_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.nodeId IS UNIQUE;"
             for label in unique_labels)
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
        statements.append("\n// Create nodes")
        for node_id, node in self.nodes.items():
            labels = ":".join(sorted(self.node_labels.get(node_id, {
                "CodeChunk"})))
            props = ["nodeId: " + self._escape_property_value(node_id)]
            for key, value in sorted(node.properties.items()):
                if value is not None and value != "":
                    props.append(f"{key}: {self._escape_property_value(value)}",
                        )
            cypher = f"CREATE (n:{labels} {{" + "\n  " + ",\n  ".join(props,
                ) + "\n}});"
            statements.append(cypher)
        if self.edges:
            statements.append("\n// Create relationships")
            for edge in self.edges:
                if edge.properties:
                    props = []
                    for key, value in sorted(edge.properties.items()):
                        if value is not None:
                            props.append(
                                f"{key}: {self._escape_property_value(value)}")
                    prop_str = " {" + ", ".join(props) + "}"
                else:
                    prop_str = ""
                cypher = f"""MATCH (a:CodeChunk {{nodeId: {self._escape_property_value(edge.source_id)}}}),
      (b:CodeChunk {{nodeId: {self._escape_property_value(edge.target_id)}}})
CREATE (a)-[:{edge.relationship_type}{prop_str}]->(b);"""
                statements.append(cypher)
        if batch_size and len(self.nodes) + len(self.edges) > batch_size:
            batched_statements = []
            setup_statements = []
            create_statements = []
            for stmt in statements:
                if "CONSTRAINT" in stmt or "INDEX" in stmt or stmt.startswith(
                    "//"):
                    setup_statements.append(stmt)
                else:
                    create_statements.append(stmt)
            batched_statements.extend(setup_statements)
            if create_statements:
                batched_statements.append("\n// Batched operations")
                for i in range(0, len(create_statements), batch_size):
                    batch = create_statements[i:i + batch_size]
                    batched_statements.append(
                        f"\n// Batch {i // batch_size + 1}")
                    batched_statements.extend(batch)
                    if i + batch_size < len(create_statements):
                        batched_statements.append(":commit;")
            return batched_statements
        return statements

    def export_string(self, fmt: str = "cypher", **options) -> str:
        """Export as string in specified fmt.

        Args:
            fmt: Export fmt - "cypher", "csv_nodes", or "csv_relationships"
            **options: Additional options

        Returns:
            Export data as string
        """
        if fmt == "cypher":
            statements = self.generate_cypher_statements(**options)
            return "\n\n".join(statements)
        if fmt == "csv_nodes":
            headers, data = self._generate_node_csv()
            return headers + "\n" + data
        if fmt == "csv_relationships":
            headers, data = self._generate_relationship_csv()
            return headers + "\n" + data
        raise ValueError(f"Unknown fmt: {fmt}")

    def export(self, output_path: Path, fmt: str = "csv", **options) -> None:
        """Export to Neo4j import fmt.

        Args:
            output_path: Base path for output files
            fmt: Export fmt - "csv" or "cypher"
            **options: Additional options
        """
        if fmt == "csv":
            nodes_path = output_path.parent / f"{output_path.stem}_nodes.csv"
            headers, data = self._generate_node_csv()
            nodes_path.write_text(headers + "\n" + data, encoding="utf-8")
            if self.edges:
                rels_path = (output_path.parent /
                    f"{output_path.stem}_relationships.csv")
                headers, data = self._generate_relationship_csv()
                rels_path.write_text(headers + "\n" + data, encoding="utf-8")
            import_cmd = self._generate_import_command(nodes_path,
                rels_path if self.edges else None)
            cmd_path = output_path.parent / f"{output_path.stem}_import.sh"
            cmd_path.write_text(import_cmd, encoding="utf-8")
            cmd_path.chmod(493)
        elif fmt == "cypher":
            statements = self.generate_cypher_statements(**options)
            output_path.write_text("\n\n".join(statements), encoding="utf-8")
        else:
            raise ValueError(f"Unknown fmt: {fmt}")

    @staticmethod
    def _generate_import_command(nodes_path: Path, relationships_path: (
        Path | None)) -> str:
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
