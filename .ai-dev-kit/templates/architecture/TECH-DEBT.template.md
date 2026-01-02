# Technical Debt Inventory

> **Project**: [Project Name]
> **Generated**: YYYY-MM-DD
> **Agent**: architecture-explorer

## Summary

| Category | Critical | High | Medium | Low | Total |
|----------|----------|------|--------|-----|-------|
| Code Quality | 0 | 0 | 0 | 0 | 0 |
| Testing | 0 | 0 | 0 | 0 | 0 |
| Dependencies | 0 | 0 | 0 | 0 | 0 |
| Documentation | 0 | 0 | 0 | 0 | 0 |
| Architecture | 0 | 0 | 0 | 0 | 0 |
| Security | 0 | 0 | 0 | 0 | 0 |
| **Total** | **0** | **0** | **0** | **0** | **0** |

## Severity Definitions

| Severity | Definition | Action Timeline |
|----------|------------|-----------------|
| **Critical** | Blocks development, security vulnerability, data loss risk | Immediate |
| **High** | Significant developer friction, reliability concerns | Next sprint |
| **Medium** | Noticeable inefficiency, maintainability concerns | Plan to address |
| **Low** | Minor inconvenience, nice-to-have improvements | Opportunistic |

---

## Code Quality Issues

### Critical

*None identified*

### High

#### [DEBT-001] [Issue Title]
- **Location**: `path/to/file.ts:123`
- **Description**: [What the issue is]
- **Impact**: [How it affects development/runtime]
- **Remediation**: [How to fix it]
- **Effort**: Small/Medium/Large
- **Related**: [Related debt items or issues]

### Medium

#### [DEBT-002] [Issue Title]
- **Location**: `path/to/file.ts`
- **Description**: [What the issue is]
- **Impact**: [How it affects development/runtime]
- **Remediation**: [How to fix it]
- **Effort**: Small/Medium/Large

### Low

*None identified*

---

## Testing Issues

### Critical

*None identified*

### High

#### [DEBT-010] Low Test Coverage in [Area]
- **Location**: `path/to/module/`
- **Current Coverage**: [X%]
- **Target Coverage**: [Y%]
- **Missing Tests**:
  - [ ] [Component/function needing tests]
  - [ ] [Component/function needing tests]
- **Effort**: Medium/Large

### Medium

#### [DEBT-011] Missing Integration Tests
- **Location**: `path/to/integration/`
- **Description**: [What flows are untested]
- **Remediation**: Add integration tests for [specific flows]
- **Effort**: Medium

### Low

*None identified*

---

## Dependency Issues

### Critical

#### [DEBT-020] Security Vulnerability in [Package]
- **Package**: `package-name@version`
- **Vulnerability**: [CVE or description]
- **Severity**: Critical
- **Fix**: Upgrade to `package-name@fixed-version`
- **Breaking Changes**: [Yes/No - details if yes]

### High

#### [DEBT-021] Outdated Major Version: [Package]
- **Current**: `package@old-version`
- **Latest**: `package@new-version`
- **Behind by**: [N] major versions
- **Migration Guide**: [Link if available]
- **Breaking Changes**: [Summary of breaking changes]
- **Effort**: Medium/Large

### Medium

#### [DEBT-022] Deprecated Package: [Package]
- **Package**: `package-name`
- **Deprecated Since**: [Date/Version]
- **Replacement**: `new-package-name`
- **Migration Effort**: Small/Medium

### Low

#### [DEBT-023] Minor Version Updates Available
- `package1`: current → latest
- `package2`: current → latest
- `package3`: current → latest

---

## Documentation Issues

### High

#### [DEBT-030] Missing README
- **Location**: Project root
- **Impact**: New developers cannot onboard
- **Remediation**: Create comprehensive README with setup instructions

#### [DEBT-031] Outdated API Documentation
- **Location**: `docs/api/`
- **Issue**: Documentation doesn't match current API
- **Stale Sections**: [List of outdated sections]

### Medium

#### [DEBT-032] Missing Code Comments in Complex Logic
- **Locations**:
  - `path/to/complex/file.ts` - [Function/section]
  - `path/to/another/file.ts` - [Function/section]
- **Impact**: Difficult to understand and maintain

### Low

*None identified*

---

## Architecture Issues

### Critical

*None identified*

### High

#### [DEBT-040] Circular Dependency
- **Cycle**: `A → B → C → A`
- **Files**:
  - `path/to/a.ts`
  - `path/to/b.ts`
  - `path/to/c.ts`
- **Impact**: Build issues, tight coupling, testing difficulty
- **Remediation**: Extract shared interface, use dependency injection

#### [DEBT-041] God Class: [ClassName]
- **Location**: `path/to/file.ts`
- **Size**: [N] lines, [M] methods
- **Responsibilities**: [List of too many responsibilities]
- **Remediation**: Split into focused classes by responsibility

### Medium

#### [DEBT-042] Missing Abstraction
- **Location**: `path/to/module/`
- **Pattern**: [Repeated code pattern]
- **Occurrences**: [N] places
- **Remediation**: Extract to shared utility/service

#### [DEBT-043] Inconsistent Error Handling
- **Location**: Throughout codebase
- **Issue**: Mix of try/catch, .catch(), and unhandled rejections
- **Remediation**: Establish and apply consistent error handling pattern

### Low

*None identified*

---

## Security Issues

### Critical

*None identified* (or list any found)

### High

#### [DEBT-050] Hardcoded Credentials
- **Location**: `path/to/file.ts:123`
- **Type**: [API key, password, token]
- **Remediation**: Move to environment variables, rotate credentials

#### [DEBT-051] Missing Input Validation
- **Location**: `path/to/endpoint.ts`
- **Endpoint**: [Route/function]
- **Risk**: [Injection, XSS, etc.]
- **Remediation**: Add input validation using [library/method]

### Medium

#### [DEBT-052] Overly Permissive CORS
- **Location**: `path/to/cors/config.ts`
- **Current**: `*` (allow all)
- **Remediation**: Restrict to specific allowed origins

### Low

*None identified*

---

## Quick Wins

Items that can be addressed with minimal effort:

| ID | Issue | Effort | Impact |
|----|-------|--------|--------|
| DEBT-023 | Update minor versions | 1 hour | Low risk updates |
| DEBT-032 | Add comments to [file] | 30 min | Better maintainability |

---

## Recommended Priority Order

Based on impact and effort, address in this order:

1. **Critical Security**: DEBT-020, DEBT-050
2. **High Architecture**: DEBT-040, DEBT-041
3. **High Dependencies**: DEBT-021
4. **High Testing**: DEBT-010
5. **Medium items**: Address during related feature work

---

## Debt Addressed in Roadmap

The following items are planned for remediation in [ROADMAP.md](../../../specs/ROADMAP.md):

| Debt ID | Roadmap Phase | Notes |
|---------|---------------|-------|
| DEBT-XXX | Phase N | [How it will be addressed] |

---

## Appendix: Detection Methods

| Category | Tools/Methods Used |
|----------|-------------------|
| Code Quality | [ESLint, manual review, complexity analysis] |
| Testing | [Coverage reports, test inventory] |
| Dependencies | [npm audit, npm outdated, manual review] |
| Security | [npm audit, manual review, OWASP checklist] |
| Architecture | [Import analysis, file size analysis, pattern detection] |

---

*This document was generated by the architecture-explorer agent. Manual verification recommended for security-sensitive items.*
