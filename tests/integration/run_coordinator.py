#!/usr/bin/env python
"""Command-line interface for the integration test coordinator."""

import argparse
import sys
from pathlib import Path
import json

from coordinator import IntegrationCoordinator, TestScenario


def main():
    parser = argparse.ArgumentParser(
        description='Run Phase 7 integration tests across multiple worktrees'
    )
    
    parser.add_argument(
        '--base-path',
        type=Path,
        default=Path.home() / 'code' / 'treesitter-chunker-worktrees',
        help='Base path for worktrees (default: ~/code/treesitter-chunker-worktrees)'
    )
    
    parser.add_argument(
        '--main-repo',
        type=Path,
        default=Path.home() / 'code' / 'treesitter-chunker',
        help='Path to main repository (default: ~/code/treesitter-chunker)'
    )
    
    parser.add_argument(
        '--scenarios',
        type=Path,
        default=Path(__file__).parent / 'scenarios.json',
        help='Path to scenarios configuration file'
    )
    
    parser.add_argument(
        '--setup-worktrees',
        action='store_true',
        help='Set up missing worktrees before running tests'
    )
    
    parser.add_argument(
        '--pull-coordinator',
        action='store_true',
        help='Pull coordinator changes in all worktrees'
    )
    
    parser.add_argument(
        '--parallel',
        action='store_true',
        default=True,
        help='Run tests in parallel (default: True)'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help='Number of parallel workers (default: 4)'
    )
    
    parser.add_argument(
        '--filter-tag',
        action='append',
        help='Only run scenarios with specified tag(s)'
    )
    
    parser.add_argument(
        '--filter-worktree',
        action='append',
        help='Only run scenarios in specified worktree(s)'
    )
    
    parser.add_argument(
        '--report',
        type=Path,
        default=Path('integration_report.json'),
        help='Path to save test report (default: integration_report.json)'
    )
    
    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Clean up worktrees after testing'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be run without executing'
    )
    
    args = parser.parse_args()
    
    # Initialize coordinator
    coordinator = IntegrationCoordinator(args.base_path, args.main_repo)
    
    # Load scenarios
    if args.scenarios.exists():
        coordinator.register_scenarios_from_config(args.scenarios)
        print(f"Loaded {len(coordinator.scenarios)} test scenarios")
    else:
        print(f"Error: Scenarios file not found: {args.scenarios}")
        return 1
    
    # Filter scenarios
    filtered_scenarios = list(coordinator.scenarios.values())
    
    if args.filter_tag:
        filtered_scenarios = [
            s for s in filtered_scenarios
            if any(tag in s.tags for tag in args.filter_tag)
        ]
        
    if args.filter_worktree:
        filtered_scenarios = [
            s for s in filtered_scenarios
            if s.worktree in args.filter_worktree
        ]
    
    # Update coordinator with filtered scenarios
    coordinator.scenarios = {s.name: s for s in filtered_scenarios}
    
    if args.dry_run:
        print("\nScenarios to run:")
        for scenario in filtered_scenarios:
            print(f"  - {scenario.name} ({scenario.worktree}): {scenario.description}")
            if scenario.dependencies:
                print(f"    Dependencies: {', '.join(scenario.dependencies)}")
        print(f"\nTotal: {len(filtered_scenarios)} scenarios")
        return 0
    
    # Check worktrees
    print("\nChecking worktrees...")
    worktrees_needed = set(s.worktree for s in filtered_scenarios)
    missing_worktrees = []
    
    for worktree in worktrees_needed:
        if coordinator.verify_worktree_setup(worktree):
            print(f"  ✓ {worktree}")
        else:
            print(f"  ✗ {worktree} (missing or incomplete)")
            missing_worktrees.append(worktree)
    
    # Set up missing worktrees if requested
    if missing_worktrees and args.setup_worktrees:
        print("\nSetting up missing worktrees...")
        for worktree in missing_worktrees:
            branch = f"feature/test-{worktree.replace('_', '-')}"
            print(f"  Setting up {worktree} with branch {branch}...")
            if coordinator.setup_worktree(worktree, branch):
                print(f"  ✓ {worktree} set up successfully")
            else:
                print(f"  ✗ Failed to set up {worktree}")
                return 1
    elif missing_worktrees:
        print("\nError: Missing worktrees. Use --setup-worktrees to create them.")
        return 1
    
    # Pull coordinator changes if requested
    if args.pull_coordinator:
        print("\nPulling coordinator changes...")
        for worktree in worktrees_needed:
            if coordinator.pull_coordinator_changes(worktree):
                print(f"  ✓ Updated {worktree}")
            else:
                print(f"  ✗ Failed to update {worktree}")
    
    # Run tests
    print(f"\nRunning {len(filtered_scenarios)} test scenarios...")
    if args.parallel:
        print(f"Using {args.workers} parallel workers")
    
    coordinator.run_all_scenarios(
        parallel=args.parallel,
        max_workers=args.workers
    )
    
    # Generate and save report
    report = coordinator.generate_report()
    
    print("\n" + "="*60)
    print("TEST RESULTS")
    print("="*60)
    print(f"Total:    {report['summary']['total']}")
    print(f"Passed:   {report['summary']['passed']}")
    print(f"Failed:   {report['summary']['failed']}")
    print(f"Skipped:  {report['summary']['skipped']}")
    print(f"Errors:   {report['summary']['errors']}")
    print(f"Duration: {report['summary']['duration']:.2f}s")
    print(f"Success:  {report['summary']['success_rate']:.1f}%")
    
    # Show failures
    if report['failures']:
        print("\nFAILURES:")
        for failure in report['failures']:
            print(f"\n  {failure['scenario']} ({failure['worktree']})")
            if failure['error']:
                print(f"    Error: {failure['error'][:200]}...")
    
    # Show resource leaks
    if report['resource_leaks']:
        print("\nRESOURCE LEAKS DETECTED:")
        for leak in report['resource_leaks']:
            print(f"  - {leak['type']}: {leak['resource_id']} ({leak['module']})")
    
    # Save report
    coordinator.save_report(args.report)
    print(f"\nDetailed report saved to: {args.report}")
    
    # Cleanup if requested
    if args.cleanup:
        print("\nCleaning up worktrees...")
        coordinator.cleanup_worktrees()
        print("Cleanup complete")
    
    # Exit with appropriate code
    return 0 if report['summary']['failed'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())