"""Refresh explicit consumer test-data directories; never a production fallback."""

import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, nargs="+")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    driver = (root / "tools/governed_scope.py").read_bytes()
    recipe = (root / "tests/fixtures/governed_scope/recipe.py").read_bytes()
    binding = {
        "kind": "test_only_transport",
        "source": "Consiliency/treesitter-chunker:tools/governed_scope.py",
        "sha256": hashlib.sha256(driver).hexdigest(),
        "recipe_sha256": hashlib.sha256(recipe).hexdigest(),
        "production_fallback": False,
    }
    for destination in args.destination:
        if (
            not destination.is_dir()
            or destination.name != "governed_scope"
            or destination.parent.name != "fixtures"
        ):
            raise ValueError(
                "explicit existing governed_scope fixture directory required"
            )
        (destination / "governed_scope.py").write_bytes(driver)
        (destination / "recipe.py").write_bytes(recipe)
        (destination / "driver-binding.json").write_text(
            json.dumps(binding, indent=2) + "\n"
        )


if __name__ == "__main__":
    main()
