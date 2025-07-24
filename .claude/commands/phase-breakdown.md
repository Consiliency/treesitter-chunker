# phase-breakdown.md - Custom Slash Command for Claude Code

Place this file at: `.claude/commands/phase-breakdown.md`

---
allowed-tools: Bash(git worktree:*), Bash(git branch:*), Bash(git status:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(cat:*), Bash(mkdir:*), Bash(echo:*), Bash(cd:*), Bash(ls:*), Bash(test:*), Bash(if:*), Bash(for:*), Task, TodoWrite, Write, MultiEdit, Read, Glob, Grep
description: Break down a development phase into parallel tasks with clear interface boundaries
argument-hint: [phase-name]
---

## Context

Current git status: !`git status`
Current branch: !`git branch --show-current`
Existing worktrees: !`git worktree list`

## Roadmap Content

!`cat ./specs/ROADMAP.md`

## Instructions

You are a Claude Code custom slash command designed to help break down a problem into parallel tasks and manage the development process. Your goal is to guide the implementation of the next phase of development based on the ROADMAP.md file above.

The phase to implement is: **$ARGUMENTS**

Follow these steps:

### 1. Ultra-think about the next phase
- Analyze the "$ARGUMENTS" phase and corresponding details from the roadmap content above
- Develop a comprehensive understanding of the phase's objectives and requirements
- Consider dependencies, constraints, and expected outcomes

### 2. Break down the phase into separable, non-interfering tasks
- Identify tasks that can be worked on independently without creating merge conflicts
- Focus on clear interface boundaries between components
- Ensure these tasks align with the phase objectives from the roadmap

### 3. Create concrete interface implementations in main branch
- Generate actual interface code files (not just TypeScript definitions)
- Create stub implementations with clear method signatures
- Each method should throw "Not implemented" errors initially
- Commit and push these to main branch before creating worktrees
- This ensures all teams work from the same concrete implementation

### 4. Write and commit integration tests first
- Create comprehensive integration tests that define expected behavior
- Tests should cover all cross-component interactions
- Tests will fail initially (this is expected)
- Commit and push tests to main branch
- Each team's success is measured by making these tests pass

### 5. Create work trees and launch sub-agents
- Verify interfaces and tests exist in main branch before proceeding
- For each identified task, create a separate git worktree inside the project
- Use naming convention: `./worktrees/task-{name}` for worktree directories
- Use the Task tool to spawn Claude agents for each worktree
- Include explicit references to interface files and integration tests in agent prompts

### 6. Merging and integration plan
- Define the order and process for merging completed work
- Include commands for creating and merging pull requests
- Specify integration test execution steps
- Verify all integration tests pass before final merge

### 7. Documentation updates
- Identify documentation that needs updating
- Prepare for the next development phase

## Output Format

Structure your response as follows:

### Phase Analysis
Provide comprehensive analysis of the "$ARGUMENTS" phase including:
- Key objectives and requirements
- Dependencies and constraints
- Expected outcomes
- Risk factors and mitigation strategies

### Task Breakdown
List separable tasks with clear boundaries:
1. **Task Name**: Description
   - Interface boundaries: [specific files/modules]
   - Dependencies: [what it needs from other tasks]
   - Deliverables: [what it provides]

### Contract Definitions
Create concrete contract files AND stub implementations in the main branch before parallel work:

    ```python
    # File: [project]/contracts/[component]_contract.py
    # Purpose: Define the boundary between components
    # Team responsible: [Team Name]
    
    from abc import ABC, abstractmethod
    from typing import Any, Dict, List, Optional, Tuple, Union
    
    class [ComponentContract](ABC):
        """Abstract contract defining component interface"""
        
        @abstractmethod
        def method_name(self, param1: Type1, param2: Type2) -> ReturnType:
            """Document expected behavior
            
            Args:
                param1: Description of parameter 1
                param2: Description of parameter 2
                
            Returns:
                Description of return value
                
            Preconditions:
                - What must be true before calling
                
            Postconditions:
                - What will be true after calling
            """
            pass
    
    # File: [project]/contracts/[component]_stub.py
    # Purpose: Concrete stub implementation for testing
    
    class [ComponentStub]([ComponentContract]):
        """Stub implementation that can be instantiated and tested"""
        
        def method_name(self, param1: Type1, param2: Type2) -> ReturnType:
            """Stub that returns valid default values"""
            # Return appropriate default for the return type
            # This ensures integration tests use correct types
            if ReturnType is str:
                return "Not implemented - [Team] will implement"
            elif ReturnType is dict:
                return {"status": "not_implemented", "team": "[Team]"}
            elif ReturnType is bool:
                return False
            elif ReturnType is list:
                return []
            elif ReturnType is tuple:
                return (False, {"message": "Not implemented"})
            else:
                raise NotImplementedError("[Team] will implement")
    ```

### Integration Test Specifications
Define expected behavior using ACTUAL stub implementations (NOT mocks!):

    ```python
    # File: tests/test_[phase]_integration.py
    # Test: [Integration Scenario Name]
    # Components involved: [List components]
    # Expected behavior: [Description]
    
    # CRITICAL: Import stub implementations, not Mock!
    from [project].contracts.[component1]_stub import [Component1Stub]
    from [project].contracts.[component2]_stub import [Component2Stub]
    
    def test_[scenario]_integration():
        """Test integration between components using real stubs"""
        # Arrange: Create real stub instances (NOT Mock()!)
        component1 = [Component1Stub]()
        component2 = [Component2Stub]()
        
        # Act: Execute cross-component operation
        result = component1.method_name(param1, param2)
        processed = component2.process(result)
        
        # Assert: Verify return types and structure
        # These assertions will FAIL if stubs don't match contracts!
        assert isinstance(result, expected_type), f"Expected {expected_type}, got {type(result)}"
        assert isinstance(processed, expected_type2)
        
        # Verify the structure matches contract expectations
        if isinstance(result, dict):
            assert 'required_field' in result
        
        # This ensures implementations will work when integrated
    ```

### Contract Compliance Tests
Create tests that verify implementations match contracts exactly:

    ```python
    # File: tests/test_contract_compliance.py
    
    import inspect
    from [project].contracts.[component]_contract import [ComponentContract]
    
    def test_[component]_contract_compliance(implementation_class):
        """Verify implementation matches contract exactly"""
        contract = [ComponentContract]
        
        # Get all abstract methods from contract
        abstract_methods = [
            name for name, method in inspect.getmembers(contract)
            if hasattr(method, '__isabstractmethod__') and method.__isabstractmethod__
        ]
        
        # Check all abstract methods are implemented
        for method_name in abstract_methods:
            assert hasattr(implementation_class, method_name), \
                f"Missing implementation for {method_name}"
            
            # Verify signatures match exactly
            contract_method = getattr(contract, method_name)
            impl_method = getattr(implementation_class, method_name)
            
            contract_sig = inspect.signature(contract_method)
            impl_sig = inspect.signature(impl_method)
            
            # Remove 'self' parameter for comparison
            contract_params = list(contract_sig.parameters.values())[1:]
            impl_params = list(impl_sig.parameters.values())[1:]
            
            assert len(contract_params) == len(impl_params), \
                f"Parameter count mismatch for {method_name}"
            
            # Check return type annotation
            assert contract_sig.return_annotation == impl_sig.return_annotation, \
                f"Return type mismatch for {method_name}"
    ```

### Permissions Setup

**CRITICAL: Configure permissions first to enable automated workflows.**

Create or update `.claude/settings.json` with these permissions:

    ```json
    {
      "allow": [
        "Bash(git worktree:*)",
        "Bash(git branch:*)",
        "Bash(git status:*)",
        "Bash(git commit:*)",
        "Bash(git push:*)",
        "Bash(git merge:*)",
        "Bash(cd worktrees/*)",
        "Bash(ls worktrees/*)",
        "Bash(mkdir worktrees/*)",
        "Edit(worktrees/**)",
        "Read(worktrees/**)",
        "Bash(npm:*)",
        "Bash(npm run:*)",
        "Task"
      ]
    }
    ```

### Work Tree Setup Commands

**Step 0: Create and Commit Contracts First**

    ```bash
    # CRITICAL: Create contract files and tests BEFORE creating worktrees
    # This ensures all teams work from the same interface definitions
    
    # Create contract files using the Write tool
    # Create integration test files using the Write tool
    
    # Commit contracts AND stub implementations to main branch
    git add [project]/contracts/*_contract.py
    git add [project]/contracts/*_stub.py
    git commit -m "feat: define component contracts and stub implementations"
    
    # Commit integration tests (using stubs, not mocks!)
    git add tests/test_*_integration.py
    git add tests/test_contract_compliance.py
    git commit -m "test: add integration tests with real stub implementations"
    
    # Push to main - this is REQUIRED before creating worktrees
    git push origin main
    
    # Verify stubs work with integration tests BEFORE creating worktrees
    pytest tests/test_*_integration.py -v
    # These should pass with stub implementations!
    ```

**Step 1: Create Internal Work Trees**

    ```bash
    # NOW create worktrees - they will inherit the contracts from main
    mkdir -p worktrees
    
    # Create work trees inside project directory (replace with actual task names)
    git worktree add ./worktrees/task1-[name] -b feature/[name]
    git worktree add ./worktrees/task2-[name] -b feature/[name]  
    git worktree add ./worktrees/task3-[name] -b feature/[name]
    
    # Verify creation
    git worktree list
    ls -la worktrees/
    ```

**Step 2: Launch Sub-Agents Using Task Tool**

**IMPORTANT**: Use the Task tool to spawn agents - do NOT use manual `claude -p` commands which can incorrectly charge API keys instead of using your Max subscription.

    ```bash
    # Task tool spawns sub-agents automatically within current Claude session
    # No manual terminal navigation required
    ```

### Sub-Agent Task Spawning

#### Task 1: [Component Name]
    ```
    Task("You are working on [Component Name] in the ./worktrees/task1-[name] directory.

    **Working Directory**: ./worktrees/task1-[name]
    **Phase**: $ARGUMENTS
    **Your Component Boundaries**: [List the specific areas this component owns]
    
    **Contract to Implement**: 
    - Review the contract file: [path to contract file in main branch]
    - You must implement ALL methods defined in the contract
    - Do NOT change method signatures - they are frozen
    - Your implementation must make the integration tests pass
    
    **Integration Tests to Pass**:
    - Review test file: [path to integration test file]
    - These tests define the expected behavior
    - Run them frequently to verify your implementation

    **Dependencies Available**: 
    - [List shared resources/utilities]
    - Other component contracts (use their interfaces, not implementations)

    **Your Objectives**:
    1. Implement all methods in your contract
    2. Make all related integration tests pass
    3. Add unit tests for your implementation
    4. Handle all error cases gracefully
    5. Document your component's behavior

    **Critical Constraints**:
    - Work ONLY within your worktree directory
    - NEVER modify the contract signatures
    - Reference other components only through their contracts
    - If integration tests fail, fix YOUR implementation, not the tests
    - Commit frequently with clear messages
    
    **Contract Compliance Requirements**:
    - Your implementation MUST have the EXACT same method signatures as the contract
    - Run contract compliance tests frequently: pytest tests/test_contract_compliance.py
    - If compliance tests fail, fix YOUR implementation signature to match
    - Do NOT modify return type annotations or parameter types
    - Return actual values of the correct type, not Mock objects
    - Ensure all return values match the contract's type hints exactly

    **Workflow**:
    1. Navigate to worktree: cd ./worktrees/task1-[name]
    2. Review the contract file from main branch
    3. Review integration tests to understand expected behavior
    4. Implement contract methods one by one
    5. Run integration tests frequently
    6. Add unit tests for your implementation
    7. Document your component

    Begin by examining your contract and understanding what needs to be implemented.")
    ```

#### Task 2: [Component Name]
    ```
    Task("You are working on [Component Name] in the ./worktrees/task2-[name] directory.

    **Working Directory**: ./worktrees/task2-[name]
    **Phase**: $ARGUMENTS
    **Your Component Boundaries**: [Specific areas this component owns]
    
    **Contract to Implement**: 
    - Contract file: [path to contract]
    - Integration tests: [path to tests]
    - Follow the contract EXACTLY - no modifications allowed
    
    **Your Implementation Focus**:
    - [Key responsibility 1]
    - [Key responsibility 2]
    - [Key responsibility 3]

    Remember: The integration tests define success. Make them pass.")
    ```

#### Task 3: [Component Name]
    ```
    Task("You are working on [Component Name] in the ./worktrees/task3-[name] directory.

    **Phase**: $ARGUMENTS
    **Contract**: [path to contract file]
    **Tests**: [path to integration tests]
    
    Focus on making the integration tests pass while staying within your component boundaries.")
    ```

### Agent Management Commands

**Monitor All Worktree Progress**:
    ```bash
    # Check status across all worktrees
    echo "=== WORKTREE STATUS OVERVIEW ==="
    git worktree list
    
    echo -e "\n=== INDIVIDUAL WORKTREE STATUS ==="
    for worktree in ./worktrees/*/; do
        if [ -d "$worktree" ]; then
            echo "--- $(basename "$worktree") ---"
            cd "$worktree" && git status --short && cd - > /dev/null
        fi
    done
    
    echo -e "\n=== RECENT COMMITS ==="
    git log --oneline --graph --all -10
    ```

**Check Individual Worktree**:
    ```bash
    # Check specific worktree (replace task1-auth with actual name)
    cd ./worktrees/task1-auth
    git status
    git log --oneline -5
    cd ../..
    ```

### Merge and Integration Plan

**Pre-merge Checklist**:
   - [ ] Contract compliance tests pass (signatures match exactly)
   - [ ] Integration tests pass with REAL implementations (no mocks)
   - [ ] All stub methods have been replaced with real implementations
   - [ ] Return types match contract specifications exactly
   - [ ] No Mock objects in production code
   - [ ] All integration tests pass (these were written BEFORE implementation)
   - [ ] Contract methods are fully implemented (no "Not implemented" errors remain)
   - [ ] Unit tests added for implementation details
   - [ ] No modifications made to contract signatures
   - [ ] Code review completed focusing on contract compliance
   - [ ] No conflicts with main branch

**Integration Sequence** (merge foundational tasks first):

    ```bash
    # 1. Update main branch first
    git checkout main
    git pull origin main
    
    # 2. Merge tasks in dependency order (foundational first)
    echo "=== Merging [Component 1] (foundational) ==="
    git merge feature/[branch-name] --no-ff -m "feat: integrate [component description]"
    
    # Run integration tests after EVERY merge
    # Replace with your test command
    [test command]
    [integration test command]
    
    # Push immediately to catch integration issues early
    git push origin main
    
    echo "=== Merging [Component 2] ==="
    git merge feature/[branch-name] --no-ff -m "feat: integrate [component description]"
    [test command]
    git push origin main
    
    echo "=== Merging [Component 3] ==="
    git merge feature/[branch-name] --no-ff -m "feat: integrate [component description]"
    [test command]
    git push origin main
    
    echo "=== Final Integration Validation ==="
    # Run all integration tests one final time
    [full test suite command]
    ```

**Integration Testing Commands**:
    ```bash
    # Run integration tests frequently during development
    [your test command for integration tests]
    
    # Verify contract compliance
    [your command to verify contracts are satisfied]
    
    # Full validation suite
    [unit tests command]           # Component-level tests
    [integration tests command]    # Cross-component tests
    [contract tests command]       # Contract compliance
    [build command]               # Build verification
    ```

### Worktree Cleanup

**After Successful Integration**:
    ```bash
    # List all worktrees to confirm what exists
    git worktree list
    
    # Remove completed worktrees (they're now integrated)
    git worktree remove ./worktrees/task1-auth
    git worktree remove ./worktrees/task2-api  
    git worktree remove ./worktrees/task3-frontend
    
    # Clean up any stale references
    git worktree prune
    
    # Optionally remove feature branches (they're merged)
    git branch -d feature/auth-system
    git branch -d feature/api-endpoints
    git branch -d feature/frontend-components
    
    # Clean up worktrees directory if empty
    rmdir worktrees 2>/dev/null || echo "Worktrees directory not empty or doesn't exist"
    
    echo "=== Cleanup Complete ==="
    git status
    ```

### Documentation Updates
- Files to update: [list with paths]
- New documentation needed: [list]
- Archive: [what to archive]  
- Next phase preparation: [steps]

## Important Notes

**Permissions**: The `.claude/settings.json` configuration enables automated workflows without manual approval prompts.

**Task Tool Usage**: Use the Task tool to spawn sub-agents rather than manual terminal commands. This ensures proper session management and Max subscription usage.

**Directory Structure**: All parallel work happens in `./worktrees/` subdirectories within your project, avoiding Claude Code's security restrictions.

**Integration Strategy**: Merge in dependency order (foundational components first) with comprehensive testing after each integration.

**Error Recovery**: If a Task agent encounters issues, the main Claude session can inspect the worktree and provide guidance.

## Interface Testing Best Practices

Based on real-world experience, follow these practices for successful parallel development:

1. **Concrete Stubs Are Essential**
   - Abstract interfaces alone will cause integration failures
   - Always create instantiable stub implementations
   - Stubs must return correct types, not Mock objects

2. **Test With Real Objects**
   - Integration tests using Mock() hide type mismatches
   - Use actual stub implementations in all integration tests
   - This ensures components will integrate properly

3. **Contract Compliance Testing**
   - Create separate tests to verify signatures match
   - Run these before any integration attempts
   - Fail fast when contracts are violated

4. **Type Safety at Boundaries**
   - Return types must match contract specifications exactly
   - Use type hints and runtime validation
   - Component boundaries are where most integration failures occur

5. **Pre-Integration Verification**
   - Run all integration tests with stubs before creating worktrees
   - Ensure stubs pass all integration tests
   - This validates your interface design early

Remember: The goal is to enable truly parallel development with minimal merge conflicts through proper interface design and automated agent orchestration.

## Usage Examples

    ```bash
    # In Claude Code main project directory:
    /phase-breakdown Phase 1: Foundation Setup
    /phase-breakdown "Phase 2: API Implementation"
    /phase-breakdown Phase 3: Frontend Development
    ```

## Additional Setup Instructions

### 1. Create the command file:
    ```bash
    mkdir -p .claude/commands
    # Copy this entire markdown content into:
    # .claude/commands/phase-breakdown.md
    ```

### 2. Ensure your project has the expected structure:
    ```
    project-root/
    ├── specs/
    │   └── ROADMAP.md
    ├── .claude/
    │   ├── commands/
    │   │   └── phase-breakdown.md
    │   └── settings.json
    ├── worktrees/           # Created automatically
    │   ├── task1-name/      # Git worktrees for parallel work
    │   ├── task2-name/
    │   └── task3-name/
    └── src/
        └── ... (project files)
    ```

### 3. ROADMAP.md format should include clear phase definitions:
    ```markdown
    # Project Roadmap

    ## Phase 1: Foundation Setup
    - Initialize project structure
    - Set up development environment
    - Define core architecture
    - Establish coding standards

    ## Phase 2: API Implementation  
    - Design RESTful endpoints
    - Implement GraphQL schema
    - Create authentication system
    - Set up database models
    - Build data validation layer

    ## Phase 3: Frontend Development
    - Create React component library
    - Implement state management
    - Build API integration layer
    - Design responsive UI/UX
    ```

The command will read this roadmap and help break down whichever phase you specify into parallel, non-conflicting tasks with automated agent orchestration using the Task tool.
```