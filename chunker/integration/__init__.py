"""Core System Integration for treesitter-chunker - Task 1.9.

This package provides the core system integration that unifies Phase 1.7 (Error Handling & User Guidance)
with Phase 1.8 (Grammar Management & CLI Tools) and Phase 1.9 (Performance Optimization & Production Validation)
into a production-ready system.

The integration provides:
- SystemIntegrator: Unified entry point for the complete grammar management system
- PerformanceOptimizer: Comprehensive performance optimization with real-time monitoring
- UserExperienceManager: Enhanced user experience and interaction management
- ProductionValidator: Comprehensive production validation and deployment readiness assessment
- Component orchestration with proper dependency management
- Thread-safe singleton pattern with lifecycle management
- Health monitoring and diagnostics for all system components
- Graceful degradation when components are unavailable
- Production-ready error handling and logging

Key Components:
- SystemIntegrator: Main orchestrator class
- PerformanceOptimizer: Performance optimization orchestrator
- UserExperienceManager: User experience enhancement orchestrator
- ProductionValidator: Production validation orchestrator
- ComponentHealth: Health monitoring and diagnostics
- LifecycleManager: Component initialization and shutdown
- ErrorProcessor: Unified error processing pipeline
- GrammarProcessor: Unified grammar management pipeline
- CacheOptimizer: Multi-level caching with intelligent invalidation
- MemoryOptimizer: Memory management and garbage collection tuning
- ConcurrencyOptimizer: Thread pool and async operation optimization
- IOOptimizer: I/O operation batching and connection pooling
- QueryOptimizer: SQL query optimization and index management
- PerformanceMonitor: Real-time performance monitoring and alerting
- ValidationComponents: Comprehensive validation for dependencies, configuration, security, performance, and integration

Phase Integration:
- Phase 1.7: Error handling, classification, compatibility detection, syntax analysis, user guidance
- Phase 1.8: Grammar management, CLI tools, registry, installation, validation
- Phase 1.9: Performance optimization, user experience, production validation, deployment readiness

The system is designed for production use with comprehensive monitoring, logging, graceful error handling,
auto-optimization capabilities, and complete deployment validation that ensures system readiness.
"""

import logging

from .core_integration import (
    ComponentHealth,
    ComponentInitializationError,
    ComponentType,
    HealthStatus,
    LifecycleManager,
    SystemDegradationError,
    SystemHealth,
    SystemInitializationError,
    SystemIntegrator,
    get_system_health,
    get_system_integrator,
    initialize_treesitter_system,
    process_grammar_error,
)
from .performance_optimizer import (
    AlertSeverity,
    CacheOptimizer,
    ConcurrencyOptimizer,
    IOOptimizer,
    LRUCache,
    MemoryOptimizer,
    MemoryPool,
    OptimizationLevel,
    PerformanceAlert,
    PerformanceMetric,
    PerformanceMonitor,
    PerformanceOptimizer,
    QueryOptimizer,
    create_performance_optimizer,
    get_treesitter_performance_report,
    optimize_treesitter_performance,
)

try:
    from .user_experience import FeedbackLevel, InteractionMode, UserExperienceManager

    USER_EXPERIENCE_AVAILABLE = True
except ImportError:
    UserExperienceManager = None
    InteractionMode = None
    FeedbackLevel = None
    USER_EXPERIENCE_AVAILABLE = False

from .production_validator import (
    ConfigurationValidator,
    CriticalPathValidator,
    DependencyValidator,
    DeploymentStage,
    IntegrationValidator,
    PerformanceValidator,
    ProductionValidator,
    SecurityValidator,
    ValidationCategory,
    ValidationReport,
    ValidationResult,
    ValidationSeverity,
    validate_production_readiness,
)

# Final Integration Testing System
try:
    from .final_integration_tests import (
        FinalIntegrationTester,
        ScenarioTestConfig,
        StressTestConfig,
        TestCategory,
        TestReport,
        TestResult,
        TestSeverity,
        TestStatus,
        TestSuite,
        create_comprehensive_test_scenarios,
        get_integration_test_coverage,
        run_final_integration_tests,
        run_scenario_tests,
        run_stress_tests,
    )

    FINAL_INTEGRATION_TESTS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Final integration tests not available: {e}")
    FinalIntegrationTester = None
    TestSeverity = None
    TestCategory = None
    TestStatus = None
    TestResult = None
    TestSuite = None
    StressTestConfig = None
    ScenarioTestConfig = None
    TestReport = None
    run_final_integration_tests = None
    run_stress_tests = None
    run_scenario_tests = None
    get_integration_test_coverage = None
    create_comprehensive_test_scenarios = None
    FINAL_INTEGRATION_TESTS_AVAILABLE = False

__all__ = [
    "FINAL_INTEGRATION_TESTS_AVAILABLE",
    "USER_EXPERIENCE_AVAILABLE",
    "AlertSeverity",
    "CacheOptimizer",
    "ComponentHealth",
    "ComponentInitializationError",
    "ComponentType",
    "ConcurrencyOptimizer",
    "ConfigurationValidator",
    "CriticalPathValidator",
    "DependencyValidator",
    "DeploymentStage",
    "FeedbackLevel",
    # Final Integration Testing
    "FinalIntegrationTester",
    "HealthStatus",
    "IOOptimizer",
    "IntegrationValidator",
    "InteractionMode",
    "LRUCache",
    "LifecycleManager",
    "MemoryOptimizer",
    "MemoryPool",
    "OptimizationLevel",
    "PerformanceAlert",
    "PerformanceMetric",
    "PerformanceMonitor",
    # Performance Optimization
    "PerformanceOptimizer",
    "PerformanceValidator",
    # Production Validation
    "ProductionValidator",
    "QueryOptimizer",
    "ScenarioTestConfig",
    "SecurityValidator",
    "StressTestConfig",
    "SystemDegradationError",
    "SystemHealth",
    "SystemInitializationError",
    # Core Integration
    "SystemIntegrator",
    "TestCategory",
    "TestReport",
    "TestResult",
    "TestSeverity",
    "TestStatus",
    "TestSuite",
    # User Experience (if available)
    "UserExperienceManager",
    "ValidationCategory",
    "ValidationReport",
    "ValidationResult",
    "ValidationSeverity",
    "create_comprehensive_test_scenarios",
    "create_performance_optimizer",
    "get_integration_test_coverage",
    "get_system_health",
    "get_system_integrator",
    "get_treesitter_performance_report",
    "initialize_treesitter_system",
    "optimize_treesitter_performance",
    "process_grammar_error",
    "run_final_integration_tests",
    "run_scenario_tests",
    "run_stress_tests",
    "validate_production_readiness",
]

__version__ = "1.0.0"
__author__ = "treesitter-chunker team"
