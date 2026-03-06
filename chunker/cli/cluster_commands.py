"""CLI commands for hierarchical clustering of code symbols."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from chunker.symbol_graph import extract_symbol_graph


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
    infer_parser.add_argument(
        "-l",
        "--language",
        default="python",
        help="Language to analyze (default: python)",
    )
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
    extraction = extract_symbol_graph(path, args.language)
    all_symbols = extraction["symbol_lookup"]
    all_relationships = extraction["relationships"]

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
