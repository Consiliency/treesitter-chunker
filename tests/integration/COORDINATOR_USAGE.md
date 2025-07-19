# Integration Test Coordinator Usage Guide

The Integration Test Coordinator manages Phase 7 integration testing across multiple parallel worktrees.

## Overview

The coordinator provides:
- Automated worktree setup and verification
- Test scenario management with dependency resolution
- Parallel test execution across worktrees
- Comprehensive reporting and resource tracking
- Cleanup and error handling

## Quick Start

### 1. Basic Usage

Run all integration tests:
```bash
python tests/integration/run_coordinator.py
```

### 2. Setup Worktrees

Set up missing worktrees automatically:
```bash
python tests/integration/run_coordinator.py --setup-worktrees --pull-coordinator
```

### 3. Filter Tests

Run only specific tests:
```bash
# By tag
python tests/integration/run_coordinator.py --filter-tag critical --filter-tag parallel

# By worktree
python tests/integration/run_coordinator.py --filter-worktree parallel-errors

# Dry run to see what would execute
python tests/integration/run_coordinator.py --filter-tag critical --dry-run
```

### 4. Control Execution

Adjust parallel execution:
```bash
# Sequential execution
python tests/integration/run_coordinator.py --no-parallel

# More workers
python tests/integration/run_coordinator.py --workers 8
```

## Command Line Options

- `--base-path PATH`: Base directory for worktrees (default: ~/code/treesitter-chunker-worktrees)
- `--main-repo PATH`: Path to main repository (default: ~/code/treesitter-chunker)
- `--scenarios FILE`: Path to scenarios configuration (default: scenarios.json)
- `--setup-worktrees`: Automatically set up missing worktrees
- `--pull-coordinator`: Pull coordinator changes in all worktrees
- `--parallel/--no-parallel`: Enable/disable parallel execution
- `--workers N`: Number of parallel workers (default: 4)
- `--filter-tag TAG`: Only run scenarios with specified tag(s)
- `--filter-worktree WT`: Only run scenarios in specified worktree(s)
- `--report FILE`: Path to save JSON report (default: integration_report.json)
- `--cleanup`: Clean up worktrees after testing
- `--dry-run`: Show what would run without executing

## Scenario Configuration

Test scenarios are defined in `scenarios.json`:

```json
{
  "scenarios": [
    {
      "name": "unique_scenario_name",
      "description": "What this test verifies",
      "worktree": "worktree-name",
      "test_file": "tests/test_file.py::test_function",
      "dependencies": ["other_scenario"],  // Optional
      "timeout": 120,                      // Seconds
      "tags": ["parallel", "critical"]     // For filtering
    }
  ]
}
```

## Programmatic Usage

Use the coordinator in Python scripts:

```python
from tests.integration.coordinator import IntegrationCoordinator, TestScenario

# Initialize
coordinator = IntegrationCoordinator(
    base_path=Path("~/code/treesitter-chunker-worktrees"),
    main_repo_path=Path("~/code/treesitter-chunker")
)

# Register scenarios
scenario = TestScenario(
    name="my_test",
    description="Test description",
    worktree="test-worktree",
    test_file="tests/test_file.py"
)
coordinator.register_scenario(scenario)

# Or load from config
coordinator.register_scenarios_from_config("scenarios.json")

# Run tests
coordinator.run_all_scenarios(parallel=True, max_workers=4)

# Get report
report = coordinator.generate_report()
print(f"Passed: {report['summary']['passed']}/{report['summary']['total']}")
```

## Test Reports

Reports include:
- Summary statistics (passed/failed/skipped/errors)
- Results grouped by worktree
- Detailed failure information
- Resource leak detection
- Execution timing

Example report structure:
```json
{
  "summary": {
    "total": 20,
    "passed": 18,
    "failed": 2,
    "skipped": 0,
    "errors": 0,
    "duration": 245.3,
    "success_rate": 90.0
  },
  "by_worktree": {
    "parallel-errors": {
      "total": 5,
      "passed": 4,
      "failed": 1
    }
  },
  "failures": [...],
  "resource_leaks": [...],
  "timestamp": "2024-01-20T10:30:00"
}
```

## Worktree Management

The coordinator handles:
- Worktree creation with proper branch names
- Virtual environment setup
- Dependency installation
- Grammar fetching and building
- Coordinator changes synchronization

Verify worktree setup:
```python
if coordinator.verify_worktree_setup("my-worktree"):
    print("Worktree ready")
else:
    coordinator.setup_worktree("my-worktree", "feature/test-branch")
```

## Dependency Management

Scenarios can depend on other scenarios:
- Dependencies must pass before dependent scenarios run
- Circular dependencies are detected and reported
- Failed dependencies cause dependent tests to be skipped

## Resource Tracking

All resources are tracked:
- Worktrees
- Test executions
- Process/thread resources

Check for leaks:
```python
report = coordinator.generate_report()
if report['resource_leaks']:
    print("Resource leaks detected!")
```

## Best Practices

1. **Always pull coordinator changes** before running tests in dependent worktrees
2. **Use tags** to organize and filter test scenarios
3. **Set appropriate timeouts** for long-running tests
4. **Check reports** for resource leaks and failures
5. **Clean up worktrees** when done to save disk space

## Troubleshooting

### Missing Worktree
```bash
# Automatically set up
python tests/integration/run_coordinator.py --setup-worktrees

# Or manually
cd ~/code/treesitter-chunker
git worktree add ../treesitter-chunker-worktrees/my-worktree -b feature/my-branch
```

### Coordinator Changes Not Found
```bash
# Pull latest coordinator changes
python tests/integration/run_coordinator.py --pull-coordinator
```

### Test Timeouts
Increase timeout in scenarios.json:
```json
{
  "timeout": 300  // 5 minutes
}
```

### Resource Leaks
Check report for leaked resources and ensure proper cleanup in tests.

## Integration with CI/CD

The coordinator can be integrated into CI/CD pipelines:

```yaml
# GitHub Actions example
- name: Run Integration Tests
  run: |
    python tests/integration/run_coordinator.py \
      --setup-worktrees \
      --pull-coordinator \
      --report integration_report.json
    
- name: Upload Report
  uses: actions/upload-artifact@v3
  with:
    name: integration-report
    path: integration_report.json
```