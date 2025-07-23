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
Create concrete contract files in the main branch before parallel work:

    ```
    // Contract: [Component Name]
    // Purpose: Define the boundary between components
    // Team responsible: [Team Name]
    
    interface [ComponentContract] {
      method: [methodName](parameters) -> returnType
        preconditions: [what must be true before calling]
        postconditions: [what will be true after calling]
        implementation: throw "Not implemented - [Team] will implement"
    }
    ```

### Integration Test Specifications
Define expected behavior across component boundaries:

    ```
    // Test: [Integration Scenario Name]
    // Components involved: [List components]
    // Expected behavior: [Description]
    
    test "[scenario description]" {
      // Arrange: Set up test data
      [setup code]
      
      // Act: Execute cross-component operation
      [execution code]
      
      // Assert: Verify expected behavior
      assert [expected condition]
    }
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
    
    # Commit contracts to main branch
    git add [contract files]
    git commit -m "feat: define component contracts for parallel development"
    
    # Commit integration tests
    git add [test files]  
    git commit -m "test: add integration specifications for contracts"
    
    # Push to main - this is REQUIRED before creating worktrees
    git push origin main
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