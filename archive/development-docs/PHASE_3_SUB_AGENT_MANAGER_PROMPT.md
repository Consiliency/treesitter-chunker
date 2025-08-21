# PHASE 3 SUB-AGENT MANAGER PROMPT
# Performance Optimization & Validation - Parallel Execution

## AGENT IDENTIFICATION & ROLES

**WHO I AM**: I am the primary AI agent working on Phase 1.7, Phase 1.8, Phase 1.9, Phase 2, and Phase 3 implementation planning and coordination. I will NOT touch any of the files assigned to sub-agents in this prompt.

**WHO YOU ARE**: You are the sub-agent manager responsible for coordinating execution of Phase 3 tasks. These tasks implement comprehensive performance optimization, validation, and production deployment readiness for the complete treesitter-chunker system.

**WHO THE SUB-AGENTS ARE**: Individual AI agents that will implement specific performance optimization, validation, and deployment components. Each sub-agent works on exactly ONE file and ONE task.

## EXECUTION STRATEGY

**PARALLEL EXECUTION**: 6 tasks designed for parallel execution with clear dependencies.
**FILE ISOLATION**: Each sub-agent touches ONLY their assigned file - no cross-file dependencies.
**QUALITY ASSURANCE**: 95%+ test coverage and production-ready code required.
**DEPENDENCY MANAGEMENT**: Performance core framework must complete before other components can start.

## PHASE 3 TASKS OVERVIEW

**OBJECTIVE**: Implement comprehensive performance optimization, validation, and production deployment readiness.
**DEPENDENCIES**: Phase 2 (Language-specific extractors) must be complete.
**OUTPUT**: Production-ready system with performance optimization and comprehensive validation.
**TIMELINE**: 3 weeks with parallel execution.

**PARALLEL EXECUTION MODEL:**
- **Task 3.1**: Must complete first (performance core framework)
- **Tasks 3.2, 3.3, 3.4, 3.5**: Can start simultaneously after Task 3.1 completion
- **Task 3.6**: Must wait for ALL other tasks completion

---

## TASK 3.1: PERFORMANCE CORE FRAMEWORK

**ASSIGNED FILE**: `chunker/performance/core/performance_framework.py`
**SUB-AGENT**: Performance Core Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: Phase 2 must be complete

### FILE STRUCTURE TO CREATE:
```python
# chunker/performance/core/performance_framework.py

from typing import Dict, List, Optional, Any, Union, Tuple, Protocol
from pathlib import Path
import logging
import time
import psutil
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
import json

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetric:
    """Represents a performance metric with comprehensive data."""
    name: str
    value: float
    unit: str
    timestamp: datetime
    context: Dict[str, Any]
    category: str  # 'cpu', 'memory', 'io', 'network', 'custom'
    severity: str  # 'normal', 'warning', 'critical'
    metadata: Dict[str, Any]

@dataclass
class PerformanceProfile:
    """Comprehensive performance profile for a system component."""
    component_name: str
    metrics: List[PerformanceMetric]
    profile_time: float
    optimization_potential: float
    recommendations: List[str]
    baseline_comparison: Dict[str, Any]

class PerformanceManager:
    """Central performance orchestration and management."""
    
    def __init__(self):
        """Initialize the performance manager."""
        self.metrics_collector = MetricsCollector()
        self.optimization_engine = OptimizationEngine()
        self.performance_budget = PerformanceBudget()
        self.logger = logging.getLogger(f"{__name__}.PerformanceManager")
        
    def collect_system_metrics(self) -> PerformanceProfile:
        """Collect comprehensive system performance metrics."""
        # Implementation: System-wide metrics collection
        
    def analyze_performance(self) -> Dict[str, Any]:
        """Analyze current performance and identify bottlenecks."""
        # Implementation: Performance analysis
        
    def optimize_system(self) -> Dict[str, Any]:
        """Execute system-wide performance optimization."""
        # Implementation: System optimization
        
    def validate_optimizations(self) -> Dict[str, Any]:
        """Validate that optimizations improved performance."""
        # Implementation: Optimization validation

class MetricsCollector:
    """Real-time performance metrics collection and storage."""
    
    def __init__(self):
        """Initialize the metrics collector."""
        self.metrics_store = {}
        self.collection_thread = None
        self.is_collecting = False
        
    def start_collection(self, interval: float = 1.0) -> None:
        """Start continuous metrics collection."""
        # Implementation: Start metrics collection
        
    def stop_collection(self) -> None:
        """Stop metrics collection."""
        # Implementation: Stop metrics collection
        
    def collect_cpu_metrics(self) -> Dict[str, Any]:
        """Collect CPU performance metrics."""
        # Implementation: CPU metrics collection
        
    def collect_memory_metrics(self) -> Dict[str, Any]:
        """Collect memory performance metrics."""
        # Implementation: Memory metrics collection
        
    def collect_io_metrics(self) -> Dict[str, Any]:
        """Collect I/O performance metrics."""
        # Implementation: I/O metrics collection

class OptimizationEngine:
    """Core optimization algorithms and strategies."""
    
    def __init__(self):
        """Initialize the optimization engine."""
        self.optimization_strategies = {}
        self.performance_baseline = {}
        self.logger = logging.getLogger(f"{__name__}.OptimizationEngine")
        
    def detect_bottlenecks(self, profile: PerformanceProfile) -> List[str]:
        """Detect performance bottlenecks in the system."""
        # Implementation: Bottleneck detection
        
    def generate_optimizations(self, bottlenecks: List[str]) -> List[Dict[str, Any]]:
        """Generate optimization strategies for detected bottlenecks."""
        # Implementation: Optimization generation
        
    def apply_optimization(self, optimization: Dict[str, Any]) -> bool:
        """Apply a specific optimization strategy."""
        # Implementation: Optimization application
        
    def validate_optimization(self, optimization: Dict[str, Any]) -> bool:
        """Validate that an optimization improved performance."""
        # Implementation: Optimization validation

class PerformanceBudget:
    """Performance budget management and enforcement."""
    
    def __init__(self):
        """Initialize the performance budget."""
        self.budget_limits = {}
        self.current_usage = {}
        self.violations = []
        
    def set_budget_limit(self, metric: str, limit: float) -> None:
        """Set a budget limit for a specific metric."""
        # Implementation: Budget limit setting
        
    def check_budget_violation(self, metric: str, value: float) -> bool:
        """Check if a metric value violates budget limits."""
        # Implementation: Budget violation checking
        
    def get_budget_status(self) -> Dict[str, Any]:
        """Get current budget status and violations."""
        # Implementation: Budget status reporting

class PerformanceUtils:
    """Common performance utilities and helpers."""
    
    @staticmethod
    def measure_execution_time(func: callable) -> callable:
        """Decorator to measure function execution time."""
        # Implementation: Execution time measurement
        
    @staticmethod
    def profile_memory_usage(func: callable) -> callable:
        """Decorator to profile memory usage of functions."""
        # Implementation: Memory profiling
        
    @staticmethod
    def optimize_memory_allocation(size: int) -> int:
        """Optimize memory allocation size."""
        # Implementation: Memory optimization
        
    @staticmethod
    def cpu_affinity_optimization() -> None:
        """Optimize CPU affinity for performance."""
        # Implementation: CPU affinity optimization
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Provide robust performance framework** for all optimization components
3. **Add comprehensive type hints** for all functions
4. **Include detailed docstrings** explaining each method
5. **Handle edge cases** and error conditions gracefully
6. **Add logging** for debugging and monitoring
7. **Create unit tests** covering all methods
8. **Ensure no cross-file dependencies** within this task

---

## TASK 3.2: SYSTEM OPTIMIZATION ENGINE

**ASSIGNED FILE**: `chunker/performance/optimization/system_optimizer.py`
**SUB-AGENT**: System Optimization Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: Task 3.1 (Performance Core) must be complete

### FILE STRUCTURE TO CREATE:
```python
# chunker/performance/optimization/system_optimizer.py

from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
import logging
import psutil
import threading
import gc
import time

from ..core.performance_framework import PerformanceManager, PerformanceProfile

logger = logging.getLogger(__name__)

class SystemOptimizer:
    """Main system optimization orchestrator."""
    
    def __init__(self):
        """Initialize the system optimizer."""
        self.performance_manager = PerformanceManager()
        self.cpu_optimizer = CPUOptimizer()
        self.memory_optimizer = MemoryOptimizer()
        self.io_optimizer = IOOptimizer()
        self.logger = logging.getLogger(f"{__name__}.SystemOptimizer")
        
    def optimize_system(self) -> Dict[str, Any]:
        """Execute comprehensive system optimization."""
        # Implementation: System-wide optimization
        
    def optimize_cpu(self) -> Dict[str, Any]:
        """Optimize CPU performance."""
        # Implementation: CPU optimization
        
    def optimize_memory(self) -> Dict[str, Any]:
        """Optimize memory performance."""
        # Implementation: Memory optimization
        
    def optimize_io(self) -> Dict[str, Any]:
        """Optimize I/O performance."""
        # Implementation: I/O optimization
        
    def measure_improvements(self) -> Dict[str, Any]:
        """Measure performance improvements from optimizations."""
        # Implementation: Improvement measurement

class CPUOptimizer:
    """CPU utilization and performance optimization."""
    
    def __init__(self):
        """Initialize the CPU optimizer."""
        self.current_affinity = None
        self.thread_pools = {}
        self.logger = logging.getLogger(f"{__name__}.CPUOptimizer")
        
    def optimize_thread_pools(self) -> Dict[str, Any]:
        """Optimize thread pool configurations."""
        # Implementation: Thread pool optimization
        
    def set_cpu_affinity(self, cpu_list: List[int]) -> bool:
        """Set CPU affinity for optimal performance."""
        # Implementation: CPU affinity setting
        
    def optimize_cache_usage(self) -> Dict[str, Any]:
        """Optimize CPU cache usage patterns."""
        # Implementation: Cache optimization
        
    def balance_cpu_load(self) -> Dict[str, Any]:
        """Balance CPU load across available cores."""
        # Implementation: Load balancing

class MemoryOptimizer:
    """Memory allocation and performance optimization."""
    
    def __init__(self):
        """Initialize the memory optimizer."""
        self.memory_pools = {}
        self.gc_settings = {}
        self.logger = logging.getLogger(f"{__name__}.MemoryOptimizer")
        
    def optimize_garbage_collection(self) -> Dict[str, Any]:
        """Optimize garbage collection settings."""
        # Implementation: GC optimization
        
    def create_memory_pools(self) -> Dict[str, Any]:
        """Create optimized memory pools."""
        # Implementation: Memory pool creation
        
    def detect_memory_leaks(self) -> List[str]:
        """Detect potential memory leaks."""
        # Implementation: Leak detection
        
    def optimize_allocation_patterns(self) -> Dict[str, Any]:
        """Optimize memory allocation patterns."""
        # Implementation: Allocation optimization

class IOOptimizer:
    """I/O operation optimization."""
    
    def __init__(self):
        """Initialize the I/O optimizer."""
        self.connection_pools = {}
        self.batch_operations = {}
        self.logger = logging.getLogger(f"{__name__}.IOOptimizer")
        
    def optimize_file_operations(self) -> Dict[str, Any]:
        """Optimize file system operations."""
        # Implementation: File operation optimization
        
    def optimize_network_io(self) -> Dict[str, Any]:
        """Optimize network I/O operations."""
        # Implementation: Network optimization
        
    def implement_batching(self) -> Dict[str, Any]:
        """Implement I/O operation batching."""
        # Implementation: Batching implementation
        
    def optimize_connection_pools(self) -> Dict[str, Any]:
        """Optimize connection pool configurations."""
        # Implementation: Connection pool optimization
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Integrate with Task 3.1** performance framework
3. **Add comprehensive type hints** for all functions
4. **Include detailed docstrings** explaining each method
5. **Handle edge cases** and error conditions gracefully
6. **Add logging** for debugging and monitoring
7. **Create unit tests** covering all methods
8. **Ensure no cross-file dependencies** within this task

---

## TASK 3.3: VALIDATION FRAMEWORK

**ASSIGNED FILE**: `chunker/validation/validation_framework.py`
**SUB-AGENT**: Validation Framework Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: Task 3.1 (Performance Core) must be complete

### FILE STRUCTURE TO CREATE:
```python
# chunker/validation/validation_framework.py

from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
import logging
import time
import json
import threading
from concurrent.futures import ThreadPoolExecutor

from ..performance.core.performance_framework import PerformanceManager, PerformanceProfile

logger = logging.getLogger(__name__)

class ValidationManager:
    """Main validation orchestration and coordination."""
    
    def __init__(self):
        """Initialize the validation manager."""
        self.performance_validator = PerformanceValidator()
        self.load_tester = LoadTester()
        self.regression_tester = RegressionTester()
        self.logger = logging.getLogger(f"{__name__}.ValidationManager")
        
    def run_full_validation(self) -> Dict[str, Any]:
        """Run complete validation suite."""
        # Implementation: Full validation execution
        
    def validate_performance(self) -> Dict[str, Any]:
        """Validate system performance."""
        # Implementation: Performance validation
        
    def run_load_tests(self) -> Dict[str, Any]:
        """Execute comprehensive load testing."""
        # Implementation: Load testing
        
    def run_regression_tests(self) -> Dict[str, Any]:
        """Execute regression testing."""
        # Implementation: Regression testing
        
    def generate_validation_report(self) -> Dict[str, Any]:
        """Generate comprehensive validation report."""
        # Implementation: Report generation

class PerformanceValidator:
    """Performance benchmark validation and testing."""
    
    def __init__(self):
        """Initialize the performance validator."""
        self.performance_manager = PerformanceManager()
        self.benchmarks = {}
        self.sla_requirements = {}
        self.logger = logging.getLogger(f"{__name__}.PerformanceValidator")
        
    def validate_performance_benchmarks(self) -> Dict[str, Any]:
        """Validate performance against benchmarks."""
        # Implementation: Benchmark validation
        
    def validate_performance_sla(self) -> Dict[str, Any]:
        """Validate performance against SLA requirements."""
        # Implementation: SLA validation
        
    def detect_performance_regressions(self) -> List[Dict[str, Any]]:
        """Detect performance regressions."""
        # Implementation: Regression detection
        
    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate performance validation report."""
        # Implementation: Performance reporting

class LoadTester:
    """Comprehensive load testing and stress testing."""
    
    def __init__(self):
        """Initialize the load tester."""
        self.test_scenarios = {}
        self.results_store = {}
        self.logger = logging.getLogger(f"{__name__}.LoadTester")
        
    def run_load_test(self, scenario: str, load_level: int) -> Dict[str, Any]:
        """Run a specific load test scenario."""
        # Implementation: Load test execution
        
    def run_stress_test(self, scenario: str) -> Dict[str, Any]:
        """Run stress testing to failure point."""
        # Implementation: Stress testing
        
    def measure_performance_under_load(self, load_level: int) -> Dict[str, Any]:
        """Measure performance under specific load levels."""
        # Implementation: Load performance measurement
        
    def generate_load_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive load test report."""
        # Implementation: Load test reporting

class RegressionTester:
    """Automated regression testing and change impact assessment."""
    
    def __init__(self):
        """Initialize the regression tester."""
        self.baseline_metrics = {}
        self.change_impact = {}
        self.logger = logging.getLogger(f"{__name__}.RegressionTester")
        
    def establish_baseline(self) -> Dict[str, Any]:
        """Establish performance baseline."""
        # Implementation: Baseline establishment
        
    def detect_regressions(self) -> List[Dict[str, Any]]:
        """Detect performance regressions from baseline."""
        # Implementation: Regression detection
        
    def assess_change_impact(self, changes: List[str]) -> Dict[str, Any]:
        """Assess impact of specific changes."""
        # Implementation: Change impact assessment
        
    def prevent_regressions(self) -> Dict[str, Any]:
        """Implement regression prevention measures."""
        # Implementation: Regression prevention
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Integrate with Task 3.1** performance framework
3. **Add comprehensive type hints** for all functions
4. **Include detailed docstrings** explaining each method
5. **Handle edge cases** and error conditions gracefully
6. **Add logging** for debugging and monitoring
7. **Create unit tests** covering all methods
8. **Ensure no cross-file dependencies** within this task

---

## TASK 3.4: PRODUCTION DEPLOYMENT

**ASSIGNED FILE**: `chunker/deployment/production_deployer.py`
**SUB-AGENT**: Production Deployment Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: Task 3.1 (Performance Core) must be complete

### FILE STRUCTURE TO CREATE:
```python
# chunker/deployment/production_deployer.py

from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
import logging
import time
import json
import subprocess
import requests

from ..performance.core.performance_framework import PerformanceManager

logger = logging.getLogger(__name__)

class ProductionDeployer:
    """Main deployment orchestration and automation."""
    
    def __init__(self):
        """Initialize the production deployer."""
        self.deployment_automation = DeploymentAutomation()
        self.health_checker = HealthChecker()
        self.rollback_manager = RollbackManager()
        self.logger = logging.getLogger(f"{__name__}.ProductionDeployer")
        
    def deploy_to_production(self, version: str) -> Dict[str, Any]:
        """Execute production deployment."""
        # Implementation: Production deployment
        
    def validate_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """Validate successful deployment."""
        # Implementation: Deployment validation
        
    def monitor_deployment_health(self, deployment_id: str) -> Dict[str, Any]:
        """Monitor deployment health post-deployment."""
        # Implementation: Health monitoring
        
    def execute_rollback(self, deployment_id: str) -> Dict[str, Any]:
        """Execute rollback if needed."""
        # Implementation: Rollback execution

class DeploymentAutomation:
    """Automated deployment pipelines and configuration management."""
    
    def __init__(self):
        """Initialize the deployment automation."""
        self.deployment_configs = {}
        self.environment_configs = {}
        self.logger = logging.getLogger(f"{__name__}.DeploymentAutomation")
        
    def create_deployment_pipeline(self, config: Dict[str, Any]) -> str:
        """Create automated deployment pipeline."""
        # Implementation: Pipeline creation
        
    def execute_deployment(self, pipeline_id: str) -> Dict[str, Any]:
        """Execute deployment pipeline."""
        # Implementation: Pipeline execution
        
    def manage_configurations(self, environment: str) -> Dict[str, Any]:
        """Manage environment-specific configurations."""
        # Implementation: Configuration management
        
    def provision_environment(self, environment: str) -> Dict[str, Any]:
        """Provision deployment environment."""
        # Implementation: Environment provisioning

class HealthChecker:
    """Comprehensive health monitoring and validation."""
    
    def __init__(self):
        """Initialize the health checker."""
        self.health_checks = {}
        self.alert_manager = AlertManager()
        self.logger = logging.getLogger(f"{__name__}.HealthChecker")
        
    def run_health_checks(self) -> Dict[str, Any]:
        """Run comprehensive health checks."""
        # Implementation: Health check execution
        
    def check_dependency_health(self) -> Dict[str, Any]:
        """Check health of system dependencies."""
        # Implementation: Dependency health checking
        
    def assess_performance_health(self) -> Dict[str, Any]:
        """Assess overall system performance health."""
        # Implementation: Performance health assessment
        
    def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report."""
        # Implementation: Health reporting

class RollbackManager:
    """Automated rollback capabilities and recovery management."""
    
    def __init__(self):
        """Initialize the rollback manager."""
        self.rollback_strategies = {}
        self.recovery_procedures = {}
        self.logger = logging.getLogger(f"{__name__}.RollbackManager")
        
    def execute_rollback(self, deployment_id: str) -> Dict[str, Any]:
        """Execute automated rollback."""
        # Implementation: Rollback execution
        
    def validate_rollback(self, rollback_id: str) -> Dict[str, Any]:
        """Validate successful rollback."""
        # Implementation: Rollback validation
        
    def execute_recovery(self, recovery_type: str) -> Dict[str, Any]:
        """Execute recovery procedures."""
        # Implementation: Recovery execution
        
    def generate_rollback_report(self, rollback_id: str) -> Dict[str, Any]:
        """Generate rollback execution report."""
        # Implementation: Rollback reporting

class AlertManager:
    """Alert generation and management system."""
    
    def __init__(self):
        """Initialize the alert manager."""
        self.alert_channels = {}
        self.alert_rules = {}
        self.logger = logging.getLogger(f"{__name__}.AlertManager")
        
    def generate_alert(self, alert_type: str, message: str) -> str:
        """Generate and send alert."""
        # Implementation: Alert generation
        
    def manage_alert_channels(self) -> Dict[str, Any]:
        """Manage alert notification channels."""
        # Implementation: Channel management
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Integrate with Task 3.1** performance framework
3. **Add comprehensive type hints** for all functions
4. **Include detailed docstrings** explaining each method
5. **Handle edge cases** and error conditions gracefully
6. **Add logging** for debugging and monitoring
7. **Create unit tests** covering all methods
8. **Ensure no cross-file dependencies** within this task

---

## TASK 3.5: MONITORING & OBSERVABILITY

**ASSIGNED FILE**: `chunker/monitoring/observability_system.py`
**SUB-AGENT**: Monitoring & Observability Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: Task 3.1 (Performance Core) must be complete

### FILE STRUCTURE TO CREATE:
```python
# chunker/monitoring/observability_system.py

from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
import logging
import time
import json
import threading
from datetime import datetime

from ..performance.core.performance_framework import PerformanceManager

logger = logging.getLogger(__name__)

class ObservabilityManager:
    """Main observability orchestration and coordination."""
    
    def __init__(self):
        """Initialize the observability manager."""
        self.metrics_collector = MetricsCollector()
        self.log_aggregator = LogAggregator()
        self.distributed_tracer = DistributedTracer()
        self.logger = logging.getLogger(f"{__name__}.ObservabilityManager")
        
    def initialize_observability(self) -> Dict[str, Any]:
        """Initialize complete observability system."""
        # Implementation: System initialization
        
    def collect_observability_data(self) -> Dict[str, Any]:
        """Collect comprehensive observability data."""
        # Implementation: Data collection
        
    def correlate_data(self) -> Dict[str, Any]:
        """Correlate metrics, logs, and traces."""
        # Implementation: Data correlation
        
    def generate_observability_report(self) -> Dict[str, Any]:
        """Generate comprehensive observability report."""
        # Implementation: Report generation

class MetricsCollector:
    """Comprehensive metrics collection and management."""
    
    def __init__(self):
        """Initialize the metrics collector."""
        self.metrics_store = {}
        self.custom_metrics = {}
        self.collection_interval = 1.0
        self.logger = logging.getLogger(f"{__name__}.MetricsCollector")
        
    def collect_system_metrics(self) -> Dict[str, Any]:
        """Collect system-wide metrics."""
        # Implementation: System metrics collection
        
    def define_custom_metric(self, name: str, metric_type: str) -> bool:
        """Define custom metrics for collection."""
        # Implementation: Custom metric definition
        
    def collect_custom_metrics(self) -> Dict[str, Any]:
        """Collect custom-defined metrics."""
        # Implementation: Custom metrics collection
        
    def aggregate_metrics(self) -> Dict[str, Any]:
        """Aggregate collected metrics."""
        # Implementation: Metrics aggregation

class LogAggregator:
    """Centralized log collection and aggregation."""
    
    def __init__(self):
        """Initialize the log aggregator."""
        self.log_sources = {}
        self.log_parser = LogParser()
        self.log_store = {}
        self.logger = logging.getLogger(f"{__name__}.LogAggregator")
        
    def collect_logs(self) -> Dict[str, Any]:
        """Collect logs from all sources."""
        # Implementation: Log collection
        
    def parse_logs(self, logs: List[str]) -> List[Dict[str, Any]]:
        """Parse and structure log entries."""
        # Implementation: Log parsing
        
    def enrich_logs(self, parsed_logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich logs with additional context."""
        # Implementation: Log enrichment
        
    def correlate_logs(self) -> Dict[str, Any]:
        """Correlate logs with other observability data."""
        # Implementation: Log correlation

class DistributedTracer:
    """Distributed tracing implementation and analysis."""
    
    def __init__(self):
        """Initialize the distributed tracer."""
        self.trace_store = {}
        self.trace_correlator = TraceCorrelator()
        self.logger = logging.getLogger(f"{__name__}.DistributedTracer")
        
    def start_trace(self, trace_name: str) -> str:
        """Start a new distributed trace."""
        # Implementation: Trace start
        
    def add_trace_span(self, trace_id: str, span_name: str) -> str:
        """Add a span to an existing trace."""
        # Implementation: Span addition
        
    def end_trace(self, trace_id: str) -> Dict[str, Any]:
        """End a distributed trace."""
        # Implementation: Trace completion
        
    def analyze_traces(self) -> Dict[str, Any]:
        """Analyze collected traces for insights."""
        # Implementation: Trace analysis

class LogParser:
    """Log parsing and structuring utilities."""
    
    @staticmethod
    def parse_log_entry(log_entry: str) -> Dict[str, Any]:
        """Parse a single log entry."""
        # Implementation: Log entry parsing
        
    @staticmethod
    def extract_timestamp(log_entry: str) -> Optional[datetime]:
        """Extract timestamp from log entry."""
        # Implementation: Timestamp extraction
        
    @staticmethod
    def extract_log_level(log_entry: str) -> Optional[str]:
        """Extract log level from log entry."""
        # Implementation: Log level extraction

class TraceCorrelator:
    """Trace correlation and analysis utilities."""
    
    @staticmethod
    def correlate_traces(traces: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Correlate multiple traces."""
        # Implementation: Trace correlation
        
    @staticmethod
    def identify_bottlenecks(trace: Dict[str, Any]) -> List[str]:
        """Identify performance bottlenecks in traces."""
        # Implementation: Bottleneck identification
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Integrate with Task 3.1** performance framework
3. **Add comprehensive type hints** for all functions
4. **Include detailed docstrings** explaining each method
5. **Handle edge cases** and error conditions gracefully
6. **Add logging** for debugging and monitoring
7. **Create unit tests** covering all methods
8. **Ensure no cross-file dependencies** within this task

---

## TASK 3.6: FINAL VALIDATION & INTEGRATION

**ASSIGNED FILE**: `chunker/validation/final_validation_tester.py`
**SUB-AGENT**: Final Validation Specialist
**IMPLEMENTATION DEADLINE**: Complete within assigned timeframe
**DEPENDENCIES**: All other tasks (3.1, 3.2, 3.3, 3.4, 3.5) must be complete

### FILE STRUCTURE TO CREATE:
```python
# chunker/validation/final_validation_tester.py

from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
import logging
import time
import json

# Import from all other tasks
from ..performance.core.performance_framework import PerformanceManager
from ..performance.optimization.system_optimizer import SystemOptimizer
from ..validation.validation_framework import ValidationManager
from ..deployment.production_deployer import ProductionDeployer
from ..monitoring.observability_system import ObservabilityManager

logger = logging.getLogger(__name__)

class FinalValidationTester:
    """Complete Phase 3 system validation and integration testing."""
    
    def __init__(self):
        """Initialize the final validation tester."""
        self.system_integration_tester = SystemIntegrationTester()
        self.production_readiness_validator = ProductionReadinessValidator()
        self.logger = logging.getLogger(__name__)
        
    def run_complete_validation(self) -> Dict[str, Any]:
        """Run complete Phase 3 validation suite."""
        # Implementation: Complete validation execution
        
    def validate_system_integration(self) -> Dict[str, Any]:
        """Validate system-wide integration."""
        # Implementation: System integration validation
        
    def validate_production_readiness(self) -> Dict[str, Any]:
        """Validate production deployment readiness."""
        # Implementation: Production readiness validation
        
    def generate_final_report(self) -> Dict[str, Any]:
        """Generate comprehensive final validation report."""
        # Implementation: Final report generation

class SystemIntegrationTester:
    """System-wide integration testing and validation."""
    
    def __init__(self):
        """Initialize the system integration tester."""
        self.performance_manager = PerformanceManager()
        self.system_optimizer = SystemOptimizer()
        self.validation_manager = ValidationManager()
        self.production_deployer = ProductionDeployer()
        self.observability_manager = ObservabilityManager()
        
    def test_component_integration(self) -> Dict[str, Any]:
        """Test integration between all components."""
        # Implementation: Component integration testing
        
    def test_performance_integration(self) -> Dict[str, Any]:
        """Test performance optimization integration."""
        # Implementation: Performance integration testing
        
    def test_validation_integration(self) -> Dict[str, Any]:
        """Test validation framework integration."""
        # Implementation: Validation integration testing
        
    def test_deployment_integration(self) -> Dict[str, Any]:
        """Test deployment system integration."""
        # Implementation: Deployment integration testing
        
    def test_observability_integration(self) -> Dict[str, Any]:
        """Test observability system integration."""
        # Implementation: Observability integration testing

class ProductionReadinessValidator:
    """Production deployment readiness validation."""
    
    def __init__(self):
        """Initialize the production readiness validator."""
        self.readiness_checks = {}
        self.compliance_validator = ComplianceValidator()
        self.logger = logging.getLogger(f"{__name__}.ProductionReadinessValidator")
        
    def validate_deployment_readiness(self) -> Dict[str, Any]:
        """Validate complete deployment readiness."""
        # Implementation: Deployment readiness validation
        
    def validate_performance_requirements(self) -> Dict[str, Any]:
        """Validate performance requirements are met."""
        # Implementation: Performance requirement validation
        
    def validate_security_compliance(self) -> Dict[str, Any]:
        """Validate security and compliance requirements."""
        # Implementation: Security compliance validation
        
    def confirm_production_readiness(self) -> bool:
        """Confirm system is ready for production deployment."""
        # Implementation: Production readiness confirmation

class ComplianceValidator:
    """Security and compliance validation utilities."""
    
    @staticmethod
    def validate_security_requirements() -> Dict[str, Any]:
        """Validate security requirements."""
        # Implementation: Security validation
        
    @staticmethod
    def validate_compliance_standards() -> Dict[str, Any]:
        """Validate compliance standards."""
        # Implementation: Compliance validation

def run_complete_phase3_validation() -> Dict[str, Any]:
    """Run complete Phase 3 validation suite."""
    # Implementation: Complete validation execution
```

### IMPLEMENTATION REQUIREMENTS:
1. **Complete all classes and methods** with full implementation
2. **Integrate with all other tasks** (import all components)
3. **Add comprehensive type hints** for all functions
4. **Include detailed docstrings** explaining each method
5. **Handle edge cases** and error conditions gracefully
6. **Add logging** for debugging and monitoring
7. **Create unit tests** covering all methods
8. **Ensure comprehensive testing** of all Phase 3 components

---

## SUB-AGENT ASSIGNMENT INSTRUCTIONS

### FOR EACH SUB-AGENT:

1. **READ THE ENTIRE TASK DESCRIPTION** before starting
2. **ONLY TOUCH THE ASSIGNED FILE** - no other files
3. **IMPLEMENT ALL METHODS** completely with full functionality
4. **ADD COMPREHENSIVE TYPE HINTS** for all functions
5. **INCLUDE DETAILED DOCSTRINGS** explaining each method
6. **HANDLE EDGE CASES** and error conditions gracefully
7. **ADD LOGGING** for debugging and monitoring
8. **CREATE UNIT TESTS** with 95%+ coverage
9. **FOLLOW PYTHON CODING STANDARDS** (PEP 8, type hints, etc.)
10. **ENSURE PRODUCTION-READY CODE** - no prototypes or stubs

### EXECUTION ORDER:

**IMPORTANT**: These tasks have specific dependencies:

1. **Task 3.1**: Must complete first (performance core framework)
2. **Tasks 3.2, 3.3, 3.4, 3.5**: Can start simultaneously after Task 3.1 completion
3. **Task 3.6**: Must wait for ALL other tasks completion

### SUB-AGENT PROMPT TEMPLATE:

```
You are assigned to implement [TASK_NAME] for Phase 3.

YOUR FILE: [FILE_PATH]
YOUR TASK: [TASK_DESCRIPTION]
DEPENDENCIES: [LIST OF DEPENDENCIES]
PHASE 3 ALIGNMENT: [SPECIFIC ALIGNMENT REQUIREMENTS]

REQUIREMENTS:
- Implement ALL methods in the class structure provided
- Add comprehensive type hints and docstrings
- Handle edge cases and error conditions
- Include logging and error handling
- Create unit tests with 95%+ coverage
- ONLY touch the assigned file
- Ensure compatibility with [DEPENDENT_TASKS] if applicable
- Maintain production-ready code quality

DO NOT:
- Modify any other files
- Skip any methods
- Leave TODO comments
- Create incomplete implementations
- Deviate from Phase 3 specification requirements

START IMPLEMENTATION NOW.
```

---

## COORDINATION & REPORTING

### SUB-AGENT MANAGER RESPONSIBILITIES:

1. **EXECUTE CORE TASK FIRST**: Start Task 3.1 (Performance Core Framework) immediately
2. **WAIT FOR CORE COMPLETION**: Ensure Task 3.1 is complete before starting other tasks
3. **EXECUTE OPTIMIZATION COMPONENTS**: Start Tasks 3.2, 3.3, 3.4, 3.5 simultaneously after Task 3.1 completion
4. **EXECUTE FINAL VALIDATION**: Start Task 3.6 after all other tasks complete
5. **COLLECT RESULTS**: Gather completed implementations from each sub-agent
6. **VALIDATE COMPLETION**: Ensure all tasks are fully implemented
7. **VERIFY PHASE 3 READINESS**: Confirm system is ready for production deployment
8. **REPORT SUMMARY**: Provide summary of all completed work

### COMPLETION CRITERIA:

Each sub-agent task is complete when:
- ✅ All methods are fully implemented
- ✅ Type hints are complete and correct
- ✅ Docstrings are comprehensive and clear
- ✅ Error handling is robust and graceful
- ✅ Logging is implemented throughout
- ✅ Unit tests achieve 95%+ coverage
- ✅ Code follows Python standards
- ✅ No TODO or incomplete code remains
- ✅ Dependencies are properly integrated
- ✅ Production-ready quality achieved

### FINAL REPORT FORMAT:

```
PHASE 3 COMPLETION REPORT
=========================

TASK 3.1 (Performance Core): [STATUS] - [SUB-AGENT NAME]
- File: chunker/performance/core/performance_framework.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Production readiness: [STATUS]
- Issues/notes: [ANY]

TASK 3.2 (System Optimization): [STATUS] - [SUB-AGENT NAME]
- File: chunker/performance/optimization/system_optimizer.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Optimization features: [LIST]
- Production readiness: [STATUS]
- Issues/notes: [ANY]

TASK 3.3 (Validation Framework): [STATUS] - [SUB-AGENT NAME]
- File: chunker/validation/validation_framework.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Validation capabilities: [LIST]
- Production readiness: [STATUS]
- Issues/notes: [ANY]

TASK 3.4 (Production Deployment): [STATUS] - [SUB-AGENT NAME]
- File: chunker/deployment/production_deployer.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Deployment features: [LIST]
- Production readiness: [STATUS]
- Issues/notes: [ANY]

TASK 3.5 (Monitoring & Observability): [STATUS] - [SUB-AGENT NAME]
- File: chunker/monitoring/observability_system.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Observability features: [LIST]
- Production readiness: [STATUS]
- Issues/notes: [ANY]

TASK 3.6 (Final Validation): [STATUS] - [SUB-AGENT NAME]
- File: chunker/validation/final_validation_tester.py
- Methods implemented: [LIST]
- Test coverage: [PERCENTAGE]
- Integration tests: [LIST]
- Production readiness: [STATUS]
- Issues/notes: [ANY]

OVERALL STATUS: [COMPLETE/INCOMPLETE]
PHASE 3 READINESS: [READY/NOT READY]
NEXT STEPS: [PRODUCTION DEPLOYMENT]
```

---

## IMPORTANT NOTES

### FILE BOUNDARIES:
- **EACH SUB-AGENT TOUCHES EXACTLY ONE FILE**
- **NO CROSS-FILE DEPENDENCIES** within individual tasks
- **ALL IMPORTS MUST BE STANDARD LIBRARY** or from completed tasks
- **NO NEW DEPENDENCIES** can be added

### DEPENDENCY MANAGEMENT:
- **3.1 (Performance Core)**: No dependencies - can start immediately
- **3.2, 3.3, 3.4, 3.5**: Depend on Task 3.1 completion
- **3.6 (Final Validation)**: Depends on ALL other tasks completion

### QUALITY STANDARDS:
- **FULL IMPLEMENTATION** - no stubs or placeholders
- **PRODUCTION-READY CODE** - not prototype quality
- **COMPREHENSIVE TESTING** - 95%+ coverage required
- **ERROR HANDLING** - graceful degradation for all edge cases
- **LOGGING** - meaningful debug and info messages
- **PHASE 3 COMPLIANCE** - specification requirements met

### COORDINATION:
- **SEQUENTIAL EXECUTION** - Task 3.1 must complete first
- **PARALLEL EXECUTION** - Tasks 3.2-3.5 can start simultaneously after Task 3.1
- **DEPENDENCY VALIDATION** - ensure previous tasks complete before starting dependent tasks
- **MANAGER OVERSIGHT** - you coordinate and ensure proper execution order
- **QUALITY GATES** - validate completion before proceeding to dependent tasks
- **PRODUCTION READINESS** - confirm system meets all quality requirements

---

## EXECUTION COMMAND

**COPY AND PASTE THIS ENTIRE PROMPT** into your sub-agent manager system to begin execution of Phase 3 tasks.

**EXPECTED DURATION**: 3 weeks with parallel execution
**EXPECTED OUTCOME**: Complete Phase 3 system with performance optimization and validation
**NEXT PHASE**: Production deployment and real-world usage

## PHASE 3 READINESS VALIDATION

### FINAL VALIDATION CHECKLIST:

Before marking Phase 3 complete, verify:

1. **Performance Core**: ✅ Fully functional and robust
2. **System Optimization**: ✅ CPU, memory, and I/O optimization operational
3. **Validation Framework**: ✅ Comprehensive testing and validation
4. **Production Deployment**: ✅ Deployment automation and health monitoring
5. **Monitoring & Observability**: ✅ Complete system visibility
6. **Final Validation**: ✅ Complete system integration and testing
7. **Production Readiness**: ✅ System ready for production deployment
8. **Quality Standards**: ✅ 95%+ test coverage achieved
9. **Performance Optimization**: ✅ System-wide optimization validated
10. **Deployment Readiness**: ✅ Production deployment capabilities confirmed

**START EXECUTION NOW** with Task 3.1 (Performance Core Framework), then proceed with Tasks 3.2-3.5 in parallel after completion, and finally Task 3.6 for final validation and integration testing.
