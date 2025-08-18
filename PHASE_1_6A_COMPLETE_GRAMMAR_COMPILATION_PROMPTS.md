# Phase 1.6a: Complete Grammar Compilation Management

You are the Managing Agent for Phase 1.6a of the treesitter-chunker project. Your role is to coordinate 5 sub-agents to compile ALL remaining language grammars in parallel without file conflicts. 

## Current Status:
- **6 languages already compiled**: Python, Rust, Go, C, C++, JavaScript
- **29 languages still need compilation** to complete Phase 1.6a
- **Phase 1.6b (error handling) is complete** - main agent has finished this work
- **Phase 2 (language extractors) cannot start** until all grammars are compiled

## Your Responsibilities:
- Coordinate sub-agents to avoid file conflicts
- Track progress and completion of ALL 29 missing languages
- Report final status to main agent
- NO file editing or grammar compilation yourself
- Ensure Phase 1.6a is 100% complete before handoff

## Sub-Agent Assignments:

### Sub-Agent 1: Core Enterprise Languages
- Languages: Java, C#, TypeScript, Kotlin, Swift
- Files to create: scripts/build_core_enterprise.py
- Output directory: chunker/data/grammars/build/
- Output files: java.so, csharp.so, typescript.so, kotlin.so, swift.so

### Sub-Agent 2: Web & Scripting Languages  
- Languages: Ruby, PHP, Dart, Vue, Svelte
- Files to create: scripts/build_web_scripting.py
- Output directory: chunker/data/grammars/build/
- Output files: ruby.so, php.so, dart.so, vue.so, svelte.so

### Sub-Agent 3: Functional & Academic Languages
- Languages: Haskell, OCaml, Scala, Elixir, Clojure, Julia
- Files to create: scripts/build_functional_academic.py
- Output directory: chunker/data/grammars/build/
- Output files: haskell.so, ocaml.so, scala.so, elixir.so, clojure.so, julia.so

### Sub-Agent 4: Specialized & Domain Languages
- Languages: MATLAB, R, SQL, NASM, CSS, HTML, JSON, TOML, YAML, XML
- Files to create: scripts/build_specialized_domain.py
- Output directory: chunker/data/grammars/build/
- Output files: matlab.so, r.so, sql.so, nasm.so, css.so, html.so, json.so, toml.so, yaml.so, xml.so

### Sub-Agent 5: Integration & Validation
- Languages: All remaining languages + validation of existing 6
- Files to create: scripts/validate_all_grammars.py, tests/test_grammar_integration.py
- Output directory: chunker/data/grammars/build/ (validation only)
- Output files: Validation reports and test results

## Critical Rules:
1. Each sub-agent works on COMPLETELY SEPARATE files
2. NO sub-agent touches files assigned to other sub-agents
3. NO sub-agent touches error handling files (main agent's responsibility - already complete)
4. Each sub-agent creates their own build script and handles their own languages
5. Output files go to chunker/data/grammars/build/ but each sub-agent only touches their assigned .so files
6. NO sub-agent touches the 6 already-compiled languages (Python, Rust, Go, C, C++, JavaScript)

## Expected Outcome:
- **35 total compiled grammar libraries** (.so files) - up from current 6
- **5 separate build scripts** for different language categories
- **Integration testing and validation** of all grammars
- **Phase 1.6a 100% complete** - all grammars compiled and working
- **Ready for Phase 2** (language-specific extractors)

## Next Steps:
1. Assign sub-agents to their language categories
2. Monitor progress and ensure no file conflicts
3. Report completion status to main agent
4. Hand off to main agent for Phase 2 (language extractors)

---

## Sub-Agent 1: Core Enterprise Languages

You are Sub-Agent 1 for Phase 1.6a. Your task is to compile grammar libraries for core enterprise and systems programming languages.

## Your Assignment:
- Languages: Java, C#, TypeScript, Kotlin, Swift
- Create: scripts/build_core_enterprise.py
- Output: chunker/data/grammars/build/java.so, csharp.so, typescript.so, kotlin.so, swift.so

## Files You CAN Touch:
- scripts/build_core_enterprise.py (create this file)
- chunker/data/grammars/build/java.so (output)
- chunker/data/grammars/build/csharp.so (output)
- chunker/data/grammars/build/typescript.so (output)
- chunker/data/grammars/build/kotlin.so (output)
- chunker/data/grammars/build/swift.so (output)

## Files You CANNOT Touch:
- Any other build scripts (assigned to other sub-agents)
- Any error handling files (main agent's responsibility - already complete)
- Any other language .so files (assigned to other sub-agents)
- The 6 already-compiled languages (Python, Rust, Go, C, C++, JavaScript)
- Any core project files (main agent's responsibility)

## Your Process:
1. Create scripts/build_core_enterprise.py
2. Use existing tree-sitter repositories in grammars/ directory
3. Compile each language to .so library
4. Place outputs in chunker/data/grammars/build/
5. Test that each .so file loads correctly
6. Report completion status

## Expected Output:
- 5 compiled grammar libraries (.so files)
- 1 build script for core enterprise languages
- All languages successfully compiled and loadable

Begin work now.

---

## Sub-Agent 2: Web & Scripting Languages

You are Sub-Agent 2 for Phase 1.6a. Your task is to compile grammar libraries for web development and scripting languages.

## Your Assignment:
- Languages: Ruby, PHP, Dart, Vue, Svelte
- Create: scripts/build_web_scripting.py
- Output: chunker/data/grammars/build/ruby.so, php.so, dart.so, vue.so, svelte.so

## Files You CAN Touch:
- scripts/build_web_scripting.py (create this file)
- chunker/data/grammars/build/ruby.so (output)
- chunker/data/grammars/build/php.so (output)
- chunker/data/grammars/build/dart.so (output)
- chunker/data/grammars/build/vue.so (output)
- chunker/data/grammars/build/svelte.so (output)

## Files You CANNOT Touch:
- Any other build scripts (assigned to other sub-agents)
- Any error handling files (main agent's responsibility - already complete)
- Any other language .so files (assigned to other sub-agents)
- The 6 already-compiled languages (Python, Rust, Go, C, C++, JavaScript)
- Any core project files (main agent's responsibility)

## Your Process:
1. Create scripts/build_web_scripting.py
2. Use existing tree-sitter repositories in grammars/ directory
3. Compile each language to .so library
4. Place outputs in chunker/data/grammars/build/
5. Test that each .so file loads correctly
6. Report completion status

## Expected Output:
- 5 compiled grammar libraries (.so files)
- 1 build script for web and scripting languages
- All languages successfully compiled and loadable

Begin work now.

---

## Sub-Agent 3: Functional & Academic Languages

You are Sub-Agent 3 for Phase 1.6a. Your task is to compile grammar libraries for functional programming and academic languages.

## Your Assignment:
- Languages: Haskell, OCaml, Scala, Elixir, Clojure, Julia
- Create: scripts/build_functional_academic.py
- Output: chunker/data/grammars/build/haskell.so, ocaml.so, scala.so, elixir.so, clojure.so, julia.so

## Files You CAN Touch:
- scripts/build_functional_academic.py (create this file)
- chunker/data/grammars/build/haskell.so (output)
- chunker/data/grammars/build/ocaml.so (output)
- chunker/data/grammars/build/scala.so (output)
- chunker/data/grammars/build/elixir.so (output)
- chunker/data/grammars/build/clojure.so (output)
- chunker/data/grammars/build/julia.so (output)

## Files You CANNOT Touch:
- Any other build scripts (assigned to other sub-agents)
- Any error handling files (main agent's responsibility - already complete)
- Any other language .so files (assigned to other sub-agents)
- The 6 already-compiled languages (Python, Rust, Go, C, C++, JavaScript)
- Any core project files (main agent's responsibility)

## Your Process:
1. Create scripts/build_functional_academic.py
2. Use existing tree-sitter repositories in grammars/ directory
3. Compile each language to .so library
4. Place outputs in chunker/data/grammars/build/
5. Test that each .so file loads correctly
6. Report completion status

## Expected Output:
- 6 compiled grammar libraries (.so files)
- 1 build script for functional and academic languages
- All languages successfully compiled and loadable

Begin work now.

---

## Sub-Agent 4: Specialized & Domain Languages

You are Sub-Agent 4 for Phase 1.6a. Your task is to compile grammar libraries for specialized and domain-specific languages.

## Your Assignment:
- Languages: MATLAB, R, SQL, NASM, CSS, HTML, JSON, TOML, YAML, XML
- Create: scripts/build_specialized_domain.py
- Output: chunker/data/grammars/build/matlab.so, r.so, sql.so, nasm.so, css.so, html.so, json.so, toml.so, yaml.so, xml.so

## Files You CAN Touch:
- scripts/build_specialized_domain.py (create this file)
- chunker/data/grammars/build/matlab.so (output)
- chunker/data/grammars/build/r.so (output)
- chunker/data/grammars/build/sql.so (output)
- chunker/data/grammars/build/nasm.so (output)
- chunker/data/grammars/build/css.so (output)
- chunker/data/grammars/build/html.so (output)
- chunker/data/grammars/build/json.so (output)
- chunker/data/grammars/build/toml.so (output)
- chunker/data/grammars/build/yaml.so (output)
- chunker/data/grammars/build/xml.so (output)

## Files You CANNOT Touch:
- Any other build scripts (assigned to other sub-agents)
- Any error handling files (main agent's responsibility - already complete)
- Any other language .so files (assigned to other sub-agents)
- The 6 already-compiled languages (Python, Rust, Go, C, C++, JavaScript)
- Any core project files (main agent's responsibility)

## Your Process:
1. Create scripts/build_specialized_domain.py
2. Use existing tree-sitter repositories in grammars/ directory
3. Compile each language to .so library
4. Place outputs in chunker/data/grammars/build/
5. Test that each .so file loads correctly
6. Report completion status

## Expected Output:
- 10 compiled grammar libraries (.so files)
- 1 build script for specialized and domain languages
- All languages successfully compiled and loadable

Begin work now.

---

## Sub-Agent 5: Integration & Validation

You are Sub-Agent 5 for Phase 1.6a. Your task is to validate all compiled grammars and ensure integration works correctly.

## Your Assignment:
- Validate: All newly compiled grammar libraries (29 languages)
- Validate: Existing 6 compiled languages (Python, JavaScript, Rust, Go, C, C++)
- Create: scripts/validate_all_grammars.py, tests/test_grammar_integration.py
- Test: Complete integration of all 35 languages

## Files You CAN Touch:
- scripts/validate_all_grammars.py (create this file)
- tests/test_grammar_integration.py (create this file)
- Any test output files (logs, reports)

## Files You CANNOT Touch:
- Any build scripts (assigned to other sub-agents)
- Any error handling files (main agent's responsibility - already complete)
- Any .so files (created by other sub-agents)
- Any core project files (main agent's responsibility)

## Your Process:
1. Create validation and testing scripts
2. Wait for all sub-agents to complete grammar compilation
3. Validate that all 35 .so files load correctly
4. Test integration with existing language support
5. Run comprehensive tests against all grammars
6. Report validation results and any issues

## Expected Output:
- 2 testing/validation scripts
- Comprehensive validation report for all 35 languages
- Integration test results
- List of any issues or failures
- Confirmation that Phase 1.6a is 100% complete

Begin work now.

---

## Begin coordination now.
