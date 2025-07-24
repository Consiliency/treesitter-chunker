"""Repository processing module for chunking entire codebases."""

from .patterns import GitignoreMatcher, load_gitignore_patterns
from .processor import GitAwareRepoProcessor, RepoProcessor

# Export with Impl names for backward compatibility
RepoProcessorImpl = RepoProcessor
GitAwareProcessorImpl = GitAwareRepoProcessor

__all__ = [
    "GitAwareProcessorImpl",
    "GitAwareRepoProcessor",
    "GitignoreMatcher",
    "RepoProcessor",
    "RepoProcessorImpl",
    "load_gitignore_patterns",
]
