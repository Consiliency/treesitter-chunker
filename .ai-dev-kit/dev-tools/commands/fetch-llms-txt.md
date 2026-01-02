# Fetch llms.txt Command

Fetch and cache llms.txt files from libraries and frameworks.

## Background

The llms.txt standard provides AI-consumable documentation at predictable URLs:
- `https://docs.viperjuice.dev/llms.txt` - Main documentation
- `https://docs.viperjuice.dev/llms-full.txt` - Extended documentation

## Instructions

When asked to fetch llms.txt for a library:

### 1. Locate the llms.txt

Common locations:
- `https://{library-domain}/llms.txt`
- `https://{library-domain}/llms-full.txt`
- `https://docs.{library-domain}/llms.txt`
- Check the library's README for llms.txt links

### 2. Fetch the Content

```bash
curl -L https://docs.viperjuice.dev/llms.txt -o ai-docs/llms-txt/example.txt
```

Or use web fetch tools if available.

### 3. Validate the Content

- Check it's actually llms.txt format (not an error page)
- Verify it contains useful information
- Note the fetch date for future updates

### 4. Store in Standard Location

Save to: `ai-docs/llms-txt/{library-name}.txt`

Add a header comment:
```
# Source: https://docs.viperjuice.dev/llms.txt
# Fetched: YYYY-MM-DD
# Library: Example Library v1.2.3

[Original content below]
```

### 5. Create Companion Doc (Optional)

If the llms.txt is substantial, create a summary in the appropriate ai-docs subdirectory that references it.

## Known llms.txt Sources

| Library | URL |
|---------|-----|
| Anthropic | https://docs.anthropic.com/llms.txt |
| Vercel | https://vercel.com/llms.txt |
| [Add more as discovered] | |

## Example Usage

User: "Fetch the llms.txt for Prisma"

1. Try `https://prisma.io/llms.txt`
2. If not found, try `https://www.prisma.io/llms.txt`
3. If not found, search for "prisma llms.txt"
4. If found, save to `ai-docs/llms-txt/prisma.txt`
5. Report success or that no llms.txt was found

## When llms.txt Doesn't Exist

If a library doesn't have llms.txt:
1. Note this in the response
2. Offer to create a manual summary from their docs
3. Suggest the user request llms.txt from the library maintainers
