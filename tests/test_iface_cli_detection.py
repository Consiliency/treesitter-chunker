"""IFACE: the CLI uses the ONE canonical extension→language map.

The CLI previously carried a divergent inline map that resolved `.ts` to
"javascript" (it is "typescript") and covered only 10 extensions, and it
returned [] silently on an unknown extension. It now delegates to
ZeroConfigAPI.EXTENSION_MAP and warns on an unknown extension.
"""

from chunker.auto import ZeroConfigAPI
from cli.main import process_file


def test_ts_resolves_to_typescript_everywhere():
    # The canonical map is the single source of truth.
    assert ZeroConfigAPI.EXTENSION_MAP.get(".ts") == "typescript"
    assert ZeroConfigAPI.EXTENSION_MAP.get(".tsx") == "typescript"


def test_cli_process_ts_file_uses_typescript(tmp_path):
    f = tmp_path / "a.ts"
    f.write_text("function greet(name: string): string {\n  return name;\n}\n")
    chunks = process_file(f, None)
    # Resolves via the canonical map (typescript) and produces chunks — the old
    # `.ts`→javascript map would still chunk, but with the wrong grammar.
    assert chunks, "CLI failed to resolve/chunk a .ts file"


def test_cli_unknown_extension_warns_not_silent(tmp_path, capsys):
    f = tmp_path / "b.unknownext"
    f.write_text("nothing parseable here\n")
    result = process_file(f, None)
    assert result == []
    err = capsys.readouterr().err
    assert (
        "no language mapping" in err and ".unknownext" in err
    ), "unknown extension must warn, not silently return []"
