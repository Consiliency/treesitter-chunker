from chunker.core import chunk_text


def test_stability_across_edits():
    SOURCE = """\
def stable_function():
    pass
"""
    SOURCE2 = """\

def stable_function():
    pass
"""
    chunks1 = chunk_text(SOURCE, "python", "stability.py")
    chunks2 = chunk_text(SOURCE2, "python", "stability.py")
    print(chunks1[0].chunk_id)
    print(chunks2[0].chunk_id)


test_stability_across_edits()
