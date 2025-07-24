# Blocked Grammar Fetches

Earlier attempts to run `scripts/fetch_grammars.py` failed because access
to GitHub was blocked.  The following grammars could not be cloned at the
time:

- Swift
- Kotlin
- Java
- PHP
- C#

With GitHub access restored we were able to fetch all grammars and build
`build/my-languages.so` successfully:

```bash
python scripts/fetch_grammars.py
python scripts/build_lib.py
```

