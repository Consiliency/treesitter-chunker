"""Comprehensive tests for R language support."""

from chunker import chunk_file, get_parser
from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.languages.r import RPlugin


class TestRBasicChunking:
    """Test basic R chunking functionality."""

    def test_simple_function(self, tmp_path):
        """Test basic R function definition."""
        src = tmp_path / "simple.R"
        src.write_text(
            """# Simple function
add_numbers <- function(a, b) {
    return(a + b)
}

# Alternative assignment
multiply_numbers = function(x, y) {
    x * y
}
""",
        )
        chunks = chunk_file(src, "r")
        assert len(chunks) >= 2

        # Check for function assignments
        func_chunks = [c for c in chunks if "function" in c.content]
        assert len(func_chunks) == 2
        assert any("add_numbers" in c.content for c in func_chunks)
        assert any("multiply_numbers" in c.content for c in func_chunks)

    def test_control_structures(self, tmp_path):
        """Test R control structures."""
        src = tmp_path / "control.R"
        src.write_text(
            """# If statement
if (x > 0) {
    print("Positive")
} else if (x < 0) {
    print("Negative")
} else {
    print("Zero")
}

# For loop
for (i in 1:10) {
    print(i^2)
}

# While loop
while (count < 100) {
    count <- count * 2
    print(count)
}

# Repeat loop
repeat {
    x <- x + 1
    if (x > 10) break
}
""",
        )
        chunks = chunk_file(src, "r")

        # Check for control structures
        chunk_types = {chunk.node_type for chunk in chunks}
        assert "if_statement" in chunk_types
        assert "for_statement" in chunk_types
        assert "while_statement" in chunk_types
        assert "repeat_statement" in chunk_types

    def test_nested_functions(self, tmp_path):
        """Test nested function definitions in R."""
        src = tmp_path / "nested.R"
        src.write_text(
            """outer_function <- function(x) {
    # Define inner function
    inner_function <- function(y) {
        y * 2
    }

    # Use inner function
    result <- inner_function(x) + 10
    return(result)
}

# Anonymous function in apply
data <- 1:10
squared <- sapply(data, function(x) x^2)
""",
        )
        chunks = chunk_file(src, "r")

        # Should have outer function and inner function
        func_chunks = [c for c in chunks if "function" in c.content]
        assert len(func_chunks) >= 2
        assert any("outer_function" in c.content for c in func_chunks)
        assert any("inner_function" in c.content for c in func_chunks)

    def test_s3_methods(self, tmp_path):
        """Test S3 method definitions."""
        src = tmp_path / "s3_methods.R"
        src.write_text(
            """# Generic function
print.myclass <- function(x, ...) {
    cat("MyClass object:\\n")
    cat("Value:", x$value, "\\n")
}

# Another S3 method
summary.myclass <- function(object, ...) {
    list(
        value = object$value,
        type = "myclass"
    )
}

# Constructor function
myclass <- function(value) {
    structure(
        list(value = value),
        class = "myclass"
    )
}
""",
        )
        chunks = chunk_file(src, "r")

        # Check for S3 methods
        func_chunks = [c for c in chunks if "function" in c.content]
        assert any("print.myclass" in c.content for c in func_chunks)
        assert any("summary.myclass" in c.content for c in func_chunks)
        assert any("myclass <-" in c.content for c in func_chunks)

    def test_r_with_pipes(self, tmp_path):
        """Test R code with pipe operators."""
        src = tmp_path / "pipes.R"
        src.write_text(
            """library(dplyr)

# Data processing pipeline
process_data <- function(df) {
    df %>%
        filter(value > 0) %>%
        group_by(category) %>%
        summarise(
            mean_value = mean(value),
            count = n()
        ) %>%
        arrange(desc(mean_value))
}

# Using native pipe (R 4.1+)
clean_data <- function(data) {
    data |>
        na.omit() |>
        scale() |>
        as.data.frame()
}
""",
        )
        chunks = chunk_file(src, "r")

        # Check for functions with pipes
        func_chunks = [c for c in chunks if "function" in c.content]
        assert len(func_chunks) == 2
        assert any("%>%" in c.content for c in func_chunks)
        assert any("|>" in c.content for c in func_chunks)


class TestRContractCompliance:
    """Test ExtendedLanguagePluginContract compliance."""

    def test_implements_contract(self):
        """Verify RPlugin implements ExtendedLanguagePluginContract."""
        assert issubclass(RPlugin, ExtendedLanguagePluginContract)

    def test_get_semantic_chunks(self, tmp_path):
        """Test get_semantic_chunks method."""
        plugin = RPlugin()

        # Create a simple R file
        source = b"""square <- function(x) {
    x^2
}
"""

        # Parse the source (mock tree-sitter node)

        parser = get_parser("r")
        plugin.set_parser(parser)
        tree = parser.parse(source)

        chunks = plugin.get_semantic_chunks(tree.root_node, source)
        assert len(chunks) >= 1
        assert all("type" in chunk for chunk in chunks)
        assert all("start_line" in chunk for chunk in chunks)
        assert all("end_line" in chunk for chunk in chunks)
        assert all("content" in chunk for chunk in chunks)

    def test_get_chunk_node_types(self):
        """Test get_chunk_node_types method."""
        plugin = RPlugin()
        node_types = plugin.get_chunk_node_types()

        assert isinstance(node_types, set)
        assert len(node_types) > 0
        assert "function_definition" in node_types
        assert "assignment" in node_types or "left_assignment" in node_types
        assert "if_statement" in node_types

    def test_should_chunk_node(self):
        """Test should_chunk_node method."""
        plugin = RPlugin()

        # Mock nodes
        class MockNode:
            def __init__(self, node_type, has_function_child=False):
                self.type = node_type
                self.children = []
                if has_function_child:
                    child = MockNode("function_definition")
                    self.children.append(child)

        # Test chunk nodes
        assert plugin.should_chunk_node(MockNode("function_definition"))
        assert plugin.should_chunk_node(MockNode("assignment", has_function_child=True))
        assert plugin.should_chunk_node(MockNode("if_statement"))
        assert plugin.should_chunk_node(MockNode("for_statement"))
        assert plugin.should_chunk_node(MockNode("comment"))

        # Test non-chunk nodes
        assert not plugin.should_chunk_node(MockNode("identifier"))
        assert not plugin.should_chunk_node(MockNode("number"))
        assert not plugin.should_chunk_node(
            MockNode("assignment", has_function_child=False),
        )

    def test_get_node_context(self):
        """Test get_node_context method."""
        plugin = RPlugin()

        # Mock node
        class MockNode:
            def __init__(self, node_type, parent=None):
                self.type = node_type
                self.children = []
                self.parent = parent

        # Test function context
        node = MockNode("function_definition")
        context = plugin.get_node_context(node, b"function(x) x^2")
        assert context is not None

        # Test control structure context
        node = MockNode("if_statement")
        context = plugin.get_node_context(node, b"if (x > 0) print(x)")
        assert context == "if statement"

        node = MockNode("for_statement")
        context = plugin.get_node_context(node, b"for (i in 1:10)")
        assert context == "for loop"


class TestREdgeCases:
    """Test edge cases in R parsing."""

    def test_empty_r_file(self, tmp_path):
        """Test empty R file."""
        src = tmp_path / "empty.R"
        src.write_text("")
        chunks = chunk_file(src, "r")
        assert len(chunks) == 0

    def test_r_with_only_comments(self, tmp_path):
        """Test R file with only comments."""
        src = tmp_path / "comments.R"
        src.write_text(
            """# This is a comment
# Another comment
# TODO: implement function
# NOTE: important information
""",
        )
        chunks = chunk_file(src, "r")
        assert all(c.node_type == "comment" for c in chunks)

    def test_r_with_complex_assignments(self, tmp_path):
        """Test R with complex assignment patterns."""
        src = tmp_path / "complex_assign.R"
        src.write_text(
            """# Multiple assignment
c(a, b) %<-% list(1, 2)

# Right assignment
list(1:10) -> numbers

# Superassignment
global_var <<- 100

# Function with default arguments
process <- function(data, method = "mean", na.rm = TRUE) {
    switch(method,
        mean = mean(data, na.rm = na.rm),
        median = median(data, na.rm = na.rm),
        sum = sum(data, na.rm = na.rm)
    )
}
""",
        )
        chunks = chunk_file(src, "r")

        # Should capture the function with default arguments
        func_chunks = [
            c for c in chunks if "process" in c.content and "function" in c.content
        ]
        assert len(func_chunks) == 1
        assert "switch" in func_chunks[0].content

    def test_r_markdown_chunks(self, tmp_path):
        """Test R Markdown file with code chunks."""
        src = tmp_path / "analysis.Rmd"
        src.write_text(
            """---
title: "Analysis"
output: html_document
---

```{r setup}
library(ggplot2)
library(dplyr)
```

## Data Processing

```{r process-data}
process_data <- function(df) {
    df %>%
        mutate(log_value = log(value)) %>%
        filter(!is.na(log_value))
}
```

## Visualization

```{r plot-function}
create_plot <- function(data, x_var, y_var) {
    ggplot(data, aes_string(x = x_var, y = y_var)) +
        geom_point() +
        theme_minimal()
}
```
""",
        )
        chunks = chunk_file(src, "r")

        # Should find functions in R Markdown code chunks
        func_chunks = [c for c in chunks if "function" in c.content]
        assert len(func_chunks) >= 2
        assert any("process_data" in c.content for c in func_chunks)
        assert any("create_plot" in c.content for c in func_chunks)

    def test_r_with_s4_classes(self, tmp_path):
        """Test R with S4 class definitions."""
        src = tmp_path / "s4_class.R"
        src.write_text(
            """# S4 class definition
setClass("Person",
    slots = list(
        name = "character",
        age = "numeric"
    )
)

# S4 method
setMethod("show", "Person",
    function(object) {
        cat("Person: ", object@name, " (", object@age, " years old)\\n", sep = "")
    }
)

# Generic function
setGeneric("birthday", function(x) standardGeneric("birthday"))

# Method implementation
setMethod("birthday", "Person",
    function(x) {
        x@age <- x@age + 1
        x
    }
)
""",
        )
        chunks = chunk_file(src, "r")

        # Should capture S4-related definitions
        assert any("setClass" in c.content and "Person" in c.content for c in chunks)
        assert any("setMethod" in c.content and "show" in c.content for c in chunks)
        assert any(
            "setGeneric" in c.content and "birthday" in c.content for c in chunks
        )
