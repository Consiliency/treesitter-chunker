#!/usr/bin/env python3
"""Build all configured tree-sitter grammars in parallel."""

import json
import logging
import multiprocessing
import sys
from pathlib import Path
from typing import List, Tuple

# Add parent directory to path to import chunker modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from chunker.grammar.manager import TreeSitterGrammarManager
from chunker.grammar.builder import GrammarBuilder

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def build_grammar(language: str) -> Tuple[str, bool, str]:
    """Build a single grammar.
    
    Args:
        language: Language name to build
        
    Returns:
        Tuple of (language, success, message)
    """
    try:
        logger.info(f"Building {language}...")
        
        # Create a new manager and builder for this process
        manager = TreeSitterGrammarManager()
        
        # Check if grammar info exists
        if not manager.get_grammar_info(language):
            # Load repository URL from config
            sources_path = Path(__file__).parent.parent / "config" / "grammar_sources.json"
            if sources_path.exists():
                with sources_path.open("r", encoding="utf-8") as f:
                    sources = json.load(f)
                    repo_url = sources.get(language)
                    if repo_url:
                        manager.add_grammar(language, repo_url)
                    else:
                        return (language, False, f"No repository URL found in config")
            else:
                return (language, False, "Grammar sources config not found")
        
        # Fetch if not already fetched
        if not manager.is_fetched(language):
            if not manager.fetch_grammar(language):
                return (language, False, "Failed to fetch grammar")
        
        # Build the grammar
        if manager.build_grammar(language):
            # Verify the output file exists
            output_dir = Path(__file__).parent.parent / "chunker" / "data" / "grammars" / "build"
            output_file = output_dir / f"{language}.so"
            if output_file.exists():
                return (language, True, f"Successfully built {output_file}")
            else:
                # Check alternate location (build directory)
                alt_output = Path(__file__).parent.parent / "build" / f"{language}.so"
                if alt_output.exists():
                    # Move to package location
                    output_dir.mkdir(parents=True, exist_ok=True)
                    alt_output.rename(output_file)
                    return (language, True, f"Successfully built and moved to {output_file}")
                return (language, False, "Built but output file not found")
        else:
            return (language, False, "Build failed")
            
    except Exception as e:
        return (language, False, f"Exception: {str(e)}")


def main():
    """Main function to build all grammars in parallel."""
    # Load grammar sources
    sources_path = Path(__file__).parent.parent / "config" / "grammar_sources.json"
    if not sources_path.exists():
        logger.error("Grammar sources config not found")
        sys.exit(1)
    
    with sources_path.open("r", encoding="utf-8") as f:
        sources = json.load(f)
    
    languages = list(sources.keys())
    logger.info(f"Found {len(languages)} languages to build")
    
    # Ensure output directory exists
    output_dir = Path(__file__).parent.parent / "chunker" / "data" / "grammars" / "build"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Check what's already built
    already_built = []
    for lang in languages:
        output_file = output_dir / f"{lang}.so"
        if output_file.exists():
            already_built.append(lang)
    
    if already_built:
        logger.info(f"Already built: {', '.join(already_built)}")
        # Remove already built from the list
        languages = [lang for lang in languages if lang not in already_built]
    
    if not languages:
        logger.info("All grammars are already built!")
        return
    
    logger.info(f"Building {len(languages)} grammars: {', '.join(languages)}")
    
    # Use multiprocessing to build in parallel
    # Limit workers to avoid overwhelming the system
    num_workers = min(multiprocessing.cpu_count(), 8, len(languages))
    logger.info(f"Using {num_workers} parallel workers")
    
    with multiprocessing.Pool(processes=num_workers) as pool:
        results = pool.map(build_grammar, languages)
    
    # Report results
    successful = []
    failed = []
    
    for language, success, message in results:
        if success:
            successful.append(language)
            logger.info(f"✓ {language}: {message}")
        else:
            failed.append((language, message))
            logger.error(f"✗ {language}: {message}")
    
    # Summary
    logger.info("="*60)
    logger.info(f"Build Summary:")
    logger.info(f"  Successful: {len(successful)}/{len(languages)}")
    if successful:
        logger.info(f"  Built: {', '.join(successful)}")
    if failed:
        logger.error(f"  Failed: {len(failed)}")
        for lang, msg in failed:
            logger.error(f"    - {lang}: {msg}")
    
    # Final count of all built grammars
    all_built = []
    for lang in sources.keys():
        output_file = output_dir / f"{lang}.so"
        if output_file.exists():
            all_built.append(lang)
    
    logger.info(f"Total grammars available: {len(all_built)}/{len(sources)}")
    
    # Exit with error if any failed
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()