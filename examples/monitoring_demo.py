#!/usr/bin/env python3
"""
Monitoring and Observability System Demo

This example demonstrates how to use the comprehensive monitoring and observability
system for the treesitter-chunker. It shows real-time metrics collection, distributed
tracing, log aggregation, and dashboard generation.
"""

import logging
import random
import time
from datetime import datetime

from chunker.monitoring import MonitoringSystem

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def simulate_chunking_operation(
    system: MonitoringSystem,
    file_path: str,
    file_type: str,
):
    """Simulate a realistic chunking operation with monitoring."""

    with system.trace_operation(
        "chunk_file",
        file_path=file_path,
        file_type=file_type,
        file_size=random.randint(1024, 10240),
    ) as span:

        logger.info(f"Starting to chunk file: {file_path}")

        # Simulate file parsing
        with system.trace_operation("parse_file") as parse_span:
            parse_time = random.uniform(0.1, 0.5)
            time.sleep(parse_time)

            ast_nodes = random.randint(50, 500)
            parse_span.set_tag("ast_nodes", ast_nodes)
            system.record_metric("ast_parse_time_ms", parse_time * 1000)
            system.record_metric("ast_nodes_count", ast_nodes, {"file_type": file_type})

            logger.debug(f"Parsed {ast_nodes} AST nodes in {parse_time:.3f}s")

        # Simulate chunking
        with system.trace_operation("extract_chunks") as chunk_span:
            chunk_time = random.uniform(0.2, 0.8)
            time.sleep(chunk_time)

            num_chunks = random.randint(5, 25)
            chunk_span.set_tag("chunks_extracted", num_chunks)
            chunk_span.set_tag("extraction_method", "semantic")

            system.record_metric("chunk_extraction_time_ms", chunk_time * 1000)
            system.record_metric(
                "chunks_extracted",
                num_chunks,
                {"file_type": file_type},
            )

            # Record individual chunk metrics
            for i in range(num_chunks):
                chunk_size = random.randint(256, 2048)
                system.record_metric(
                    "chunk_size_bytes",
                    chunk_size,
                    {"file_type": file_type, "chunk_index": str(i)},
                )

            logger.info(f"Extracted {num_chunks} chunks in {chunk_time:.3f}s")

        # Simulate occasional errors
        if random.random() < 0.1:  # 10% error rate
            error_msg = f"Failed to process {file_path}"
            span.set_tag("error", True)
            span.set_tag("error.type", "ProcessingError")
            span.log(error_msg, level="error")

            system.record_metric("chunking_errors", 1, {"error_type": "processing"})
            logger.error(error_msg)

            raise RuntimeError(error_msg)

        # Record successful completion
        total_time = time.time() - span.start_time.timestamp()
        span.set_tag("success", True)
        span.set_tag("total_chunks", num_chunks)

        system.record_metric("chunking_operations_total", 1)
        system.record_metric("chunking_success_total", 1, {"file_type": file_type})
        system.record_metric("chunking_duration_ms", total_time * 1000)

        logger.info(f"Successfully chunked {file_path} into {num_chunks} chunks")


def simulate_batch_processing(system: MonitoringSystem):
    """Simulate batch processing of multiple files."""

    files_to_process = [
        ("src/main.py", "python"),
        ("src/utils.py", "python"),
        ("lib/parser.js", "javascript"),
        ("components/App.tsx", "typescript"),
        ("models/user.py", "python"),
        ("api/routes.js", "javascript"),
        ("utils/helpers.ts", "typescript"),
        ("tests/test_main.py", "python"),
    ]

    with system.trace_operation(
        "batch_processing",
        batch_size=len(files_to_process),
    ) as batch_span:

        successful_files = 0
        failed_files = 0

        for file_path, file_type in files_to_process:
            try:
                simulate_chunking_operation(system, file_path, file_type)
                successful_files += 1
            except RuntimeError:
                failed_files += 1
                system.record_metric(
                    "chunking_errors",
                    1,
                    {"error_type": "file_processing"},
                )

            # Small delay between files
            time.sleep(0.1)

        batch_span.set_tag("files_processed", len(files_to_process))
        batch_span.set_tag("successful_files", successful_files)
        batch_span.set_tag("failed_files", failed_files)

        # Record batch metrics
        system.record_metric("batch_processing_total", 1)
        system.record_metric("files_processed_total", len(files_to_process))
        system.record_metric(
            "batch_success_rate",
            (successful_files / len(files_to_process)) * 100,
        )

        logger.info(
            f"Batch processing complete: {successful_files} successful, {failed_files} failed",
        )


def demonstrate_alerts(system: MonitoringSystem):
    """Demonstrate the alerting system."""

    logger.info("Setting up custom alert rules...")

    # Add custom alert rules
    high_error_rate_rule = {
        "name": "High Error Rate",
        "type": "metric",
        "metric": "chunking_errors",
        "condition": "greater_than",
        "threshold": 3.0,
        "severity": "warning",
        "description": "Too many chunking errors detected",
    }

    low_success_rate_rule = {
        "name": "Low Success Rate",
        "type": "metric",
        "metric": "batch_success_rate",
        "condition": "less_than",
        "threshold": 80.0,
        "severity": "critical",
        "description": "Batch processing success rate is too low",
    }

    system.add_alert_rule(high_error_rate_rule)
    system.add_alert_rule(low_success_rate_rule)

    # Add alert callback
    def alert_handler(alert):
        logger.warning(f"ALERT TRIGGERED: {alert.title} - {alert.description}")
        logger.warning(
            f"  Metric: {alert.metric_name} = {alert.current_value} (threshold: {alert.threshold})",
        )
        logger.warning(f"  Severity: {alert.severity}")

    system.add_alert_callback(alert_handler)

    logger.info("Alert rules configured. Alerts will be triggered during processing.")


def demonstrate_dashboards(system: MonitoringSystem):
    """Demonstrate dashboard creation and data generation."""

    logger.info("Creating custom dashboard...")

    # Create a custom dashboard
    system.dashboard_generator.create_dashboard(
        "chunking_performance",
        "Chunking Performance Dashboard",
        "Real-time performance metrics for chunking operations",
        refresh_interval=30,
    )

    # Add widgets to the dashboard
    system.dashboard_generator.add_widget(
        "chunking_performance",
        "chunking_duration_chart",
        "line_chart",
        "Chunking Duration Over Time",
        {"metrics": ["chunking_duration_ms"], "y_axis_title": "Duration (ms)"},
        {"x": 0, "y": 0, "width": 6, "height": 4},
    )

    system.dashboard_generator.add_widget(
        "chunking_performance",
        "success_rate_gauge",
        "gauge",
        "Success Rate",
        {
            "metric": "batch_success_rate",
            "min_value": 0,
            "max_value": 100,
            "unit": "%",
            "thresholds": [
                {"value": 80, "color": "yellow"},
                {"value": 90, "color": "green"},
            ],
        },
        {"x": 6, "y": 0, "width": 3, "height": 4},
    )

    system.dashboard_generator.add_widget(
        "chunking_performance",
        "chunks_extracted_counter",
        "counter",
        "Total Chunks Extracted",
        {"metric": "chunks_extracted", "unit": "chunks"},
        {"x": 9, "y": 0, "width": 3, "height": 4},
    )

    system.dashboard_generator.add_widget(
        "chunking_performance",
        "performance_table",
        "table",
        "Performance Metrics Summary",
        {
            "metrics": [
                "chunking_duration_ms",
                "chunks_extracted",
                "ast_nodes_count",
                "chunk_size_bytes",
            ],
        },
        {"x": 0, "y": 4, "width": 12, "height": 4},
    )

    logger.info("Custom dashboard created with 4 widgets")


def main():
    """Main demonstration function."""

    print("🔍 Treesitter-Chunker Monitoring & Observability Demo")
    print("=" * 60)

    # Initialize monitoring system
    system = MonitoringSystem(
        service_name="chunker-demo",
        metrics_interval=2.0,  # Collect metrics every 2 seconds
        trace_sampling_rate=1.0,  # Sample all traces for demo
        max_logs=1000,
    )

    try:
        with system:
            logger.info("Monitoring system started")

            # Setup alerts and dashboards
            demonstrate_alerts(system)
            demonstrate_dashboards(system)

            print("\n📊 Starting batch processing simulation...")

            # Run several batch processing cycles
            for batch_num in range(3):
                logger.info(f"Starting batch {batch_num + 1}/3")
                try:
                    simulate_batch_processing(system)
                except Exception as e:
                    logger.error(f"Batch {batch_num + 1} failed: {e}")

                # Brief pause between batches
                time.sleep(2)

            print("\n📈 Processing complete! Generating reports...")

            # Get system health
            health = system.get_system_health()
            print(f"\nSystem Health: {health['monitoring_status']}")
            print(
                f"Active Components: {len([c for c in health['components'].values() if c.get('status') == 'running'])}",
            )
            print(f"Active Alerts: {health['active_alerts']}")

            # Get metrics summary
            metrics_summary = system.get_metrics_summary(duration_minutes=10)
            print(f"\nMetrics Collected: {len(metrics_summary)}")

            # Show some key metrics
            key_metrics = [
                "chunking_operations_total",
                "chunking_success_total",
                "chunking_errors",
                "chunks_extracted",
                "batch_success_rate",
            ]

            print("\nKey Metrics:")
            for metric in key_metrics:
                if metric in metrics_summary and "error" not in metrics_summary[metric]:
                    summary = metrics_summary[metric]
                    print(
                        f"  {metric}: {summary['latest']} (avg: {summary['avg']:.2f})",
                    )

            # Get dashboard data
            print("\n📊 Dashboard Data:")
            dashboard_data = system.get_dashboard_data(
                "chunking_performance",
                duration_minutes=10,
            )
            if "error" not in dashboard_data:
                widgets_data = dashboard_data["widgets_data"]
                print(f"  Dashboard widgets: {len(widgets_data)}")

                for widget_id, widget_data in widgets_data.items():
                    if "error" not in widget_data:
                        print(f"    {widget_id}: {widget_data['type']}")

            # Search for traces
            traces = system.tracing_manager.search_traces(limit=5)
            print(f"\nRecent Traces: {len(traces)}")
            for trace in traces[:3]:  # Show first 3
                print(
                    f"  {trace['trace_id'][:8]}... - {trace['root_operation']} ({trace['span_count']} spans)",
                )

            # Search for error logs
            error_logs = system.search_logs(level="ERROR", limit=5)
            print(f"\nError Logs: {len(error_logs)}")
            for log in error_logs[:3]:  # Show first 3
                print(f"  {log.timestamp.strftime('%H:%M:%S')} - {log.message}")

            print("\n✅ Demo complete! Monitoring data collected successfully.")
            print("\nKey features demonstrated:")
            print("  • Real-time metrics collection (system, application, business)")
            print("  • Distributed tracing with span hierarchies")
            print("  • Structured log aggregation with trace correlation")
            print("  • Custom dashboards with multiple widget types")
            print("  • Alert rules and callback system")
            print("  • Performance monitoring integration")

    except KeyboardInterrupt:
        print("\n\n⏹️  Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"\n❌ Demo failed: {e}")

    print("\n🔍 Monitoring system stopped.")


if __name__ == "__main__":
    main()
