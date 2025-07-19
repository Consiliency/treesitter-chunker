"""Integration test coordinator for managing cross-worktree testing."""

import subprocess
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import threading
import queue

from .interfaces import ErrorPropagationMixin, ConfigChangeObserver, ResourceTracker


@dataclass
class TestScenario:
    """Definition of a test scenario."""
    name: str
    description: str
    worktree: str
    test_file: str
    dependencies: List[str] = field(default_factory=list)
    timeout: int = 300  # 5 minutes default
    retry_count: int = 0
    tags: List[str] = field(default_factory=list)
    

@dataclass
class TestResult:
    """Result from a test execution."""
    scenario: TestScenario
    status: str  # 'passed', 'failed', 'skipped', 'error'
    duration: float
    output: str
    error: Optional[str] = None
    retry_attempt: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


class IntegrationCoordinator(ErrorPropagationMixin):
    """Coordinates integration testing across multiple worktrees."""
    
    def __init__(self, base_path: Path, main_repo_path: Path):
        """Initialize the coordinator.
        
        Args:
            base_path: Path to the worktrees directory
            main_repo_path: Path to the main repository
        """
        self.base_path = Path(base_path)
        self.main_repo_path = Path(main_repo_path)
        self.scenarios: Dict[str, TestScenario] = {}
        self.results: List[TestResult] = []
        self.resource_tracker = ResourceTracker()
        self.config_observer = ConfigChangeObserver()
        self._execution_queue = queue.Queue()
        self._workers: List[threading.Thread] = []
        self._stop_event = threading.Event()
        
    def register_scenario(self, scenario: TestScenario) -> None:
        """Register a test scenario."""
        self.scenarios[scenario.name] = scenario
        
    def register_scenarios_from_config(self, config_file: Path) -> None:
        """Load test scenarios from a JSON configuration file."""
        with open(config_file) as f:
            config = json.load(f)
            
        for scenario_dict in config.get('scenarios', []):
            scenario = TestScenario(**scenario_dict)
            self.register_scenario(scenario)
            
    def verify_worktree_setup(self, worktree_name: str) -> bool:
        """Verify a worktree is properly set up.
        
        Returns:
            True if worktree is ready, False otherwise
        """
        worktree_path = self.base_path / worktree_name
        
        # Check worktree exists
        if not worktree_path.exists():
            return False
            
        # Check it's a git worktree
        git_dir = worktree_path / '.git'
        if not git_dir.exists():
            return False
            
        # Check virtual environment
        venv_path = worktree_path / '.venv'
        if not venv_path.exists():
            return False
            
        # Check grammars are built
        build_dir = worktree_path / 'build'
        if not build_dir.exists() or not any(build_dir.glob('*.so')):
            return False
            
        return True
        
    def setup_worktree(self, worktree_name: str, branch_name: str) -> bool:
        """Set up a new worktree.
        
        Returns:
            True if setup successful, False otherwise
        """
        worktree_path = self.base_path / worktree_name
        
        try:
            # Create worktree
            subprocess.run(
                ['git', 'worktree', 'add', str(worktree_path), '-b', branch_name],
                cwd=self.main_repo_path,
                check=True,
                capture_output=True
            )
            
            # Set up virtual environment
            subprocess.run(
                ['python', '-m', 'venv', '.venv'],
                cwd=worktree_path,
                check=True
            )
            
            # Install dependencies
            pip_path = worktree_path / '.venv' / 'bin' / 'pip'
            subprocess.run(
                [str(pip_path), 'install', '-e', '.[dev]'],
                cwd=worktree_path,
                check=True
            )
            
            # Fetch and build grammars
            python_path = worktree_path / '.venv' / 'bin' / 'python'
            subprocess.run(
                [str(python_path), 'scripts/fetch_grammars.py'],
                cwd=worktree_path,
                check=True
            )
            subprocess.run(
                [str(python_path), 'scripts/build_lib.py'],
                cwd=worktree_path,
                check=True
            )
            
            # Track worktree as resource
            self.resource_tracker.track_resource(
                module='coordinator',
                resource_type='worktree',
                resource_id=f'worktree_{worktree_name}'
            )
            
            return True
            
        except subprocess.CalledProcessError as e:
            error_context = self.capture_cross_module_error(
                source_module='coordinator.setup',
                target_module='coordinator.main',
                error=e
            )
            self.results.append(TestResult(
                scenario=TestScenario(name=f'setup_{worktree_name}', 
                                    description='Worktree setup',
                                    worktree=worktree_name,
                                    test_file=''),
                status='error',
                duration=0,
                output='',
                error=str(error_context)
            ))
            return False
            
    def pull_coordinator_changes(self, worktree_name: str) -> bool:
        """Pull integration coordinator changes into a worktree."""
        worktree_path = self.base_path / worktree_name
        
        try:
            # Fetch latest
            subprocess.run(
                ['git', 'fetch', 'origin'],
                cwd=worktree_path,
                check=True
            )
            
            # Pull coordinator branch
            subprocess.run(
                ['git', 'pull', 'origin', 'feature/integration-coordinator'],
                cwd=worktree_path,
                check=True
            )
            
            return True
            
        except subprocess.CalledProcessError:
            return False
            
    def run_scenario(self, scenario: TestScenario) -> TestResult:
        """Run a single test scenario."""
        worktree_path = self.base_path / scenario.worktree
        python_path = worktree_path / '.venv' / 'bin' / 'python'
        
        # Track test execution
        resource_id = f'test_{scenario.name}_{time.time()}'
        self.resource_tracker.track_resource(
            module='coordinator',
            resource_type='test_execution',
            resource_id=resource_id
        )
        
        start_time = time.time()
        
        try:
            # Run the test
            result = subprocess.run(
                [str(python_path), '-m', 'pytest', scenario.test_file, '-v'],
                cwd=worktree_path,
                capture_output=True,
                text=True,
                timeout=scenario.timeout
            )
            
            duration = time.time() - start_time
            
            # Determine status
            status = 'passed' if result.returncode == 0 else 'failed'
            
            test_result = TestResult(
                scenario=scenario,
                status=status,
                duration=duration,
                output=result.stdout,
                error=result.stderr if result.stderr else None
            )
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            test_result = TestResult(
                scenario=scenario,
                status='error',
                duration=duration,
                output='',
                error=f'Test timed out after {scenario.timeout} seconds'
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_context = self.capture_cross_module_error(
                source_module=f'coordinator.runner',
                target_module='coordinator.main',
                error=e
            )
            test_result = TestResult(
                scenario=scenario,
                status='error',
                duration=duration,
                output='',
                error=str(error_context)
            )
            
        finally:
            # Release test execution resource
            self.resource_tracker.release_resource(resource_id)
            
        self.results.append(test_result)
        return test_result
        
    def run_scenario_with_retry(self, scenario: TestScenario) -> TestResult:
        """Run a scenario with retry logic."""
        max_retries = 3
        
        for attempt in range(max_retries):
            result = self.run_scenario(scenario)
            
            if result.status == 'passed':
                return result
                
            if attempt < max_retries - 1:
                # Wait before retry
                time.sleep(2 ** attempt)  # Exponential backoff
                scenario.retry_count = attempt + 1
                
        return result
        
    def check_dependencies(self, scenario: TestScenario) -> bool:
        """Check if scenario dependencies are satisfied."""
        for dep in scenario.dependencies:
            # Check if dependency has passed
            dep_results = [r for r in self.results 
                          if r.scenario.name == dep and r.status == 'passed']
            if not dep_results:
                return False
        return True
        
    def run_all_scenarios(self, parallel: bool = True, max_workers: int = 4) -> None:
        """Run all registered scenarios."""
        if parallel:
            self._run_parallel(max_workers)
        else:
            self._run_sequential()
            
    def _run_sequential(self) -> None:
        """Run scenarios sequentially."""
        # Sort scenarios by dependencies
        sorted_scenarios = self._topological_sort_scenarios()
        
        for scenario in sorted_scenarios:
            if self.check_dependencies(scenario):
                self.run_scenario_with_retry(scenario)
            else:
                self.results.append(TestResult(
                    scenario=scenario,
                    status='skipped',
                    duration=0,
                    output='',
                    error='Dependencies not satisfied'
                ))
                
    def _run_parallel(self, max_workers: int) -> None:
        """Run scenarios in parallel."""
        # Start worker threads
        for i in range(max_workers):
            worker = threading.Thread(
                target=self._worker,
                name=f'test_worker_{i}'
            )
            worker.start()
            self._workers.append(worker)
            
        # Queue scenarios
        sorted_scenarios = self._topological_sort_scenarios()
        for scenario in sorted_scenarios:
            self._execution_queue.put(scenario)
            
        # Wait for completion
        self._execution_queue.join()
        
        # Stop workers
        self._stop_event.set()
        for worker in self._workers:
            worker.join()
            
    def _worker(self) -> None:
        """Worker thread for parallel execution."""
        while not self._stop_event.is_set():
            try:
                scenario = self._execution_queue.get(timeout=1)
                
                # Wait for dependencies
                while not self.check_dependencies(scenario):
                    time.sleep(0.5)
                    if self._stop_event.is_set():
                        return
                        
                self.run_scenario_with_retry(scenario)
                self._execution_queue.task_done()
                
            except queue.Empty:
                continue
                
    def _topological_sort_scenarios(self) -> List[TestScenario]:
        """Sort scenarios by dependencies."""
        # Simple implementation - could be improved
        sorted_list = []
        remaining = list(self.scenarios.values())
        
        while remaining:
            # Find scenarios with no dependencies or satisfied dependencies
            ready = []
            for scenario in remaining:
                if not scenario.dependencies:
                    ready.append(scenario)
                elif all(any(s.name == dep for s in sorted_list) 
                        for dep in scenario.dependencies):
                    ready.append(scenario)
                    
            if not ready:
                # Circular dependency or missing dependency
                raise ValueError("Circular or missing dependencies detected")
                
            sorted_list.extend(ready)
            for scenario in ready:
                remaining.remove(scenario)
                
        return sorted_list
        
    def generate_report(self) -> Dict[str, Any]:
        """Generate a test execution report."""
        total_tests = len(self.results)
        passed = sum(1 for r in self.results if r.status == 'passed')
        failed = sum(1 for r in self.results if r.status == 'failed')
        skipped = sum(1 for r in self.results if r.status == 'skipped')
        errors = sum(1 for r in self.results if r.status == 'error')
        
        total_duration = sum(r.duration for r in self.results)
        
        # Group by worktree
        by_worktree = {}
        for result in self.results:
            worktree = result.scenario.worktree
            if worktree not in by_worktree:
                by_worktree[worktree] = []
            by_worktree[worktree].append(result)
            
        # Check for resource leaks
        leaks = self.resource_tracker.get_all_resources(state='active')
        
        return {
            'summary': {
                'total': total_tests,
                'passed': passed,
                'failed': failed,
                'skipped': skipped,
                'errors': errors,
                'duration': total_duration,
                'success_rate': (passed / total_tests * 100) if total_tests > 0 else 0
            },
            'by_worktree': {
                wt: {
                    'total': len(results),
                    'passed': sum(1 for r in results if r.status == 'passed'),
                    'failed': sum(1 for r in results if r.status == 'failed')
                }
                for wt, results in by_worktree.items()
            },
            'failures': [
                {
                    'scenario': r.scenario.name,
                    'worktree': r.scenario.worktree,
                    'error': r.error,
                    'duration': r.duration
                }
                for r in self.results if r.status in ('failed', 'error')
            ],
            'resource_leaks': [
                {
                    'resource_id': r['resource_id'],
                    'type': r['resource_type'],
                    'module': r['owner_module']
                }
                for r in leaks
            ],
            'timestamp': datetime.now().isoformat()
        }
        
    def save_report(self, filepath: Path) -> None:
        """Save report to file."""
        report = self.generate_report()
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
            
    def cleanup_worktrees(self) -> None:
        """Clean up all worktrees."""
        active_worktrees = self.resource_tracker.get_all_resources(
            module='coordinator',
            state='active'
        )
        
        for resource in active_worktrees:
            if resource['resource_type'] == 'worktree':
                worktree_name = resource['resource_id'].replace('worktree_', '')
                worktree_path = self.base_path / worktree_name
                
                try:
                    # Remove worktree
                    subprocess.run(
                        ['git', 'worktree', 'remove', str(worktree_path)],
                        cwd=self.main_repo_path,
                        check=True
                    )
                    
                    # Mark resource as released
                    self.resource_tracker.release_resource(resource['resource_id'])
                    
                except subprocess.CalledProcessError:
                    pass  # Ignore cleanup errors