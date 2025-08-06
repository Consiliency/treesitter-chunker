"""Tests for Go language support."""

import pytest

from chunker.core import chunk_text
from chunker.languages import language_config_registry
from chunker.parser import list_languages


class TestGoLanguageSupport:
    """Test Go language chunking."""

    @staticmethod
    @pytest.mark.skipif("go" not in list_languages(), reason="Go grammar not available")
    def test_go_function_chunking():
        """Test chunking Go functions."""
        code = """
package main

import "fmt"

// Regular function
func greet(name string) string {
    return fmt.Sprintf("Hello, %s!", name)
}

// Function with multiple returns
func divide(a, b float64) (float64, error) {
    if b == 0 {
        return 0, fmt.Errorf("division by zero")
    }
    return a / b, nil
}

// Main function
func main() {
    fmt.Println(greet("World"))
}
"""
        chunks = chunk_text(code, "go", "main.go")
        assert len(chunks) == 3
        func_names = [
            c.parent_context for c in chunks if c.node_type == "function_declaration"
        ]
        assert "greet" in func_names
        assert "divide" in func_names
        assert "main" in func_names

    @staticmethod
    @pytest.mark.skipif("go" not in list_languages(), reason="Go grammar not available")
    def test_go_method_chunking():
        """Test chunking Go methods."""
        code = """
package main

type User struct {
    Name  string
    Email string
}

// Value receiver method
func (u User) String() string {
    return u.Name + " <" + u.Email + ">"
}

// Pointer receiver method
func (u *User) UpdateEmail(email string) {
    u.Email = email
}

// Method with error return
func (u *User) Validate() error {
    if u.Email == "" {
        return errors.New("email is required")
    }
    return nil
}
"""
        chunks = chunk_text(code, "go", "user.go")
        assert len(chunks) >= 4
        types = {c.node_type for c in chunks}
        assert "type_declaration" in types or "type_spec" in types
        assert "method_declaration" in types or "function_declaration" in types

    @staticmethod
    @pytest.mark.skipif("go" not in list_languages(), reason="Go grammar not available")
    def test_go_type_declarations():
        """Test chunking Go type declarations."""
        code = """
package models

// Simple type alias
type ID string

// Struct type
type Product struct {
    ID          ID
    Name        string
    Price       float64
    InStock     bool
}

// Interface type
type Repository interface {
    Find(id ID) (*Product, error)
    Save(p *Product) error
    Delete(id ID) error
}

// Embedded struct
type DetailedProduct struct {
    Product
    Description string
    Tags        []string
}
"""
        chunks = chunk_text(code, "go", "models.go")
        type_chunks = [c for c in chunks if "type" in c.node_type]
        assert len(type_chunks) >= 4
        type_names = [c.parent_context for c in type_chunks]
        assert any("Product" in n for n in type_names)
        assert any("Repository" in n for n in type_names)

    @staticmethod
    @pytest.mark.skipif("go" not in list_languages(), reason="Go grammar not available")
    def test_go_const_var_declarations():
        """Test chunking Go const and var declarations."""
        code = """
package config

import "time"

// Single constant
const AppName = "MyApp"

// Grouped constants
const (
    DefaultPort = 8080
    MaxRetries  = 3
    Timeout     = 30 * time.Second
)

// Single variable
var Version = "1.0.0"

// Grouped variables
var (
    StartTime = time.Now()
    IsDebug   = false
    Config    *AppConfig
)
"""
        chunks = chunk_text(code, "go", "config.go")
        const_chunks = [c for c in chunks if c.node_type == "const_declaration"]
        var_chunks = [c for c in chunks if c.node_type == "var_declaration"]
        assert len(const_chunks) >= 1
        assert len(var_chunks) >= 1

    @staticmethod
    @pytest.mark.skipif("go" not in list_languages(), reason="Go grammar not available")
    def test_go_language_config():
        """Test Go language configuration."""
        config = language_config_registry.get_config("go")
        assert config is not None
        assert config.name == "go"
        assert ".go" in config.file_extensions
        rule_names = [rule.name for rule in config.chunk_rules]
        assert "functions" in rule_names
        assert "types" in rule_names
        assert "constants" in rule_names
        assert "variables" in rule_names
        assert "source_file" in config.scope_node_types
        assert "function_declaration" in config.scope_node_types
        assert "block" in config.scope_node_types
