"""Real-parser contract for a local interactive debug REPL session."""

from pathlib import Path

from chunker.debug.interactive.repl import Confirm, DebugREPL, Prompt


FIXTURE = Path(__file__).parent / "fixtures/boundary_ir/repos/python/app/service.py"


def test_repl_loads_parses_and_saves_local_fixture(monkeypatch, tmp_path, capsys):
    output = tmp_path / "debug-session.md"
    commands = iter((f"load {FIXTURE}", f"save {output}", "quit"))
    monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: next(commands))
    monkeypatch.setattr(Confirm, "ask", lambda *args, **kwargs: True)

    repl = DebugREPL()
    repl.start()

    source = FIXTURE.read_text(encoding="utf-8")
    assert repl.current_file == str(FIXTURE)
    assert repl.current_code == source
    assert repl.current_language == "python"
    assert repl.node_explorer is not None
    assert not repl.node_explorer.parser.parse(
        source.encode("utf-8")
    ).root_node.has_error
    saved = output.read_text(encoding="utf-8")
    assert f"# File: {FIXTURE}" in saved
    assert source in saved
    assert f"load {FIXTURE}" in saved
    assert f"save {output}" in saved
    terminal = capsys.readouterr().out
    assert "Loaded:" in terminal
    assert "Session saved to:" in terminal
