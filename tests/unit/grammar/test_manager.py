"""Unit tests for grammar manager."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from chunker.grammar import TreeSitterGrammarManager
from chunker.interfaces.grammar import GrammarInfo, GrammarStatus


class TestTreeSitterGrammarManager:
    """Test the TreeSitterGrammarManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path("/tmp/test_grammars")
        self.manager = TreeSitterGrammarManager(
            grammars_dir=self.temp_dir / "grammars",
            build_dir=self.temp_dir / "build"
        )
    
    def test_add_grammar(self):
        """Test adding a new grammar."""
        info = self.manager.add_grammar(
            "python",
            "https://github.com/tree-sitter/tree-sitter-python.git",
            "v0.20.0"
        )
        
        assert info.name == "python"
        assert info.repository_url == "https://github.com/tree-sitter/tree-sitter-python.git"
        assert info.commit_hash == "v0.20.0"
        assert info.status == GrammarStatus.NOT_FOUND
        
        # Check it's in the registry
        assert "python" in self.manager._grammars
    
    def test_add_duplicate_grammar(self):
        """Test adding a grammar that already exists."""
        # Add first time
        self.manager.add_grammar("python", "https://example.com/python.git")
        
        # Add again with different URL
        info = self.manager.add_grammar("python", "https://example.com/python-new.git")
        
        # Should update the existing entry
        assert info.repository_url == "https://example.com/python-new.git"
    
    @patch('subprocess.run')
    def test_fetch_grammar_clone(self, mock_run):
        """Test fetching a new grammar."""
        mock_run.return_value = Mock(returncode=0)
        
        # Add grammar first
        self.manager.add_grammar("go", "https://github.com/tree-sitter/tree-sitter-go.git")
        
        # Fetch it
        result = self.manager.fetch_grammar("go")
        
        assert result is True
        assert self.manager._grammars["go"].status == GrammarStatus.NOT_BUILT
        
        # Check git clone was called
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "git"
        assert args[1] == "clone"
        assert "tree-sitter-go.git" in args[2]
    
    @patch('subprocess.run')
    def test_fetch_grammar_update(self, mock_run):
        """Test updating an existing grammar."""
        mock_run.return_value = Mock(returncode=0)
        
        # Add grammar
        self.manager.add_grammar("ruby", "https://github.com/tree-sitter/tree-sitter-ruby.git")
        
        # Create the directory to simulate existing clone
        grammar_path = self.manager.grammars_dir / "tree-sitter-ruby"
        grammar_path.mkdir(parents=True, exist_ok=True)
        
        # Fetch it (should pull)
        result = self.manager.fetch_grammar("ruby")
        
        assert result is True
        
        # Check git pull was called
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "git"
        assert args[1] == "pull"
    
    def test_fetch_unknown_grammar(self):
        """Test fetching a grammar that wasn't added."""
        result = self.manager.fetch_grammar("unknown")
        assert result is False
    
    @patch('chunker.grammar.manager.build_language')
    def test_build_grammar(self, mock_build):
        """Test building a grammar."""
        mock_build.return_value = True
        
        # Add and set up grammar
        self.manager.add_grammar("java", "https://example.com/java.git")
        grammar_path = self.manager.grammars_dir / "tree-sitter-java"
        grammar_path.mkdir(parents=True, exist_ok=True)
        self.manager._grammars["java"].path = grammar_path
        self.manager._grammars["java"].status = GrammarStatus.NOT_BUILT
        
        # Build it
        result = self.manager.build_grammar("java")
        
        assert result is True
        assert self.manager._grammars["java"].status == GrammarStatus.READY
        
        # Check build function was called
        mock_build.assert_called_once_with("java", str(grammar_path), str(self.manager.build_dir))
    
    def test_list_grammars(self):
        """Test listing grammars."""
        # Add some grammars
        self.manager.add_grammar("python", "https://example.com/python.git")
        self.manager.add_grammar("go", "https://example.com/go.git")
        self.manager._grammars["python"].status = GrammarStatus.READY
        self.manager._grammars["go"].status = GrammarStatus.ERROR
        
        # List all
        all_grammars = self.manager.list_grammars()
        assert len(all_grammars) == 2
        
        # List by status
        ready = self.manager.list_grammars(GrammarStatus.READY)
        assert len(ready) == 1
        assert ready[0].name == "python"
        
        errors = self.manager.list_grammars(GrammarStatus.ERROR)
        assert len(errors) == 1
        assert errors[0].name == "go"
    
    def test_remove_grammar(self):
        """Test removing a grammar."""
        # Add grammar
        self.manager.add_grammar("rust", "https://example.com/rust.git")
        
        # Create fake source directory
        grammar_path = self.manager.grammars_dir / "tree-sitter-rust"
        grammar_path.mkdir(parents=True, exist_ok=True)
        (grammar_path / "parser.c").touch()
        self.manager._grammars["rust"].path = grammar_path
        
        # Remove it
        result = self.manager.remove_grammar("rust")
        
        assert result is True
        assert "rust" not in self.manager._grammars
        assert not grammar_path.exists()
    
    @patch('chunker.parser.get_parser')
    def test_validate_grammar(self, mock_get_parser):
        """Test validating a grammar."""
        # Set up mock parser
        mock_parser = Mock()
        mock_tree = Mock()
        mock_tree.root_node = Mock()
        mock_parser.parse.return_value = mock_tree
        mock_get_parser.return_value = mock_parser
        
        # Add ready grammar
        self.manager.add_grammar("python", "https://example.com/python.git")
        self.manager._grammars["python"].status = GrammarStatus.READY
        
        # Validate
        is_valid, error = self.manager.validate_grammar("python")
        
        assert is_valid is True
        assert error is None
        
        # Check parser was used
        mock_get_parser.assert_called_once_with("python")
        mock_parser.parse.assert_called_once()
    
    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        # Add some grammars
        self.manager.add_grammar("python", "https://example.com/python.git", "v1.0")
        self.manager.add_grammar("go", "https://example.com/go.git")
        self.manager._grammars["python"].status = GrammarStatus.READY
        self.manager._grammars["go"].error = "Build failed"
        
        # Save config
        self.manager._save_config()
        
        # Create new manager and check it loads the config
        new_manager = TreeSitterGrammarManager(
            grammars_dir=self.temp_dir / "grammars",
            build_dir=self.temp_dir / "build"
        )
        
        assert len(new_manager._grammars) == 2
        assert new_manager._grammars["python"].commit_hash == "v1.0"
        assert new_manager._grammars["python"].status == GrammarStatus.READY
        assert new_manager._grammars["go"].error == "Build failed"