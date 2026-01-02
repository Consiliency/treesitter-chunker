---
name: explore-architecture
argument-hint: [depth: quick|standard|deep]
description: "Explore codebase architecture, build C4 diagrams, capture technical context for AI-assisted development."
allowed-tools: Bash(git:*), Bash(find:*), Bash(wc:*), Bash(ls:*), Read, Glob, Grep
---

# Explore Codebase Architecture

Systematically explore a brownfield codebase to build a comprehensive C4 architectural model with Mermaid diagrams and capture all context needed for continued development.

## Inputs

- `$1` = Exploration depth (optional, defaults to `standard`)
  - `quick`: Entry points, main dependencies, high-level structure (~5 min)
  - `standard`: Full C4 model, dependency graph, pattern detection (~15 min)
  - `deep`: Component-level docs, code-level diagrams, full tech debt audit (~30 min)

## Workflow

### 1. Initialize Exploration

Spawn the `architecture-explorer` subagent with the following context:

```
Use the architecture-explorer subagent to explore this codebase.

Context:
- Depth: $1 (or "standard" if not specified)
- Working directory: Current project root
- Output location: .claude/architecture/

Instructions:
1. Start with entry point discovery
2. Build dependency graph
3. Construct C4 model (Context → Container → Component)
4. Identify patterns and anti-patterns
5. Document technical debt
6. Generate Mermaid diagrams for each C4 level
7. Write findings to output location
```

### 2. Entry Point Discovery

Find the starting points of the codebase:

- Package manifests: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `*.csproj`
- Main files: `main.*`, `index.*`, `app.*`, `server.*`
- Config files: Framework configs, build configs, environment files
- README and documentation

### 3. Dependency Mapping

Build the module dependency graph:

- Parse import/export statements
- Identify external vs internal dependencies
- Map module relationships
- Detect circular dependencies

### 4. C4 Model Construction

Build each layer of the C4 model:

#### Context Level
- System boundaries
- External actors (users, external systems, APIs)
- High-level data flows

#### Container Level
- Deployable units (services, apps, databases)
- Technology choices per container
- Inter-container communication

#### Component Level
- Major modules within each container
- Component responsibilities
- Internal APIs and interfaces

#### Code Level (deep mode only)
- Critical classes and functions
- Key algorithms
- Data structures

### 5. Pattern Detection

Identify architectural patterns:

- **Structural**: MVC, MVVM, Hexagonal, Clean Architecture, Microservices
- **Communication**: REST, GraphQL, gRPC, Message Queues, Event-Driven
- **Data**: Repository, Unit of Work, CQRS, Event Sourcing
- **Anti-patterns**: God classes, circular deps, tight coupling, missing abstractions

### 6. Technical Debt Identification

Catalog shortcomings:

- Missing or outdated tests
- Stale dependencies
- Code duplication
- Incomplete error handling
- Missing documentation
- Security concerns
- Performance bottlenecks

### 7. Generate Output

Create the architecture documentation:

| File | Description |
|------|-------------|
| `.claude/architecture/CODEBASE.md` | Main architecture document |
| `.claude/architecture/TECH-DEBT.md` | Technical debt inventory |
| `.claude/architecture/components/*.md` | Per-component details (deep mode) |

## Output Format

Begin with a short control-plane reminder that Claude Code (ai-dev-kit plugin) orchestrates the workflow.
Encourage delegation to other agents via `/ai-dev-kit:delegate <provider> "<task>"` when they are better suited.

The main `CODEBASE.md` follows the template at:
`@.claude/ai-dev-kit/templates/architecture/CODEBASE.template.md`

## Usage Examples

```bash
# Standard exploration
/ai-dev-kit:explore-architecture

# Quick overview for initial assessment
/ai-dev-kit:explore-architecture quick

# Deep dive with component-level documentation
/ai-dev-kit:explore-architecture deep
```

## Skills Used

This command leverages:
- `c4-modeling` - C4 diagram syntax and best practices
- `codebase-analysis` - Pattern detection and dependency tracing

## Next Steps

After running this command, use `/ai-dev-kit:plan-roadmap` to generate a phased implementation plan based on the captured architecture context.
