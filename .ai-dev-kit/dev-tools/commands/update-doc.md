# Update Documentation Command

Update or create documentation in the ai-docs directory.

## Instructions

When asked to update documentation:

### 1. Identify the Target

- Which doc needs updating? (framework, library, pattern, standard)
- Does it exist or need to be created?
- Is this a universal doc (`ai-docs/`) or project-specific override?

### 2. Gather Information

For frameworks/libraries:
- Check official documentation
- Look for llms.txt at the project's website
- Review changelog for recent changes
- Check for breaking changes in new versions

### 3. Structure the Content

Follow the template in `ai-docs/README.md`:

```markdown
# [Name]

## Overview
[Brief description and when to use]

## Key Concepts
[Core ideas and terminology]

## Common Patterns
[Code examples of good usage]

## Anti-Patterns
[What to avoid]

## Integration Notes
[Project-specific usage]

## References
[Official docs, llms.txt]
```

### 4. Validate

- Ensure code examples are correct
- Verify links work
- Check for outdated information
- Test any commands mentioned

### 5. Place Correctly

- Universal docs → `ai-docs/libraries/` (tracked in git)
- Project-specific → Document in `AGENTS.local.md` overrides

## Example Usage

User: "Update the React docs with React 19 patterns"

1. Check current React version in project
2. Review React 19 release notes
3. Update `ai-docs/libraries/react/_index.toon` and add pages under `ai-docs/libraries/react/pages/` with:
   - New hooks (use, useFormStatus, etc.)
   - Server Components patterns
   - Updated best practices
4. Add migration notes if applicable
