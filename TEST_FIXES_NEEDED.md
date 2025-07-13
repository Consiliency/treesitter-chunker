# Test Fixes Needed

## Summary
- Total tests: 558
- Passing: 513 
- Failing: 43
- Skipped: 2

## Fixed Issues
1. CLI command name: Changed `list-languages` to `languages`
2. Added `--quiet` flag to batch commands to suppress progress output
3. Removed non-existent options: `--auto-detect-language`, `--continue-on-error`, `--output`, `--stream`, `--progress`
4. Fixed plugin tests to mock parser for non-existent languages

## Remaining Issues

### CLI Integration Tests (test_cli_integration_advanced.py)
- JSON parsing issues with batch command output
- Some CLI options don't match actual implementation
- Need to verify actual CLI interface

### Plugin Integration Tests (test_plugin_integration_advanced.py) 
- Many tests assume plugin features that don't exist in current implementation
- Need to mock parser for all plugin tests
- Plugin lifecycle methods not matching actual API

### Recovery Tests (test_recovery.py)
- Mock setup issues for crash simulation
- Multiprocessing tests have race conditions
- Some recovery features not implemented

## Recommendations
1. Focus on core functionality tests first (parser, chunking, export)
2. Update advanced tests to match actual implementation
3. Add proper mocking for external dependencies
4. Consider marking some tests as integration tests that require full setup