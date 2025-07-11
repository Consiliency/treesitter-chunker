# Tree‑sitter Chunker

Semantic **code chunker** built on [Tree‑sitter](https://tree-sitter.github.io/) to slice source
files into function, class, and logical blocks suitable for:

* **Embedding / vector search** pipelines
* **Code graph** construction (call / reference edges)
* Any downstream static‑analysis or context‑retrieval use‑case

---

## Quick start

```bash
# Clone repo & enter
git clone git@github.com:Consiliency/treesitter-chunker.git
cd treesitter-chunker

# Bootstrap dev env (requires `uv`)
./dev.sh                 # builds venv & installs deps
python scripts/fetch_grammars.py
python cli/main.py chunk examples/example.py -l python
