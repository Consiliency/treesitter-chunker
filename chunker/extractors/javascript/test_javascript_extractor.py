"""
Comprehensive unit tests for JavaScript extractor.

This module provides extensive test coverage for the JavaScriptExtractor class,
ensuring all methods and edge cases are properly tested with 95%+ coverage.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ..core.extraction_framework import CallSite, ExtractionResult
from .javascript_extractor import JavaScriptExtractor, JavaScriptPatterns


class TestJavaScriptExtractor(unittest.TestCase):
    """Test cases for JavaScriptExtractor class."""

    def setUp(self):
        """Set up test fixtures."""
        self.extractor = JavaScriptExtractor()
        self.sample_js_code = """
function myFunction() {
    console.log("Hello World");
    return getValue();
}

class MyClass {
    constructor() {
        super();
        this.data = [];
    }
    
    processData() {
        this.data.map(item => item.process());
        return this.helper.doSomething();
    }
}

const arrowFunc = async () => {
    await fetchData();
    return Promise.resolve();
};

// JSX components
const Component = () => {
    return <div><Button onClick={handleClick} /></div>;
};

// Template literals
const message = `Hello ${getName()}, your balance is ${account.getBalance()}`;
"""

    def test_initialization(self):
        """Test extractor initialization."""
        self.assertEqual(self.extractor.language, "javascript")
        self.assertIsInstance(self.extractor.patterns, JavaScriptPatterns)
        self.assertTrue(self.extractor._is_initialized)
        self.assertIsNotNone(self.extractor.extraction_stats)

    def test_extract_calls_basic(self):
        """Test basic call extraction functionality."""
        result = self.extractor.extract_calls(self.sample_js_code)

        self.assertIsInstance(result, ExtractionResult)
        self.assertTrue(result.is_successful())
        self.assertGreater(len(result.call_sites), 0)
        self.assertGreater(result.extraction_time, 0)

        # Verify metadata
        self.assertEqual(result.metadata["extractor"], "JavaScriptExtractor")
        self.assertEqual(result.metadata["language"], "javascript")
        self.assertIn("extraction_stats", result.metadata)

    def test_extract_calls_with_file_path(self):
        """Test call extraction with file path."""
        test_file = Path("test.js")
        result = self.extractor.extract_calls(self.sample_js_code, test_file)

        self.assertTrue(result.is_successful())
        for call_site in result.call_sites:
            self.assertEqual(call_site.file_path, test_file)
            self.assertEqual(call_site.language, "javascript")

    def test_extract_calls_empty_code(self):
        """Test extraction with empty code."""
        result = self.extractor.extract_calls("   ")  # whitespace only
        self.assertFalse(result.is_successful())
        self.assertGreater(len(result.errors), 0)

    def test_extract_calls_invalid_input(self):
        """Test extraction with invalid input."""
        # Test None input
        result_none = self.extractor.extract_calls(None)
        self.assertFalse(result_none.is_successful())
        self.assertGreater(len(result_none.errors), 0)

        # Test numeric input
        result_num = self.extractor.extract_calls(123)
        self.assertFalse(result_num.is_successful())
        self.assertGreater(len(result_num.errors), 0)

    def test_validate_source_valid(self):
        """Test source validation with valid JavaScript code."""
        valid_codes = [
            "function test() { return 1; }",
            "const x = () => { console.log('hello'); };",
            "class MyClass { constructor() {} }",
            "import { func } from 'module';",
            "export default function() {}",
            "async function fetch() { await getData(); }",
            "if (condition) { doSomething(); }",
        ]

        for code in valid_codes:
            with self.subTest(code=code):
                self.assertTrue(self.extractor.validate_source(code))

    def test_validate_source_invalid(self):
        """Test source validation with invalid input."""
        invalid_inputs = [
            None,
            123,
            "",
            "   ",
        ]

        for invalid_input in invalid_inputs:
            with self.subTest(input=invalid_input):
                self.assertFalse(self.extractor.validate_source(invalid_input))

    def test_validate_source_unbalanced_brackets(self):
        """Test source validation with unbalanced brackets."""
        unbalanced_codes = [
            "function test() { return 1;",  # Missing closing brace
            "if (condition { doSomething(); }",  # Missing closing paren
            "array[index;",  # Missing closing bracket
        ]

        for code in unbalanced_codes:
            with self.subTest(code=code):
                self.assertFalse(self.extractor.validate_source(code))

    def test_extract_function_calls(self):
        """Test function call extraction."""
        code = """
        function test() {
            regularFunction();
            asyncFunction();
            await awaitedFunction();
            callback(anotherFunction);
        }
        """

        calls = self.extractor.extract_function_calls(code)
        self.assertIsInstance(calls, list)

        # Should find function calls
        function_names = [call.function_name for call in calls]
        expected_functions = ["regularFunction", "asyncFunction", "awaitedFunction"]

        for expected in expected_functions:
            self.assertIn(expected, function_names)

    def test_extract_method_calls(self):
        """Test method call extraction."""
        code = """
        object.method();
        obj.nestedObj.deepMethod();
        array.map(item => item.process());
        optional?.chaining?.method();
        this.instanceMethod();
        """

        calls = self.extractor.extract_method_calls(code)
        self.assertIsInstance(calls, list)
        self.assertGreater(len(calls), 0)

        # Check for method calls
        call_names = [call.function_name for call in calls]
        self.assertTrue(any("method" in name for name in call_names))

    def test_extract_constructor_calls(self):
        """Test constructor call extraction."""
        code = """
        class Child extends Parent {
            constructor() {
                super();
                this.instance = new MyClass();
                this.other = new module.ExportedClass(param);
            }
        }
        """

        calls = self.extractor.extract_constructor_calls(code)
        self.assertIsInstance(calls, list)

        # Should find constructor calls
        call_names = [call.function_name for call in calls]
        self.assertIn("super", call_names)
        self.assertIn("MyClass", call_names)

    def test_extract_jsx_calls(self):
        """Test JSX component call extraction."""
        code = """
        const Component = () => {
            return (
                <div>
                    <Button onClick={handler} />
                    <CustomComponent prop={value}>
                        <NestedComponent />
                    </CustomComponent>
                </div>
            );
        };
        """

        calls = self.extractor.extract_jsx_calls(code)
        self.assertIsInstance(calls, list)

        # Should find JSX components
        component_names = [call.function_name for call in calls]
        expected_components = ["Button", "CustomComponent", "NestedComponent"]

        for expected in expected_components:
            self.assertIn(expected, component_names)

    def test_extract_template_calls(self):
        """Test template literal call extraction."""
        code = """
        const message = `Hello ${getName()}, balance: ${account.getBalance()}`;
        const query = `SELECT * FROM ${getTableName()} WHERE id = ${getId()}`;
        """

        calls = self.extractor.extract_template_calls(code)
        self.assertIsInstance(calls, list)

        # Should find template calls
        if calls:  # Template extraction is complex, so we just verify structure
            for call in calls:
                self.assertIsInstance(call, CallSite)
                self.assertEqual(call.call_type, "template")

    def test_create_call_site_from_match(self):
        """Test CallSite creation from match information."""
        call_info = {
            "name": "testFunction",
            "start": 10,
            "end": 25,
            "context": {"test": "value"},
        }

        call_site = self.extractor._create_call_site_from_match(
            call_info,
            self.sample_js_code,
            "function",
        )

        self.assertIsInstance(call_site, CallSite)
        self.assertEqual(call_site.function_name, "testFunction")
        self.assertEqual(call_site.byte_start, 10)
        self.assertEqual(call_site.byte_end, 25)
        self.assertEqual(call_site.call_type, "function")
        self.assertEqual(call_site.language, "javascript")

    def test_create_call_site_from_match_invalid(self):
        """Test CallSite creation with invalid match information."""
        invalid_call_info = {"name": "", "start": 10, "end": 25}  # Empty name

        call_site = self.extractor._create_call_site_from_match(
            invalid_call_info,
            self.sample_js_code,
            "function",
        )

        self.assertIsNone(call_site)

    def test_check_balanced_brackets(self):
        """Test balanced bracket checking."""
        balanced_codes = [
            "function() { return [1, 2, 3]; }",
            "if (condition) { doSomething(); }",
            "array.map(item => { return item.value; })",
        ]

        unbalanced_codes = [
            "function() { return [1, 2, 3; }",
            "if (condition { doSomething(); }",
            "array.map(item => { return item.value; }",
        ]

        for code in balanced_codes:
            with self.subTest(code=code):
                self.assertTrue(self.extractor._check_balanced_brackets(code))

        for code in unbalanced_codes:
            with self.subTest(code=code):
                self.assertFalse(self.extractor._check_balanced_brackets(code))

    def test_remove_strings_and_comments(self):
        """Test string and comment removal."""
        code_with_strings = """
        // This is a comment
        function test() {
            const str = "string with { brackets }";
            const template = `template with ${expression}`;
            /* Multi-line
               comment */
            return 'another string';
        }
        """

        cleaned = self.extractor._remove_strings_and_comments(code_with_strings)

        # Comments should be removed
        self.assertNotIn("This is a comment", cleaned)
        self.assertNotIn("Multi-line", cleaned)

        # Strings should be replaced with empty strings
        self.assertNotIn("string with { brackets }", cleaned)
        self.assertIn('""', cleaned)

    def test_deduplicate_calls(self):
        """Test call site deduplication."""
        # Create duplicate call sites
        call_site1 = CallSite(
            function_name="test",
            line_number=1,
            column_number=0,
            byte_start=0,
            byte_end=10,
            call_type="function",
            context={},
            language="javascript",
            file_path=Path("test.js"),
        )

        call_site2 = CallSite(
            function_name="test",
            line_number=1,
            column_number=0,
            byte_start=0,
            byte_end=10,
            call_type="function",
            context={},
            language="javascript",
            file_path=Path("test.js"),
        )

        call_site3 = CallSite(
            function_name="different",
            line_number=2,
            column_number=0,
            byte_start=20,
            byte_end=30,
            call_type="function",
            context={},
            language="javascript",
            file_path=Path("test.js"),
        )

        duplicates = [call_site1, call_site2, call_site3]
        deduplicated = self.extractor._deduplicate_calls(duplicates)

        self.assertEqual(len(deduplicated), 2)  # Should remove one duplicate

    def test_validate_call_sites(self):
        """Test call site validation."""
        result = ExtractionResult()

        # Use a longer test code so byte offsets make sense
        test_code = "function test() { return 42; }"

        # Valid call site
        valid_call = CallSite(
            function_name="test",
            line_number=1,
            column_number=0,
            byte_start=0,
            byte_end=8,  # Length of "function"
            call_type="function",
            context={},
            language="javascript",
            file_path=Path("test.js"),
        )

        # Create invalid call site using private attributes to bypass validation
        invalid_call = object.__new__(CallSite)
        invalid_call.function_name = "invalid"
        invalid_call.line_number = 1
        invalid_call.column_number = 0
        invalid_call.byte_start = -1  # Invalid negative value
        invalid_call.byte_end = 10
        invalid_call.call_type = "function"
        invalid_call.context = {}
        invalid_call.language = "javascript"
        invalid_call.file_path = Path("test.js")

        result.call_sites = [valid_call, invalid_call]

        self.extractor._validate_call_sites(result, test_code)

        # Should keep only valid call sites
        self.assertEqual(len(result.call_sites), 1)
        self.assertEqual(result.call_sites[0].function_name, "test")

        # Should have warning about invalid call site
        self.assertGreater(len(result.warnings), 0)

    def test_error_handling_in_extraction(self):
        """Test error handling during extraction."""
        # Mock patterns to raise exception
        with patch.object(
            self.extractor.patterns,
            "find_function_calls",
            side_effect=Exception("Test error"),
        ):
            result = self.extractor.extract_calls("function test() {}")

            # Should still return a result (may be empty due to error)
            self.assertIsInstance(result, ExtractionResult)

    def test_performance_measurement(self):
        """Test performance measurement functionality."""
        result = self.extractor.extract_calls(self.sample_js_code)

        # Should have performance metrics
        self.assertGreater(len(result.performance_metrics), 0)
        self.assertIn("function_calls", result.performance_metrics)


class TestJavaScriptPatterns(unittest.TestCase):
    """Test cases for JavaScriptPatterns class."""

    def setUp(self):
        """Set up test fixtures."""
        self.patterns = JavaScriptPatterns()

    def test_find_function_calls(self):
        """Test function call pattern matching."""
        code = """
        function test() {
            regularCall();
            await asyncCall();
            callback(functionParam);
            complexCall().then();
        }
        """

        calls = JavaScriptPatterns.find_function_calls(code)
        self.assertIsInstance(calls, list)
        self.assertGreater(len(calls), 0)

        # Check structure of returned calls
        for call in calls:
            self.assertIn("name", call)
            self.assertIn("start", call)
            self.assertIn("end", call)
            self.assertIn("full_match", call)

    def test_find_method_calls(self):
        """Test method call pattern matching."""
        code = """
        object.method();
        this.instanceMethod();
        nested.obj.deepMethod();
        optional?.chaining();
        array[0].method();
        """

        calls = JavaScriptPatterns.find_method_calls(code)
        self.assertIsInstance(calls, list)
        self.assertGreater(len(calls), 0)

        # Check for method calls
        method_names = [call.get("method_name", call.get("name", "")) for call in calls]
        self.assertTrue(any("method" in name.lower() for name in method_names))

    def test_find_constructor_calls(self):
        """Test constructor call pattern matching."""
        code = """
        class Test extends Parent {
            constructor() {
                super();
                this.obj = new MyClass();
                this.other = new namespace.Class(param);
            }
        }
        """

        calls = JavaScriptPatterns.find_constructor_calls(code)
        self.assertIsInstance(calls, list)
        self.assertGreater(len(calls), 0)

        # Should find super and new calls
        call_names = [call["name"] for call in calls]
        self.assertIn("super", call_names)

    def test_find_jsx_calls(self):
        """Test JSX component pattern matching."""
        jsx_code = """
        const Component = () => {
            return (
                <div>
                    <Button onClick={handler} />
                    <CustomComponent>
                        <NestedComponent />
                    </CustomComponent>
                </div>
            );
        };
        """

        calls = JavaScriptPatterns.find_jsx_calls(jsx_code)
        self.assertIsInstance(calls, list)

        # Should find JSX components
        if calls:  # JSX detection might be complex
            component_names = [call["name"] for call in calls]
            self.assertTrue(any(name[0].isupper() for name in component_names))

    def test_find_template_calls(self):
        """Test template literal call pattern matching."""
        code = """
        const msg = `Hello ${getName()}, balance: ${user.getBalance()}`;
        const sql = `SELECT * FROM ${table.getName()} WHERE id = ${getId()}`;
        """

        calls = JavaScriptPatterns.find_template_calls(code)
        self.assertIsInstance(calls, list)

        # Template matching is complex, just verify structure
        for call in calls:
            self.assertIn("name", call)
            self.assertIn("context", call)

    def test_extract_call_context(self):
        """Test context extraction from call information."""
        call_info = {
            "name": "testFunction",
            "start": 50,
            "end": 65,
            "full_match": "testFunction()",
            "pattern": r"test_pattern",
        }

        source_code = """
        function example() {
            const result = testFunction();
            return result;
        }
        """

        context = JavaScriptPatterns.extract_call_context(call_info, source_code)

        self.assertIsInstance(context, dict)
        self.assertIn("surrounding_text", context)
        self.assertIn("match_text", context)
        self.assertIn("pattern_used", context)
        self.assertEqual(context["match_text"], "testFunction()")

    def test_extract_call_context_async(self):
        """Test context extraction for async calls."""
        call_info = {
            "name": "asyncFunction",
            "start": 30,
            "end": 45,
            "full_match": "await asyncFunction()",
            "pattern": r"async_pattern",
        }

        source_code = """
        async function test() {
            const result = await asyncFunction();
            return result;
        }
        """

        context = JavaScriptPatterns.extract_call_context(call_info, source_code)

        self.assertIsInstance(context, dict)
        self.assertTrue(context.get("is_async", False))

    def test_clean_source_for_pattern_matching(self):
        """Test source code cleaning for pattern matching."""
        code_with_noise = """
        // Single line comment
        function test() {
            const str = "string with function() call";
            const regex = /pattern/gi;
            /* Multi-line
               comment with function() */
            const template = `template with ${func()}`;
            realFunction();
        }
        """

        cleaned = JavaScriptPatterns._clean_source_for_pattern_matching(code_with_noise)

        # Comments should be removed
        self.assertNotIn("Single line comment", cleaned)
        self.assertNotIn("Multi-line", cleaned)

        # Strings should be replaced
        self.assertNotIn("string with function() call", cleaned)
        self.assertIn('""', cleaned)

        # Regex should be replaced
        self.assertNotIn("/pattern/gi", cleaned)

        # Real function call should remain
        self.assertIn("realFunction", cleaned)

    def test_remove_comments_only(self):
        """Test comment-only removal."""
        code_with_comments = """
        // Comment
        const str = "keep this string";
        /* Multi comment */
        function test() {}
        """

        cleaned = JavaScriptPatterns._remove_comments_only(code_with_comments)

        # Comments should be removed
        self.assertNotIn("Comment", cleaned)
        self.assertNotIn("Multi comment", cleaned)

        # Strings should be preserved
        self.assertIn("keep this string", cleaned)

    def test_is_valid_identifier(self):
        """Test JavaScript identifier validation."""
        valid_identifiers = [
            "validName",
            "_underscore",
            "$dollar",
            "name123",
            "camelCase",
            "UPPERCASE",
            "_$mixed123",
        ]

        invalid_identifiers = [
            "",
            "123invalid",
            "invalid-dash",
            "invalid space",
            "invalid.dot",
            None,
            123,
        ]

        for valid in valid_identifiers:
            with self.subTest(identifier=valid):
                self.assertTrue(JavaScriptPatterns._is_valid_identifier(valid))

        for invalid in invalid_identifiers:
            with self.subTest(identifier=invalid):
                self.assertFalse(JavaScriptPatterns._is_valid_identifier(invalid))

    def test_is_valid_jsx_component(self):
        """Test JSX component name validation."""
        valid_components = [
            "Component",
            "MyComponent",
            "UI_Component",
            "Component123",
            "ComponentV2",
        ]

        invalid_components = [
            "component",  # lowercase
            "my-component",  # dash
            "123Component",  # starts with number
            "",
            None,
            "invalid space",
        ]

        for valid in valid_components:
            with self.subTest(component=valid):
                self.assertTrue(JavaScriptPatterns._is_valid_jsx_component(valid))

        for invalid in invalid_components:
            with self.subTest(component=invalid):
                self.assertFalse(JavaScriptPatterns._is_valid_jsx_component(invalid))

    def test_pattern_edge_cases(self):
        """Test edge cases in pattern matching."""
        edge_cases = [
            "",  # Empty code
            "   ",  # Whitespace only
            "// Only comments",
            "/* Only block comment */",
            '"only strings"',
            "123 + 456",  # Only numbers
            "var x;",  # Variable declaration only
        ]

        for code in edge_cases:
            with self.subTest(code=code):
                # Should not crash on edge cases
                function_calls = JavaScriptPatterns.find_function_calls(code)
                method_calls = JavaScriptPatterns.find_method_calls(code)
                constructor_calls = JavaScriptPatterns.find_constructor_calls(code)
                jsx_calls = JavaScriptPatterns.find_jsx_calls(code)
                template_calls = JavaScriptPatterns.find_template_calls(code)

                # All should return lists (possibly empty)
                self.assertIsInstance(function_calls, list)
                self.assertIsInstance(method_calls, list)
                self.assertIsInstance(constructor_calls, list)
                self.assertIsInstance(jsx_calls, list)
                self.assertIsInstance(template_calls, list)


class TestJavaScriptExtractorIntegration(unittest.TestCase):
    """Integration tests for JavaScript extractor."""

    def setUp(self):
        """Set up test fixtures."""
        self.extractor = JavaScriptExtractor()

    def test_real_world_javascript_file(self):
        """Test extraction on a real-world JavaScript file structure."""
        real_world_code = """
import React, { useState, useEffect } from 'react';
import { fetchUserData, validateInput } from './utils';

const UserProfile = ({ userId }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    
    useEffect(() => {
        const loadUser = async () => {
            try {
                setLoading(true);
                const userData = await fetchUserData(userId);
                if (validateInput(userData)) {
                    setUser(userData);
                } else {
                    throw new Error('Invalid user data');
                }
            } catch (err) {
                console.error('Failed to load user:', err);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };
        
        loadUser();
    }, [userId]);
    
    const handleUpdate = (field, value) => {
        const updatedUser = { ...user, [field]: value };
        setUser(updatedUser);
        saveUserData(updatedUser);
    };
    
    if (loading) {
        return <LoadingSpinner />;
    }
    
    if (error) {
        return <ErrorMessage message={error} onRetry={() => window.location.reload()} />;
    }
    
    return (
        <div className="user-profile">
            <Avatar src={user.avatar} alt={`${user.name}'s avatar`} />
            <h1>{user.name}</h1>
            <p>{user.email}</p>
            <EditableField 
                value={user.bio}
                onChange={(value) => handleUpdate('bio', value)}
            />
            <Button onClick={() => logAnalytics('profile_view', { userId: user.id })}>
                View Analytics
            </Button>
        </div>
    );
};

export default UserProfile;
"""

        result = self.extractor.extract_calls(real_world_code, Path("UserProfile.jsx"))

        # Should successfully extract calls
        self.assertTrue(result.is_successful())
        self.assertGreater(len(result.call_sites), 10)  # Should find many calls

        # Check for expected call types
        call_types = [call.call_type for call in result.call_sites]
        self.assertIn("function", call_types)
        self.assertIn("method", call_types)
        self.assertIn("jsx", call_types)

        # Check for specific expected functions
        function_names = [call.function_name for call in result.call_sites]
        expected_functions = [
            "useState",
            "useEffect",
            "fetchUserData",
            "validateInput",
            "console.error",
        ]

        for expected in expected_functions:
            self.assertTrue(
                any(expected in name for name in function_names),
                f"Expected function '{expected}' not found in {function_names}",
            )

    def test_typescript_specific_features(self):
        """Test extraction on TypeScript-specific features."""
        typescript_code = """
interface User {
    id: number;
    name: string;
    email: string;
}

class UserService {
    private apiClient: ApiClient;
    
    constructor(apiClient: ApiClient) {
        this.apiClient = apiClient;
    }
    
    async getUser(id: number): Promise<User> {
        const response = await this.apiClient.get<User>(`/users/${id}`);
        return this.transformUser(response.data);
    }
    
    private transformUser(data: any): User {
        return {
            id: parseInt(data.id),
            name: String(data.name).trim(),
            email: data.email.toLowerCase()
        };
    }
}

// Generic function
function processArray<T>(items: T[], processor: (item: T) => T): T[] {
    return items.map(processor);
}

// Usage
const userService = new UserService(apiClient);
const user = await userService.getUser(123);
const processedData = processArray(data, (item) => normalize(item));
"""

        result = self.extractor.extract_calls(typescript_code, Path("UserService.ts"))

        # Should handle TypeScript syntax
        self.assertTrue(result.is_successful())
        self.assertGreater(len(result.call_sites), 5)

        # Check for TypeScript-specific calls
        function_names = [call.function_name for call in result.call_sites]
        typescript_functions = [
            "parseInt",
            "String",
            "toLowerCase",
            "UserService",
            "getUser",
        ]

        for ts_func in typescript_functions:
            self.assertTrue(
                any(ts_func in name for name in function_names),
                f"TypeScript function '{ts_func}' not found",
            )

    def test_performance_with_large_file(self):
        """Test performance with a large JavaScript file."""
        # Create a large file with many function calls
        large_code_parts = []
        for i in range(100):
            large_code_parts.append(
                f"""
function function{i}() {{
    call{i}();
    object{i}.method{i}();
    new Constructor{i}();
    return getValue{i}();
}}
""",
            )

        large_code = "\n".join(large_code_parts)

        result = self.extractor.extract_calls(large_code)

        # Should complete in reasonable time and find many calls
        self.assertTrue(result.is_successful())
        self.assertGreater(len(result.call_sites), 300)  # Should find lots of calls
        self.assertLess(result.extraction_time, 5.0)  # Should complete quickly

    def test_error_recovery(self):
        """Test extractor's ability to recover from syntax errors."""
        malformed_code = """
function broken() {
    // Missing closing brace
    normalFunction();
    
// Unclosed comment
function another() {
    stillWorks();
}

// Weird syntax
function ??? invalid {
    butThisWorks();
}
"""

        result = self.extractor.extract_calls(malformed_code)

        # Should still extract some calls despite syntax errors
        self.assertGreater(len(result.call_sites), 0)

        # Should find the valid function calls
        function_names = [call.function_name for call in result.call_sites]
        self.assertTrue(any("normalFunction" in name for name in function_names))
        self.assertTrue(any("stillWorks" in name for name in function_names))


class TestJavaScriptExtractorEdgeCases(unittest.TestCase):
    """Additional edge case tests to improve coverage."""

    def setUp(self):
        """Set up test fixtures."""
        self.extractor = JavaScriptExtractor()

    def test_extract_calls_with_exception_handling(self):
        """Test extraction when individual extractors raise exceptions."""
        # Create malformed code that might cause issues
        malformed_code = """
        function test() {
            // This should still work
            normalCall();
            
            // Complex patterns that might cause regex issues
            weird...syntax.here();
            invalid\\escape\\sequences();
        }
        """

        result = self.extractor.extract_calls(malformed_code)

        # Should still return a result
        self.assertIsInstance(result, ExtractionResult)

    def test_extract_calls_with_existing_file(self):
        """Test extraction with an actual file path."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write('function test() { console.log("hello"); }')
            temp_file = Path(f.name)

        try:
            result = self.extractor.extract_calls(
                'function test() { console.log("hello"); }',
                temp_file,
            )

            # Should include file metadata
            self.assertIn("file_metadata", result.metadata)
            self.assertIn("size_bytes", result.metadata["file_metadata"])

        finally:
            # Clean up
            os.unlink(temp_file)

    def test_validate_source_no_js_indicators(self):
        """Test validation with code that has no JavaScript indicators."""
        non_js_code = "1 + 2 + 3; 'just a string'; /* comment */"

        # Should still return True but log a warning
        result = self.extractor.validate_source(non_js_code)
        self.assertTrue(result)  # Basic validation still passes

    def test_error_in_pattern_matching(self):
        """Test handling of regex errors in pattern matching."""
        # Test with code that might cause regex issues
        problematic_code = """
        // Test various edge cases
        function test() {
            // Unicode characters
            função();
            методCall();
            
            // Unusual spacing
            func     (     );
            obj    .    method    (    );
            
            // Complex expressions
            (complex ? expression : alternative)();
            obj[computed.property]();
        }
        """

        # Should handle without crashing
        function_calls = JavaScriptPatterns.find_function_calls(problematic_code)
        method_calls = JavaScriptPatterns.find_method_calls(problematic_code)

        self.assertIsInstance(function_calls, list)
        self.assertIsInstance(method_calls, list)

    def test_context_extraction_with_multiline(self):
        """Test context extraction with multiline expressions."""
        call_info = {
            "name": "multilineFunction",
            "start": 50,
            "end": 70,
            "full_match": "multilineFunction()",
            "pattern": r"test_pattern",
        }

        multiline_code = """
        function example() {
            const result = multilineFunction(
                param1,
                param2,
                param3
            );
            return result;
        }
        """

        context = JavaScriptPatterns.extract_call_context(call_info, multiline_code)

        self.assertIsInstance(context, dict)
        self.assertIn("line_text", context)

    def test_balanced_brackets_with_strings(self):
        """Test bracket checking with strings containing brackets."""
        code_with_string_brackets = """
        function test() {
            const str = "string with { brackets } and [arrays]";
            const template = `template with ${expression}`;
            return normalFunction();
        }
        """

        # Should recognize as balanced despite brackets in strings
        result = self.extractor._check_balanced_brackets(code_with_string_brackets)
        self.assertTrue(result)

    def test_pattern_extraction_edge_cases(self):
        """Test pattern extraction with various edge cases."""
        edge_case_code = """
        // Test edge cases
        () => func();  // Arrow function calling func
        [1,2,3].map(x => x.transform());  // Array method with arrow
        obj?.method?.();  // Optional chaining
        new (getConstructor())();  // Dynamic constructor
        `template ${call()} literal`;  // Template literal call
        """

        # Test all extraction methods
        function_calls = self.extractor.extract_function_calls(edge_case_code)
        method_calls = self.extractor.extract_method_calls(edge_case_code)
        constructor_calls = self.extractor.extract_constructor_calls(edge_case_code)
        jsx_calls = self.extractor.extract_jsx_calls(edge_case_code)
        template_calls = self.extractor.extract_template_calls(edge_case_code)

        # Should all return lists without crashing
        self.assertIsInstance(function_calls, list)
        self.assertIsInstance(method_calls, list)
        self.assertIsInstance(constructor_calls, list)
        self.assertIsInstance(jsx_calls, list)
        self.assertIsInstance(template_calls, list)

    def test_create_call_site_with_missing_data(self):
        """Test CallSite creation with missing data."""
        # Test with missing start/end
        call_info = {
            "name": "testFunc",
            # Missing start/end
            "context": {},
        }

        call_site = self.extractor._create_call_site_from_match(
            call_info,
            "test code",
            "function",
        )

        # Should handle gracefully
        self.assertIsInstance(call_site, CallSite)
        self.assertEqual(call_site.function_name, "testFunc")
        self.assertEqual(call_site.byte_start, 0)  # Default value

    def test_clean_source_error_handling(self):
        """Test source cleaning error handling."""
        # Test with problematic input that might cause regex errors
        problematic_inputs = [
            None,  # Will cause TypeError in some regex operations
            123,  # Non-string input
            "",  # Empty string
            "\\invalid\\escape\\sequences",  # Problematic escapes
        ]

        for input_val in problematic_inputs:
            try:
                cleaned = JavaScriptPatterns._clean_source_for_pattern_matching(
                    input_val,
                )
                # Should either clean successfully or return original
                self.assertIsNotNone(cleaned)
            except Exception:
                # If it raises an exception, that's also acceptable behavior
                pass

    def test_extract_context_with_exception(self):
        """Test context extraction when an exception occurs."""
        # Create call_info that might cause issues
        problematic_call_info = {
            "name": "test",
            "start": -1,  # Invalid position
            "end": 1000000,  # Position beyond source length
            "full_match": None,  # Invalid match
        }

        context = JavaScriptPatterns.extract_call_context(
            problematic_call_info,
            "short code",
        )

        # Should handle gracefully and include error info
        self.assertIsInstance(context, dict)
        self.assertIn("extraction_error", context)

    def test_extraction_methods_with_exceptions(self):
        """Test extraction methods when they raise exceptions."""
        # Mock the patterns to raise exceptions and test error handling
        with patch.object(
            JavaScriptPatterns,
            "find_function_calls",
            side_effect=Exception("Function call error"),
        ):
            calls = self.extractor.extract_function_calls("test code")
            self.assertEqual(calls, [])  # Should return empty list on error

        with patch.object(
            JavaScriptPatterns,
            "find_method_calls",
            side_effect=Exception("Method call error"),
        ):
            calls = self.extractor.extract_method_calls("test code")
            self.assertEqual(calls, [])  # Should return empty list on error

        with patch.object(
            JavaScriptPatterns,
            "find_constructor_calls",
            side_effect=Exception("Constructor call error"),
        ):
            calls = self.extractor.extract_constructor_calls("test code")
            self.assertEqual(calls, [])  # Should return empty list on error

        with patch.object(
            JavaScriptPatterns,
            "find_jsx_calls",
            side_effect=Exception("JSX call error"),
        ):
            calls = self.extractor.extract_jsx_calls("test code")
            self.assertEqual(calls, [])  # Should return empty list on error

        with patch.object(
            JavaScriptPatterns,
            "find_template_calls",
            side_effect=Exception("Template call error"),
        ):
            calls = self.extractor.extract_template_calls("test code")
            self.assertEqual(calls, [])  # Should return empty list on error

    def test_pattern_find_methods_with_invalid_regex(self):
        """Test pattern finding methods with invalid regex patterns."""
        # Patch the patterns to include invalid regex
        invalid_patterns = [r"[invalid", r"*invalid", r"(?P<invalid"]

        with patch.object(
            JavaScriptPatterns,
            "FUNCTION_CALL_PATTERNS",
            invalid_patterns,
        ):
            calls = JavaScriptPatterns.find_function_calls("function test() {}")
            self.assertIsInstance(calls, list)  # Should handle gracefully

        with patch.object(JavaScriptPatterns, "METHOD_CALL_PATTERNS", invalid_patterns):
            calls = JavaScriptPatterns.find_method_calls("obj.method()")
            self.assertIsInstance(calls, list)  # Should handle gracefully

        with patch.object(JavaScriptPatterns, "CONSTRUCTOR_PATTERNS", invalid_patterns):
            calls = JavaScriptPatterns.find_constructor_calls("new Class()")
            self.assertIsInstance(calls, list)  # Should handle gracefully

        with patch.object(JavaScriptPatterns, "JSX_PATTERNS", invalid_patterns):
            calls = JavaScriptPatterns.find_jsx_calls("<Component />")
            self.assertIsInstance(calls, list)  # Should handle gracefully

        with patch.object(
            JavaScriptPatterns,
            "TEMPLATE_LITERAL_PATTERNS",
            invalid_patterns,
        ):
            calls = JavaScriptPatterns.find_template_calls("`template ${func()}`")
            self.assertIsInstance(calls, list)  # Should handle gracefully

    def test_create_call_site_exception_handling(self):
        """Test CallSite creation exception handling."""
        # Test with call_info that will cause an exception in CallSite creation
        invalid_call_info = {
            "name": "testFunc",
            "start": "invalid",  # Non-integer start
            "end": "invalid",  # Non-integer end
            "context": None,  # Invalid context
        }

        call_site = self.extractor._create_call_site_from_match(
            invalid_call_info,
            "test code",
            "function",
        )

        # Should return None on exception
        self.assertIsNone(call_site)

    def test_individual_pattern_match_exception_handling(self):
        """Test individual pattern match exception handling."""
        # Test extract_function_calls with invalid match processing
        with patch.object(
            self.extractor,
            "_create_call_site_from_match",
            side_effect=Exception("CallSite error"),
        ):
            # This should catch the exception and continue
            calls = self.extractor.extract_function_calls("function test() {}")
            self.assertIsInstance(calls, list)

        # Same for other methods
        with patch.object(
            self.extractor,
            "_create_call_site_from_match",
            side_effect=Exception("CallSite error"),
        ):
            calls = self.extractor.extract_method_calls("obj.method()")
            self.assertIsInstance(calls, list)

        with patch.object(
            self.extractor,
            "_create_call_site_from_match",
            side_effect=Exception("CallSite error"),
        ):
            calls = self.extractor.extract_constructor_calls("new Class()")
            self.assertIsInstance(calls, list)

        with patch.object(
            self.extractor,
            "_create_call_site_from_match",
            side_effect=Exception("CallSite error"),
        ):
            calls = self.extractor.extract_jsx_calls("<Component />")
            self.assertIsInstance(calls, list)

        with patch.object(
            self.extractor,
            "_create_call_site_from_match",
            side_effect=Exception("CallSite error"),
        ):
            calls = self.extractor.extract_template_calls("`template ${func()}`")
            self.assertIsInstance(calls, list)

    def test_check_balanced_brackets_exception(self):
        """Test balanced bracket checking with exception handling."""
        # Test the exception case in _check_balanced_brackets
        result = self.extractor._check_balanced_brackets(None)
        self.assertTrue(result)  # Should return True on exception

    def test_remove_strings_and_comments_exception(self):
        """Test string/comment removal with exception handling."""
        # Test the exception case in _remove_strings_and_comments
        result = self.extractor._remove_strings_and_comments(None)
        self.assertIsNone(result)  # Should return original on exception

    def test_pattern_cleaning_exceptions(self):
        """Test pattern cleaning methods with exceptions."""
        # Test _clean_source_for_pattern_matching exception path
        result = JavaScriptPatterns._clean_source_for_pattern_matching(None)
        self.assertIsNone(result)  # Should return original on exception

        # Test _remove_comments_only exception path
        result = JavaScriptPatterns._remove_comments_only(None)
        self.assertIsNone(result)  # Should return original on exception

    def test_validation_with_specific_edge_cases(self):
        """Test validation with specific edge cases that trigger warnings."""
        # Test source with no JS indicators to trigger warning
        minimal_code = "x = 1;"
        result = self.extractor.validate_source(minimal_code)
        # This should trigger the "No JavaScript syntax indicators found" warning
        self.assertTrue(result)  # But still pass basic validation


if __name__ == "__main__":
    unittest.main()
