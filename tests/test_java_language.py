"""Tests for Java language support."""

import pytest

from chunker.chunker import chunk_text
from chunker.languages import language_config_registry
from chunker.parser import list_languages


class TestJavaLanguageSupport:
    """Test Java language chunking."""

    @pytest.mark.skipif(
        "java" not in list_languages(),
        reason="Java grammar not available",
    )
    def test_java_class_chunking(self):
        """Test chunking Java classes."""
        code = """
package com.example.model;

import java.util.List;
import java.util.ArrayList;

public class User {
    private String name;
    private String email;
    private List<Role> roles;

    public User(String name, String email) {
        this.name = name;
        this.email = email;
        this.roles = new ArrayList<>();
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getEmail() {
        return email;
    }

    public void addRole(Role role) {
        this.roles.add(role);
    }

    @Override
    public String toString() {
        return "User{name='" + name + "', email='" + email + "'}";
    }
}
"""
        chunks = chunk_text(code, "java", "User.java")

        # Should find class, fields, constructor, and methods
        assert len(chunks) >= 7

        # Check for class
        class_chunks = [c for c in chunks if c.node_type == "class_declaration"]
        assert len(class_chunks) == 1
        assert "User" in class_chunks[0].parent_context

        # Check for methods
        method_chunks = [c for c in chunks if c.node_type == "method_declaration"]
        assert len(method_chunks) >= 5  # getName, setName, getEmail, addRole, toString

        # Check for constructor
        constructor_chunks = [
            c for c in chunks if c.node_type == "constructor_declaration"
        ]
        assert len(constructor_chunks) == 1

    @pytest.mark.skipif(
        "java" not in list_languages(),
        reason="Java grammar not available",
    )
    def test_java_interface_chunking(self):
        """Test chunking Java interfaces."""
        code = """
package com.example.repository;

import java.util.List;
import java.util.Optional;

public interface UserRepository {
    Optional<User> findById(Long id);

    List<User> findByEmail(String email);

    User save(User user);

    void delete(User user);

    default List<User> findAll() {
        return findAll(0, 100);
    }

    List<User> findAll(int offset, int limit);
}
"""
        chunks = chunk_text(code, "java", "UserRepository.java")

        # Should find interface and methods
        interface_chunks = [c for c in chunks if c.node_type == "interface_declaration"]
        assert len(interface_chunks) == 1
        assert "UserRepository" in interface_chunks[0].parent_context

        # Interface methods may be parsed differently
        method_chunks = [c for c in chunks if "method" in c.node_type]
        assert len(method_chunks) >= 1  # At least the default method

    @pytest.mark.skipif(
        "java" not in list_languages(),
        reason="Java grammar not available",
    )
    def test_java_enum_chunking(self):
        """Test chunking Java enums."""
        code = """
package com.example.model;

public enum UserRole {
    ADMIN("Administrator"),
    USER("Regular User"),
    GUEST("Guest User");

    private final String displayName;

    UserRole(String displayName) {
        this.displayName = displayName;
    }

    public String getDisplayName() {
        return displayName;
    }

    public boolean hasAdminPrivileges() {
        return this == ADMIN;
    }
}
"""
        chunks = chunk_text(code, "java", "UserRole.java")

        # Should find enum, field, constructor, and methods
        enum_chunks = [c for c in chunks if c.node_type == "enum_declaration"]
        assert len(enum_chunks) == 1
        assert "UserRole" in enum_chunks[0].parent_context

        # Check for enum methods and constructor
        assert len(chunks) >= 4  # enum + field + constructor + methods

    @pytest.mark.skipif(
        "java" not in list_languages(),
        reason="Java grammar not available",
    )
    def test_java_annotations(self):
        """Test chunking Java code with annotations."""
        code = """
package com.example.controller;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/users")
public class UserController {

    @Autowired
    private UserService userService;

    @GetMapping("/{id}")
    public User getUser(@PathVariable Long id) {
        return userService.findById(id);
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public User createUser(@RequestBody @Valid User user) {
        return userService.save(user);
    }

    @ExceptionHandler(UserNotFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public ErrorResponse handleNotFound(UserNotFoundException e) {
        return new ErrorResponse(e.getMessage());
    }
}
"""
        chunks = chunk_text(code, "java", "UserController.java")

        # Should find class and annotated methods
        class_chunks = [c for c in chunks if c.node_type == "class_declaration"]
        assert len(class_chunks) == 1

        method_chunks = [c for c in chunks if c.node_type == "method_declaration"]
        assert len(method_chunks) >= 3  # getUser, createUser, handleNotFound

    @pytest.mark.skipif(
        "java" not in list_languages(),
        reason="Java grammar not available",
    )
    def test_java_inner_classes(self):
        """Test chunking Java inner classes."""
        code = """
public class OuterClass {
    private String outerField;

    public class InnerClass {
        public void innerMethod() {
            System.out.println(outerField);
        }
    }

    public static class StaticNestedClass {
        public void staticMethod() {
            System.out.println("Static nested");
        }
    }

    public void methodWithAnonymousClass() {
        Runnable r = new Runnable() {
            @Override
            public void run() {
                System.out.println("Anonymous class");
            }
        };
        r.run();
    }
}
"""
        chunks = chunk_text(code, "java", "OuterClass.java")

        # Should find outer class and nested classes
        class_chunks = [c for c in chunks if c.node_type == "class_declaration"]
        assert len(class_chunks) >= 3  # OuterClass, InnerClass, StaticNestedClass

    @pytest.mark.skipif(
        "java" not in list_languages(),
        reason="Java grammar not available",
    )
    def test_java_language_config(self):
        """Test Java language configuration."""
        config = language_config_registry.get_config("java")

        assert config is not None
        assert config.name == "java"
        assert ".java" in config.file_extensions

        # Check chunk rules
        rule_names = [rule.name for rule in config.chunk_rules]
        assert "classes" in rule_names
        assert "methods" in rule_names
        assert "fields" in rule_names

        # Check node types in class rule
        class_rule = next(r for r in config.chunk_rules if r.name == "classes")
        assert "class_declaration" in class_rule.node_types
        assert "interface_declaration" in class_rule.node_types
        assert "enum_declaration" in class_rule.node_types

        # Check scope node types
        assert "program" in config.scope_node_types
        assert "class_declaration" in config.scope_node_types
        assert "method_declaration" in config.scope_node_types
        assert "block" in config.scope_node_types
