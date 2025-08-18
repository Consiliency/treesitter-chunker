# Phase 1.6a: Parallel Grammar Compilation Management

You are the Managing Agent for Phase 1.6a of the treesitter-chunker project. Your role is to coordinate 5 sub-agents to compile 30+ language grammars in parallel without file conflicts.

## Your Responsibilities:
- Coordinate sub-agents to avoid file conflicts
- Track progress and completion
- Report final status to main agent
- NO file editing or grammar compilation yourself

## Sub-Agent Assignments:

### Sub-Agent 1: Core Languages
- Languages: Go, C, C++, Java, C#, TypeScript
- Files to create: scripts/build_core_languages.py
- Output directory: chunker/data/grammars/build/
- Output files: go.so, c.so, cpp.so, java.so, csharp.so, typescript.so

### Sub-Agent 2: Web Languages  
- Languages: Ruby, PHP, Kotlin, Swift, Dart
- Files to create: scripts/build_web_languages.py
- Output directory: chunker/data/grammars/build/
- Output files: ruby.so, php.so, kotlin.so, swift.so, dart.so

### Sub-Agent 3: Functional Languages
- Languages: Haskell, OCaml, Scala, Elixir, Clojure
- Files to create: scripts/build_functional_languages.py
- Output directory: chunker/data/grammars/build/
- Output files: haskell.so, ocaml.so, scala.so, elixir.so, clojure.so

### Sub-Agent 4: Specialized Languages
- Languages: MATLAB, Julia, R, SQL, NASM, Vue, Svelte
- Files to create: scripts/build_specialized_languages.py
- Output directory: chunker/data/grammars/build/
- Output files: matlab.so, julia.so, r.so, sql.so, nasm.so, vue.so, svelte.so

### Sub-Agent 5: Integration & Testing
- Languages: Python, JavaScript, Rust (already working) + validation
- Files to create: scripts/validate_all_grammars.py, tests/test_grammar_integration.py
- Output directory: chunker/data/grammars/build/ (validation only)
- Output files: Validation reports and test results

## Critical Rules:
1. Each sub-agent works on COMPLETELY SEPARATE files
2. NO sub-agent touches files assigned to other sub-agents
3. NO sub-agent touches error handling files (main agent's responsibility)
4. Each sub-agent creates their own build script and handles their own languages
5. Output files go to chunker/data/grammars/build/ but each sub-agent only touches their assigned .so files

## Expected Outcome:
- 30+ compiled grammar libraries (.so files)
- 5 separate build scripts for different language categories
- Integration testing and validation
- All sub-agents complete without file conflicts

## Next Steps:
1. Assign sub-agents to their language categories
2. Monitor progress and ensure no file conflicts
3. Report completion status to main agent
4. Hand off to main agent for Phase 1.6b (error handling)

---

## Sub-Agent 1: Core Languages

You are Sub-Agent 1 for Phase 1.6a. Your task is to compile grammar libraries for core programming languages.

## Your Assignment:
- Languages: Go, C, C++, Java, C#, TypeScript
- Create: scripts/build_core_languages.py
- Output: chunker/data/grammars/build/go.so, c.so, cpp.so, java.so, csharp.so, typescript.so

## Files You CAN Touch:
- scripts/build_core_languages.py (create this file)
- chunker/data/grammars/build/go.so (output)
- chunker/data/grammars/build/c.so (output)
- chunker/data/grammars/build/cpp.so (output)
- chunker/data/grammars/build/java.so (output)
- chunker/data/grammars/build/csharp.so (output)
- chunker/data/grammars/build/typescript.so (output)

## Files You CANNOT Touch:
- Any other build scripts (assigned to other sub-agents)
- Any error handling files (main agent's responsibility)
- Any other language .so files (assigned to other sub-agents)
- Any core project files (main agent's responsibility)

## Your Process:
1. Create scripts/build_core_languages.py
2. Use existing tree-sitter repositories in grammars/ directory
3. Compile each language to .so library
4. Place outputs in chunker/data/grammars/build/
5. Test that each .so file loads correctly
6. Report completion status

## Expected Output:
- 6 compiled grammar libraries (.so files)
- 1 build script for core languages
- All languages successfully compiled and loadable

Begin work now.

---

## Sub-Agent 2: Web Languages

You are Sub-Agent 2 for Phase 1.6a. Your task is to compile grammar libraries for web and mobile programming languages.

## Your Assignment:
- Languages: Ruby, PHP, Kotlin, Swift, Dart
- Create: scripts/build_web_languages.py
- Output: chunker/data/grammars/build/ruby.so, php.so, kotlin.so, swift.so, dart.so

## Files You CAN Touch:
- scripts/build_web_languages.py (create this file)
- chunker/data/grammars/build/ruby.so (output)
- chunker/data/grammars/build/php.so (output)
- chunker/data/grammars/build/kotlin.so (output)
- chunker/data/grammars/build/swift.so (output)
- chunker/data/grammars/build/dart.so (output)

## Files You CANNOT Touch:
- Any other build scripts (assigned to other sub-agents)
- Any error handling files (main agent's responsibility)
- Any other language .so files (assigned to other sub-agents)
- Any core project files (main agent's responsibility)

## Your Process:
1. Create scripts/build_web_languages.py
2. Use existing tree-sitter repositories in grammars/ directory
3. Compile each language to .so library
4. Place outputs in chunker/data/grammars/build/
5. Test that each .so file loads correctly
6. Report completion status

## Expected Output:
- 5 compiled grammar libraries (.so files)
- 1 build script for web languages
- All languages successfully compiled and loadable

Begin work now.

---

## Sub-Agent 3: Functional Languages

You are Sub-Agent 3 for Phase 1.6a. Your task is to compile grammar libraries for functional programming languages.

## Your Assignment:
- Languages: Haskell, OCaml, Scala, Elixir, Clojure
- Create: scripts/build_functional_languages.py
- Output: chunker/data/grammars/build/haskell.so, ocaml.so, scala.so, elixir.so, clojure.so

## Files You CAN Touch:
- scripts/build_functional_languages.py (create this file)
- chunker/data/grammars/build/haskell.so (output)
- chunker/data/grammars/build/ocaml.so (output)
- chunker/data/grammars/build/scala.so (output)
- chunker/data/grammars/build/elixir.so (output)
- chunker/data/grammars/build/clojure.so (output)

## Files You CANNOT Touch:
- Any other build scripts (assigned to other sub-agents)
- Any error handling files (main agent's responsibility)
- Any other language .so files (assigned to other sub-agents)
- Any core project files (main agent's responsibility)

## Your Process:
1. Create scripts/build_functional_languages.py
2. Use existing tree-sitter repositories in grammars/ directory
3. Compile each language to .so library
4. Place outputs in chunker/data/grammars/build/
5. Test that each .so file loads correctly
6. Report completion status

## Expected Output:
- 5 compiled grammar libraries (.so files)
- 1 build script for functional languages
- All languages successfully compiled and loadable

Begin work now.

---

## Sub-Agent 4: Specialized Languages

You are Sub-Agent 4 for Phase 1.6a. Your task is to compile grammar libraries for specialized and domain-specific languages.

## Your Assignment:
- Languages: MATLAB, Julia, R, SQL, NASM, Vue, Svelte
- Create: scripts/build_specialized_languages.py
- Output: chunker/data/grammars/build/matlab.so, julia.so, r.so, sql.so, nasm.so, vue.so, svelte.so

## Files You CAN Touch:
- scripts/build_specialized_languages.py (create this file)
- chunker/data/grammars/build/matlab.so (output)
- chunker/data/grammars/build/julia.so (output)
- chunker/data/grammars/build/r.so (output)
- chunker/data/grammars/build/sql.so (output)
- chunker/data/grammars/build/nasm.so (output)
- chunker/data/grammars/build/vue.so (output)
- chunker/data/grammars/build/svelte.so (output)

## Files You CANNOT Touch:
- Any other build scripts (assigned to other sub-agents)
- Any error handling files (main agent's responsibility)
- Any other language .so files (assigned to other sub-agents)
- Any core project files (main agent's responsibility)

## Your Process:
1. Create scripts/build_specialized_languages.py
2. Use existing tree-sitter repositories in grammars/ directory
3. Compile each language to .so library
4. Place outputs in chunker/data/grammars/build/
5. Test that each .so file loads correctly
6. Report completion status

## Expected Output:
- 8 compiled grammar libraries (.so files)
- 1 build script for specialized languages
- All languages successfully compiled and loadable

Begin work now.

---

## Sub-Agent 5: Integration & Testing

You are Sub-Agent 5 for Phase 1.6a. Your task is to validate all compiled grammars and ensure integration works correctly.

## Your Assignment:
- Validate: All compiled grammar libraries
- Create: scripts/validate_all_grammars.py, tests/test_grammar_integration.py
- Test: Python, JavaScript, Rust (already working) + all newly compiled grammars

## Files You CAN Touch:
- scripts/validate_all_grammars.py (create this file)
- tests/test_grammar_integration.py (create this file)
- Any test output files (logs, reports)

## Files You CANNOT Touch:
- Any build scripts (assigned to other sub-agents)
- Any error handling files (main agent's responsibility)
- Any .so files (created by other sub-agents)
- Any core project files (main agent's responsibility)

## Your Process:
1. Create validation and testing scripts
2. Wait for all sub-agents to complete grammar compilation
3. Validate that all .so files load correctly
4. Test integration with existing language support
5. Run comprehensive tests against all grammars
6. Report validation results and any issues

## Expected Output:
- 2 testing/validation scripts
- Comprehensive validation report
- Integration test results
- List of any issues or failures

Begin work now.

---

## Begin coordination now.
