"""Neo4j export implementation for code chunks."""

import csv
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from io import StringIO
from .graph_exporter_base import GraphExporterBase, GraphNode, GraphEdge
from ..types import CodeChunk


class Neo4jExporter(GraphExporterBase):
    """Export code chunks for Neo4j graph database import."""
    
    def __init__(self):
        super().__init__()
        self.node_labels: Dict[str, Set[str]] = {}  # node_id -> set of labels
        self.cypher_statements: List[str] = []
    
    def add_chunks(self, chunks: List[CodeChunk]) -> None:
        """Add chunks as nodes with appropriate labels."""
        super().add_chunks(chunks)
        
        # Assign labels based on chunk types
        for node_id, node in self.nodes.items():
            labels = {"CodeChunk"}  # Base label for all chunks
            
            chunk_type = node.chunk.metadata.get("chunk_type", node.chunk.node_type) if node.chunk.metadata else node.chunk.node_type
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
        components = snake_str.split('_')
        return ''.join(x.title() for x in components)
    
    def _escape_property_value(self, value: Any) -> str:
        """Escape property values for Cypher queries."""
        if isinstance(value, str):
            # Escape single quotes and backslashes
            escaped = value.replace('\\', '\\\\').replace("'", "\\'")
            return f"'{escaped}'"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif value is None:
            return "null"
        else:
            # Convert to string and escape
            escaped = str(value).replace('\\', '\\\\').replace("'", "\\'")
            return f"'{escaped}'"
    
    def _generate_node_csv(self) -> Tuple[str, str]:
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
    
    def _generate_relationship_csv(self) -> Tuple[str, str]:
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
    
    def generate_cypher_statements(self, batch_size: int = 1000) -> List[str]:
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
        
        for label in unique_labels:
            if label != "CodeChunk":  # Don't create constraint on base label
                statements.append(
                    f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.nodeId IS UNIQUE;"
                )
        
        # Generate index statements
        statements.append("CREATE INDEX IF NOT EXISTS FOR (n:CodeChunk) ON (n.file_path);")
        statements.append("CREATE INDEX IF NOT EXISTS FOR (n:CodeChunk) ON (n.chunk_type);")
        statements.append("CREATE INDEX IF NOT EXISTS FOR (n:CodeChunk) ON (n.language);")
        
        # Generate node creation statements in batches
        node_items = list(self.nodes.items())
        for i in range(0, len(node_items), batch_size):
            batch = node_items[i:i + batch_size]
            
            cypher = "UNWIND $batch AS item\n"
            cypher += "CREATE (n:CodeChunk)\n"
            cypher += "SET n = item.properties\n"
            cypher += "SET n.nodeId = item.id\n"
            cypher += "WITH n, item\n"
            cypher += "CALL apoc.create.addLabels(n, item.labels) YIELD node\n"
            cypher += "RETURN count(node);"
            
            # Create the parameter object
            batch_data = []
            for node_id, node in batch:
                labels = list(self.node_labels.get(node_id, {"CodeChunk"}))
                labels.remove("CodeChunk")  # Already set as base label
                batch_data.append({
                    "id": node_id,
                    "properties": node.properties,
                    "labels": labels
                })
            
            statements.append(f"// Batch {i // batch_size + 1} of nodes")
            statements.append(f"// Parameters: {batch_data}")
            statements.append(cypher)
        
        # Generate relationship creation statements in batches
        for i in range(0, len(self.edges), batch_size):
            batch = self.edges[i:i + batch_size]
            
            cypher = "UNWIND $batch AS rel\n"
            cypher += "MATCH (a:CodeChunk {nodeId: rel.source})\n"
            cypher += "MATCH (b:CodeChunk {nodeId: rel.target})\n"
            cypher += "CALL apoc.create.relationship(a, rel.type, rel.properties, b) YIELD rel AS r\n"
            cypher += "RETURN count(r);"
            
            # Create the parameter object
            batch_data = []
            for edge in batch:
                batch_data.append({
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "type": edge.relationship_type,
                    "properties": edge.properties
                })
            
            statements.append(f"// Batch {i // batch_size + 1} of relationships")
            statements.append(f"// Parameters: {batch_data}")
            statements.append(cypher)
        
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
        elif format == "csv_nodes":
            headers, data = self._generate_node_csv()
            return headers + "\n" + data
        elif format == "csv_relationships":
            headers, data = self._generate_relationship_csv()
            return headers + "\n" + data
        else:
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
            nodes_path.write_text(headers + "\n" + data, encoding='utf-8')
            
            # Export relationships CSV
            if self.edges:
                rels_path = output_path.parent / f"{output_path.stem}_relationships.csv"
                headers, data = self._generate_relationship_csv()
                rels_path.write_text(headers + "\n" + data, encoding='utf-8')
            
            # Export import command
            import_cmd = self._generate_import_command(nodes_path, rels_path if self.edges else None)
            cmd_path = output_path.parent / f"{output_path.stem}_import.sh"
            cmd_path.write_text(import_cmd, encoding='utf-8')
            cmd_path.chmod(0o755)  # Make executable
            
        elif format == "cypher":
            statements = self.generate_cypher_statements(**options)
            output_path.write_text("\n\n".join(statements), encoding='utf-8')
        else:
            raise ValueError(f"Unknown format: {format}")
    
    def _generate_import_command(self, nodes_path: Path, relationships_path: Optional[Path]) -> str:
        """Generate neo4j-admin import command."""
        cmd = "#!/bin/bash\n\n"
        cmd += "# Neo4j import command for code chunks\n"
        cmd += "# Adjust paths and database name as needed\n\n"
        
        cmd += "neo4j-admin import \\\n"
        cmd += f"  --database=neo4j \\\n"
        cmd += f"  --nodes={nodes_path.name} \\\n"
        
        if relationships_path:
            cmd += f"  --relationships={relationships_path.name} \\\n"
        
        cmd += "  --skip-bad-relationships=true \\\n"
        cmd += "  --skip-duplicate-nodes=true\n"
        
        return cmd