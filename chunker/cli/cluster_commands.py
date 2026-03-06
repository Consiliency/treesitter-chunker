"""CLI commands for hierarchical clustering of code symbols."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chunker.extractors.python import PythonExtractor


def setup_cluster_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register clustering commands."""
    cluster_parser = subparsers.add_parser(
        "cluster", help="Infer architectural modules from code"
    )
    cluster_subparsers = cluster_parser.add_subparsers(dest="cluster_command")

    # cluster infer
    infer_parser = cluster_subparsers.add_parser(
        "infer", help="Infer module hierarchy from symbols"
    )
    infer_parser.add_argument("path", help="Path to analyze")
    infer_parser.add_argument("-o", "--output", help="Output JSON file")
    infer_parser.add_argument(
        "--resolution",
        choices=["coarse", "medium", "fine"],
        default="medium",
        help="Clustering resolution",
    )
    infer_parser.add_argument(
        "--coarse-resolution",
        type=float,
        default=None,
        help="Leiden resolution for component level (overrides --resolution)",
    )
    infer_parser.add_argument(
        "--fine-resolution",
        type=float,
        default=None,
        help="Leiden resolution for sub-component level (overrides --resolution)",
    )
    infer_parser.add_argument(
        "--no-infrastructure", action="store_true", help="Skip infrastructure detection"
    )
    infer_parser.add_argument(
        "--format", choices=["json", "summary"], default="json", help="Output format"
    )
    infer_parser.set_defaults(func=cmd_cluster_infer)


def resolution_to_params(resolution: str) -> tuple[float, float]:
    """Convert named resolution to (coarse, fine) parameter pair."""
    presets = {
        "coarse": (0.3, 0.8),
        "medium": (0.5, 1.5),
        "fine": (0.8, 2.5),
    }
    return presets.get(resolution, presets["medium"])


def cmd_cluster_infer(args: argparse.Namespace) -> int:
    """Handle 'cluster infer' command."""
    # Import here to avoid circular imports and defer dependency check
    try:
        from chunker.clustering import ClusteringEngine
    except ImportError as e:
        print(f"Error: Clustering dependencies not installed: {e}", file=sys.stderr)
        print("Install with: pip install networkx leidenalg igraph", file=sys.stderr)
        return 1

    path = Path(args.path)
    if not path.exists():
        print(f"Error: Path does not exist: {path}", file=sys.stderr)
        return 1

    # Determine resolution parameters
    if args.coarse_resolution is not None and args.fine_resolution is not None:
        coarse_res, fine_res = args.coarse_resolution, args.fine_resolution
    else:
        coarse_res, fine_res = resolution_to_params(args.resolution)
        if args.coarse_resolution is not None:
            coarse_res = args.coarse_resolution
        if args.fine_resolution is not None:
            fine_res = args.fine_resolution

    # 1. Extract symbols
    print(f"Extracting symbols from {path}...", file=sys.stderr)
    extractor = PythonExtractor()

    # Collect files
    if path.is_file():
        files = [path]
    else:
        files = list(path.rglob("*.py"))
        files = [
            f
            for f in files
            if not any(
                part in f.parts
                for part in [
                    "__pycache__",
                    ".git",
                    ".venv",
                    "venv",
                    "node_modules",
                    ".tox",
                    ".pytest_cache",
                    "build",
                    "dist",
                    ".eggs",
                ]
            )
        ]

    if not files:
        print(f"Error: No Python files found in {path}", file=sys.stderr)
        return 1

    # Extract from all files
    all_symbols: dict[str, Any] = {}
    all_relationships: list[dict] = []

    for file_path in sorted(files):
        try:
            source_code = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            print(f"Warning: Skipping {file_path}: {e}", file=sys.stderr)
            continue

        try:
            rel_path = file_path.relative_to(path if path.is_dir() else path.parent)
            module_parts = list(rel_path.parts)
            if module_parts[-1].endswith(".py"):
                module_parts[-1] = module_parts[-1][:-3]
            module_name = ".".join(module_parts)
        except ValueError:
            module_name = file_path.stem

        result = extractor.extract_symbols(source_code, file_path, module_name)

        if result.get("symbol_lookup"):
            all_symbols.update(result["symbol_lookup"])
        all_relationships.extend(result["relationships"])

    if not all_symbols:
        print("Error: No symbols extracted", file=sys.stderr)
        return 1

    # Post-process relationships to validate is_internal flag with combined symbol_lookup
    for rel in all_relationships:
        from_exists = rel["from"] in all_symbols
        to_exists = rel["to"] in all_symbols
        rel["is_internal"] = from_exists and to_exists

    print(
        f"Extracted {len(all_symbols)} symbols, {len(all_relationships)} relationships",
        file=sys.stderr,
    )

    # 2. Run clustering
    print("Running hierarchical clustering...", file=sys.stderr)
    engine = ClusteringEngine(
        coarse_resolution=coarse_res,
        fine_resolution=fine_res,
        detect_infrastructure=not args.no_infrastructure,
    )

    cluster_result = engine.cluster(all_symbols, all_relationships)

    # 3. Output results
    if args.format == "summary":
        print_summary(cluster_result)
    else:
        json_output = json.dumps(cluster_result, indent=2, default=str)
        if args.output:
            output_path = Path(args.output)
            output_path.write_text(json_output, encoding="utf-8")
            print(f"Output written to: {output_path}", file=sys.stderr)
        else:
            print(json_output)

    return 0


def print_summary(result: dict[str, Any]) -> None:
    """Print human-readable summary of clustering results."""
    hierarchy = result.get("hierarchy", {})
    infrastructure = result.get("infrastructure", [])
    metrics = result.get("metrics", {})

    print("\n=== Clustering Summary ===\n")
    print(f"Total symbols: {metrics.get('total_symbols', 'N/A')}")
    print(f"Total components: {metrics.get('total_components', 'N/A')}")
    print(
        f"Overall modularity: {metrics.get('overall_modularity', 'N/A'):.3f}"
        if isinstance(metrics.get("overall_modularity"), (int, float))
        else f"Overall modularity: {metrics.get('overall_modularity', 'N/A')}"
    )
    print(f"Infrastructure nodes: {len(infrastructure)}")

    print("\n--- Components ---")
    for i, child in enumerate(hierarchy.get("children", [])):
        size = len(child.get("members", []))
        quality = (
            child.get("metrics", {}).get("quality_score", "N/A")
            if child.get("metrics")
            else "N/A"
        )
        if isinstance(quality, float):
            quality = f"{quality:.2f}"
        print(
            f"  [{i}] {child.get('id', 'unknown')}: {size} symbols (quality: {quality})"
        )

    if infrastructure:
        print("\n--- Infrastructure ---")
        for node in infrastructure[:10]:  # Limit to first 10
            print(f"  - {node}")
        if len(infrastructure) > 10:
            print(f"  ... and {len(infrastructure) - 10} more")
