# phase-breakdown.md - Custom Slash Command for Claude Code

Place this file at: `.claude/commands/phase-breakdown.md`

---
allowed-tools: Bash(git worktree:*), Bash(git branch:*), Bash(git status:*), Bash(cat:*), Bash(mkdir:*), Bash(echo:*), Bash(cd:*), Bash(ls:*), Task
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

### 3. Define interfaces and tests
- Create interface definitions that outline contracts between different tasks
- Design integration tests for these interfaces
- Ensure interfaces minimize coupling between parallel work streams

### 4. Create work trees and launch sub-agents
- For each identified task, provide commands to create a separate git worktree inside the project
- Use naming convention: `./worktrees/task-{name}` for worktree directories
- Use the Task tool to spawn Claude agents for each worktree
- Include all necessary context and constraints in each agent prompt

### 5. Merging and integration plan
- Define the order and process for merging completed work
- Include commands for creating and merging pull requests
- Specify integration test execution steps

### 6. Documentation updates
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

### Interface Definitions
    ```typescript
    // or appropriate language
    // Define interfaces here
    ```

### Integration Tests
    ```typescript
    // Define integration test specifications
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

**Step 1: Create Internal Work Trees**

    ```bash
    # Ensure worktrees directory exists
    mkdir -p worktrees
    
    # Create work trees inside project directory (replace with actual task names)
    git worktree add ./worktrees/task1-auth -b feature/auth-system
    git worktree add ./worktrees/task2-api -b feature/api-endpoints  
    git worktree add ./worktrees/task3-frontend -b feature/frontend-components
    
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

#### Task 1: [Auth System]
    ```
    Task("You are working on the Authentication System in the ./worktrees/task1-auth directory.

    **Working Directory**: ./worktrees/task1-auth
    **Phase**: $ARGUMENTS
    **Your Boundaries**: Authentication modules, user management, session handling
    **Interfaces to Implement**: 
    - UserAuth interface with login/logout/register methods
    - SessionManager interface for token handling
    - AuthMiddleware for route protection

    **Dependencies Available**: 
    - Database models (shared)
    - Crypto utilities (shared)
    - Configuration system (shared)

    **Your Objectives**:
    1. Implement user authentication system with JWT tokens
    2. Create password hashing and validation utilities  
    3. Build session management with refresh tokens
    4. Add authentication middleware for API routes
    5. Write comprehensive unit tests for all auth functions
    6. Document all public authentication APIs

    **Constraints**:
    - Work ONLY within ./worktrees/task1-auth directory
    - Implement interfaces exactly as specified above
    - Follow project coding standards from main CLAUDE.md
    - Include error handling for all edge cases
    - Commit work in logical chunks with descriptive messages
    - Run tests after each major change

    **Workflow**:
    1. First, navigate to and examine the worktree: cd ./worktrees/task1-auth && ls -la
    2. Review current authentication-related code
    3. Plan implementation approach
    4. Implement core authentication logic
    5. Add comprehensive tests
    6. Document APIs and usage
    7. Validate integration points match defined interfaces

    Begin by changing to the worktree directory and examining the current state.")
    ```

#### Task 2: [API Endpoints]
    ```
    Task("You are working on the API Endpoints in the ./worktrees/task2-api directory.

    **Working Directory**: ./worktrees/task2-api
    **Phase**: $ARGUMENTS
    **Your Boundaries**: REST API routes, request validation, response formatting
    **Interfaces to Implement**:
    - RESTful endpoints following OpenAPI 3.0 spec
    - Request validation middleware
    - Standardized error response format
    - API versioning system

    **Dependencies Available**:
    - Authentication system (interface only - implementation in parallel)
    - Database models (shared)
    - Validation libraries (shared)

    **Your Objectives**:
    1. Design and implement RESTful API endpoints
    2. Add request validation and sanitization
    3. Implement standardized error handling
    4. Create API documentation with examples
    5. Add integration tests for all endpoints
    6. Implement rate limiting and security headers

    **Constraints**:
    - Work ONLY within ./worktrees/task2-api directory
    - Design for the auth interface (implementation will be integrated later)
    - Follow RESTful conventions and HTTP status codes
    - Include comprehensive error handling
    - Validate all inputs thoroughly
    - Commit work in logical chunks

    **Workflow**:
    1. Navigate to worktree: cd ./worktrees/task2-api && ls -la
    2. Review existing API structure
    3. Plan endpoint design and data flow
    4. Implement core API routes
    5. Add validation and error handling
    6. Create comprehensive tests
    7. Document all endpoints

    Begin by changing to the worktree directory and examining the current state.")
    ```

#### Task 3: [Frontend Components]
    ```
    Task("You are working on Frontend Components in the ./worktrees/task3-frontend directory.

    **Working Directory**: ./worktrees/task3-frontend
    **Phase**: $ARGUMENTS  
    **Your Boundaries**: UI components, state management, client-side routing
    **Interfaces to Implement**:
    - Reusable component library
    - State management with consistent patterns
    - API integration layer
    - Responsive design system

    **Dependencies Available**:
    - API endpoints (interface only - implementation in parallel)
    - Design system guidelines (shared)
    - Utility functions (shared)

    **Your Objectives**:
    1. Build reusable UI component library
    2. Implement state management for application data
    3. Create API integration layer for data fetching
    4. Add responsive design and accessibility features
    5. Write component tests and interaction tests
    6. Document component usage and props

    **Constraints**:
    - Work ONLY within ./worktrees/task3-frontend directory
    - Design for the API interface (implementation will be integrated later)
    - Follow accessibility guidelines (WCAG 2.1)
    - Ensure mobile-responsive design
    - Include comprehensive testing
    - Use TypeScript for type safety

    **Workflow**:
    1. Navigate to worktree: cd ./worktrees/task3-frontend && ls -la
    2. Review existing component structure
    3. Plan component architecture and data flow
    4. Implement core UI components
    5. Add state management and API integration
    6. Create comprehensive tests
    7. Document component library

    Begin by changing to the worktree directory and examining the current state.")
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
   - [ ] All unit tests pass in each worktree
   - [ ] Interface contracts are satisfied and validated
   - [ ] Code review completed for each task
   - [ ] Integration tests defined and ready
   - [ ] No conflicts with main branch

**Integration Sequence** (merge foundational tasks first):

    ```bash
    # 1. Update main branch first
    git checkout main
    git pull origin main
    
    # 2. Merge tasks in dependency order (foundational first)
    echo "=== Merging Auth System (foundational) ==="
    git merge feature/auth-system --no-ff -m "feat: integrate authentication system"
    
    # Run integration tests after each merge
    npm test  # or your test command
    npm run test:integration
    
    # Push immediately to update remote
    git push origin main
    
    echo "=== Merging API Endpoints ==="
    git merge feature/api-endpoints --no-ff -m "feat: integrate API endpoints"
    npm test && npm run test:integration
    git push origin main
    
    echo "=== Merging Frontend Components ==="
    git merge feature/frontend-components --no-ff -m "feat: integrate frontend components"
    npm test && npm run test:integration && npm run test:e2e
    git push origin main
    
    echo "=== Final Integration Validation ==="
    npm run build
    npm run test:all
    ```

**Integration Testing**:
    ```bash
    # Comprehensive integration test suite
    npm run test:unit           # All unit tests
    npm run test:integration    # Cross-component integration
    npm run test:e2e           # End-to-end user workflows
    npm run test:api           # API contract testing
    npm run lint               # Code quality checks
    npm run type-check         # TypeScript validation
    npm run build              # Build verification
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