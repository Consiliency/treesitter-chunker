"""Repository processing module for chunking entire codebases."""

from .processor import RepoProcessor, GitAwareRepoProcessor
from .patterns import GitignoreMatcher, load_gitignore_patterns

# Export with Impl names for backward compatibility
RepoProcessorImpl = RepoProcessor
GitAwareProcessorImpl = GitAwareRepoProcessor

__all__ = [
    "RepoProcessor", 
    "GitAwareRepoProcessor",
    "RepoProcessorImpl",
    "GitAwareProcessorImpl",
    "GitignoreMatcher",
    "load_gitignore_patterns"
]