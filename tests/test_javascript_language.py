"""Test JavaScript-specific language features."""

from chunker.core import chunk_file
from chunker.languages import LanguageConfig, language_config_registry


class JavaScriptConfig(LanguageConfig):
    """Language configuration for JavaScript."""

    @property
    def language_id(self) -> str:
        return "javascript"

    @property
    def chunk_types(self) -> set[str]:
        return {
            "function_declaration",
            "function_expression",
            "arrow_function",
            "generator_function_declaration",
            "class_declaration",
            "method_definition",
            "export_statement",
        }

    def should_chunk_node(self, node_type: str) -> bool:
        """Override to handle variable_declarator specially."""
        # Note: In actual use, the JavaScript plugin handles variable_declarator filtering
        # For tests, we'll accept all chunk types since we can't easily filter by content
        return node_type in self.chunk_types or node_type == "variable_declarator"


class TestJavaScriptLanguageFeatures:
    """Test JavaScript-specific syntax and language features."""

    def setup_method(self):
        """Register JavaScript config for tests."""
        # Clear and register JavaScript config
        if not language_config_registry.get("javascript"):
            language_config_registry.register(JavaScriptConfig())

    def teardown_method(self):
        """Clean up after tests."""
        # Remove JavaScript config if it was added by tests
        if language_config_registry.get("javascript"):
            language_config_registry._configs.pop("javascript", None)

    def test_es6_syntax_support(self, tmp_path):
        """Test ES6+ syntax support (let, const, arrow functions)."""
        test_file = tmp_path / "es6_test.js"
        test_file.write_text(
            """
// ES6 variable declarations
let mutableVar = 10;
const CONSTANT_VALUE = 42;

// Arrow functions
const arrowFunc = () => {
    return "arrow function";
};

const implicitReturn = x => x * 2;

const multiParam = (a, b) => a + b;

// Array destructuring
const [first, second] = [1, 2];

// Object destructuring
const {name, age} = {name: "John", age: 30};

// Template literals
const greeting = `Hello, ${name}!`;

// Default parameters
const withDefaults = (x = 0, y = 10) => x + y;
""",
        )

        chunks = chunk_file(test_file, "javascript")

        # Debug: print what we got
        # for c in chunks:
        #     print(f"Type: {c.node_type}, Content: {c.content[:50]}...")

        # Should find arrow functions
        arrow_chunks = [c for c in chunks if "=>" in c.content]
        assert (
            len(arrow_chunks) >= 4
        )  # arrowFunc, implicitReturn, multiParam, withDefaults

        # Variable declarators are captured but don't include the const/let keyword
        # (that's part of the parent lexical_declaration node)
        var_declarator_chunks = [
            c for c in chunks if c.node_type == "variable_declarator"
        ]
        assert len(var_declarator_chunks) >= 8  # All variable declarations

        # Check that arrow functions are captured (either as arrow_function or within variable_declarator)
        arrow_content_chunks = [c for c in chunks if "=>" in c.content]
        assert len(arrow_content_chunks) >= 4

        # Verify arrow function syntax is captured
        all_content = "".join(c.content for c in chunks)
        assert "=>" in all_content
        assert "return" in all_content

    def test_jsx_tsx_handling(self, tmp_path):
        """Test JSX/TSX handling (if supported by the parser)."""
        # Test with .jsx extension
        jsx_file = tmp_path / "component.jsx"
        jsx_file.write_text(
            """
import React from 'react';

// Function component with JSX
const MyComponent = () => {
    return (
        <div className="container">
            <h1>Hello World</h1>
            <p>This is JSX</p>
        </div>
    );
};

// Class component
class ClassComponent extends React.Component {
    render() {
        return <div>Class Component</div>;
    }
}

// Component with props
const WithProps = ({ name, age }) => (
    <div>
        <span>Name: {name}</span>
        <span>Age: {age}</span>
    </div>
);

export { MyComponent, ClassComponent, WithProps };
""",
        )

        chunks = chunk_file(jsx_file, "javascript")

        # Should find components
        assert len(chunks) >= 3  # At least MyComponent, ClassComponent, WithProps

        # Check for arrow function components
        arrow_components = [c for c in chunks if "=>" in c.content and "<" in c.content]
        assert len(arrow_components) >= 2  # MyComponent, WithProps

        # Check for class component
        class_chunks = [c for c in chunks if c.node_type == "class_declaration"]
        assert len(class_chunks) >= 1
        assert "ClassComponent" in class_chunks[0].content

        # Check that render method is captured
        render_chunks = [c for c in chunks if "render()" in c.content]
        assert len(render_chunks) >= 1

    def test_arrow_function_variations(self, tmp_path):
        """Test different arrow function declaration styles."""
        test_file = tmp_path / "arrows.js"
        test_file.write_text(
            """
// Single parameter without parentheses
const single = x => x * 2;

// Multiple parameters
const multiple = (a, b, c) => a + b + c;

// No parameters
const noParams = () => console.log("hello");

// Block body
const blockBody = (x) => {
    const doubled = x * 2;
    console.log(doubled);
    return doubled;
};

// Async arrow functions
const asyncArrow = async () => {
    const result = await fetch('/api/data');
    return result.json();
};

// Arrow function returning object literal
const returnsObject = () => ({ name: "John", age: 30 });

// Higher-order arrow function
const createMultiplier = (factor) => (x) => x * factor;

// IIFE arrow function
((x) => console.log(x))("IIFE");

// Arrow functions in array methods
const numbers = [1, 2, 3];
const doubled = numbers.map(x => x * 2);
const filtered = numbers.filter(x => x > 1);
const sum = numbers.reduce((acc, x) => acc + x, 0);
""",
        )

        chunks = chunk_file(test_file, "javascript")

        # Should find various arrow functions
        arrow_chunks = [c for c in chunks if "=>" in c.content]
        assert len(arrow_chunks) >= 8  # At least the named ones

        # Check for async arrow function
        async_chunks = [c for c in chunks if "async" in c.content and "=>" in c.content]
        assert len(async_chunks) >= 1
        assert "asyncArrow" in async_chunks[0].content

        # Check for nested arrow functions (higher-order)
        nested_arrows = [c for c in chunks if c.content.count("=>") >= 2]
        assert len(nested_arrows) >= 1
        assert "createMultiplier" in nested_arrows[0].content

        # Check that arrow functions in expressions are captured
        map_chunks = [c for c in chunks if "map" in c.content and "=>" in c.content]
        assert len(map_chunks) >= 1

    def test_class_properties_and_methods(self, tmp_path):
        """Test class properties and various method types."""
        test_file = tmp_path / "classes.js"
        test_file.write_text(
            """
class ModernClass {
    // Class properties (ES2022)
    publicField = "public";
    #privateField = "private";
    static staticField = "static";

    // Constructor
    constructor(name) {
        this.name = name;
    }

    // Regular method
    regularMethod() {
        return this.publicField;
    }

    // Async method
    async asyncMethod() {
        const result = await Promise.resolve(42);
        return result;
    }

    // Generator method
    *generatorMethod() {
        yield 1;
        yield 2;
        yield 3;
    }

    // Getter
    get fullName() {
        return `${this.name} Smith`;
    }

    // Setter
    set fullName(value) {
        this.name = value.split(' ')[0];
    }

    // Static method
    static staticMethod() {
        return this.staticField;
    }

    // Private method (ES2022)
    #privateMethod() {
        return this.#privateField;
    }

    // Method with arrow function property
    arrowMethod = () => {
        return this.name;
    }
}

// Class expression
const ClassExpression = class {
    method() {
        return "class expression";
    }
};

// Class with inheritance
class ExtendedClass extends ModernClass {
    constructor(name, age) {
        super(name);
        this.age = age;
    }

    // Override method
    regularMethod() {
        return super.regularMethod() + " extended";
    }

    // New method
    newMethod() {
        return this.age;
    }
}
""",
        )

        chunks = chunk_file(test_file, "javascript")

        # Should find classes
        class_chunks = [c for c in chunks if c.node_type == "class_declaration"]
        assert len(class_chunks) >= 2  # ModernClass, ExtendedClass

        # Should find methods
        method_chunks = [c for c in chunks if c.node_type == "method_definition"]
        # Should include: constructor, regularMethod, asyncMethod, generatorMethod,
        # getter, setter, staticMethod, and methods in ExtendedClass
        assert len(method_chunks) >= 8

        # Check for async method
        async_methods = [c for c in method_chunks if "async" in c.content]
        assert len(async_methods) >= 1

        # Check for generator method
        generator_methods = [c for c in method_chunks if "*" in c.content]
        assert len(generator_methods) >= 1

        # Check for static method
        static_methods = [c for c in method_chunks if "static" in c.content]
        assert len(static_methods) >= 1

        # Check for arrow function property
        arrow_properties = [c for c in chunks if "arrowMethod =" in c.content]
        assert len(arrow_properties) >= 1

    def test_module_imports_exports(self, tmp_path):
        """Test various module import/export patterns."""
        test_file = tmp_path / "modules.js"
        test_file.write_text(
            """
// ES6 imports
import defaultExport from './module';
import * as name from './module';
import { export1 } from './module';
import { export1 as alias1 } from './module';
import { export1, export2 } from './module';
import { export1, export2 as alias2 } from './module';
import defaultExport, { export1 } from './module';
import defaultExport, * as name from './module';
import './side-effects';

// Dynamic imports
const loadModule = async () => {
    const module = await import('./dynamic-module');
    return module.default;
};

// Named exports
export const namedConst = 42;
export let namedLet = "hello";
export var namedVar = true;

export function namedFunction() {
    return "named function";
}

export class NamedClass {
    method() {
        return "named class";
    }
}

// Export with declaration
export const arrowExport = () => "arrow export";

// Default exports
export default function defaultFunction() {
    return "default function";
}

// Alternative default export patterns
const MyComponent = () => <div>Component</div>;
export default MyComponent;

// Re-exports
export { export1, export2 } from './other-module';
export * from './another-module';
export { default as OtherDefault } from './other-module';

// Export destructuring
const obj = { a: 1, b: 2, c: 3 };
export const { a, b } = obj;

// CommonJS (for compatibility)
const commonjsExport = () => "commonjs";
module.exports = commonjsExport;

// Mixed CommonJS
exports.mixedExport = function() {
    return "mixed";
};
""",
        )

        chunks = chunk_file(test_file, "javascript")

        # Should find exported functions and classes
        export_chunks = [
            c
            for c in chunks
            if c.node_type == "export_statement" or "export" in c.content
        ]
        assert len(export_chunks) >= 5

        # Check for named function export
        named_func_exports = [c for c in chunks if "export function" in c.content]
        assert len(named_func_exports) >= 1

        # Check for arrow function exports
        arrow_exports = [
            c for c in chunks if "export const" in c.content and "=>" in c.content
        ]
        assert len(arrow_exports) >= 1

        # Check for class export
        class_exports = [c for c in chunks if "export class" in c.content]
        assert len(class_exports) >= 1

        # Check for dynamic import function
        dynamic_import_chunks = [c for c in chunks if "import(" in c.content]
        assert len(dynamic_import_chunks) >= 1

    def test_async_await_patterns(self, tmp_path):
        """Test async/await patterns and Promise handling."""
        test_file = tmp_path / "async.js"
        test_file.write_text(
            """
// Async function declaration
async function fetchData() {
    const response = await fetch('/api/data');
    const data = await response.json();
    return data;
}

// Async arrow function
const fetchUser = async (userId) => {
    try {
        const user = await getUserById(userId);
        return user;
    } catch (error) {
        console.error('Error fetching user:', error);
        return null;
    }
};

// Async method in class
class DataService {
    async getData() {
        const result = await this.fetchFromAPI();
        return this.processData(result);
    }

    async fetchFromAPI() {
        return fetch('/api/endpoint');
    }

    processData(data) {
        return data.map(item => item.value);
    }
}

// Async generator
async function* asyncGenerator() {
    for (let i = 0; i < 5; i++) {
        await new Promise(resolve => setTimeout(resolve, 100));
        yield i;
    }
}

// Promise patterns
const promiseFunction = () => {
    return new Promise((resolve, reject) => {
        setTimeout(() => {
            resolve('Promise resolved');
        }, 1000);
    });
};

// Promise chaining
const chainedPromises = () => {
    return fetchData()
        .then(data => processData(data))
        .then(result => saveResult(result))
        .catch(error => handleError(error))
        .finally(() => cleanup());
};

// Parallel async operations
const parallelOperations = async () => {
    const [user, posts, comments] = await Promise.all([
        fetchUser(1),
        fetchPosts(1),
        fetchComments(1)
    ]);

    return { user, posts, comments };
};

// Async IIFE
(async () => {
    const data = await fetchData();
    console.log('IIFE data:', data);
})();

// Top-level await (ES2022)
const topLevelData = await fetchData();
""",
        )

        chunks = chunk_file(test_file, "javascript")

        # Should find async functions
        async_chunks = [c for c in chunks if "async" in c.content]
        assert len(async_chunks) >= 7  # Various async functions and methods

        # Check for async function declarations
        async_func_decl = [
            c
            for c in chunks
            if c.node_type == "function_declaration" and "async" in c.content
        ]
        assert len(async_func_decl) >= 1

        # Check for async arrow functions
        async_arrows = [c for c in chunks if "async" in c.content and "=>" in c.content]
        assert len(async_arrows) >= 3

        # Check for async generator
        async_gen = [c for c in chunks if "async function*" in c.content]
        assert len(async_gen) >= 1

        # Check for Promise patterns
        promise_chunks = [c for c in chunks if "Promise" in c.content]
        assert len(promise_chunks) >= 3

        # Check for async methods in class
        async_methods = [
            c
            for c in chunks
            if c.node_type == "method_definition" and "async" in c.content
        ]
        assert len(async_methods) >= 2

    def test_generator_functions(self, tmp_path):
        """Test generator function support."""
        test_file = tmp_path / "generators.js"
        test_file.write_text(
            """
// Generator function declaration
function* simpleGenerator() {
    yield 1;
    yield 2;
    yield 3;
}

// Generator function expression
const generatorExpr = function* () {
    let i = 0;
    while (true) {
        yield i++;
    }
};

// Generator method
class GeneratorClass {
    *generate() {
        yield* [1, 2, 3];
    }

    // Async generator method
    async *asyncGenerate() {
        for (let i = 0; i < 5; i++) {
            await delay(100);
            yield i;
        }
    }
}

// Generator with delegation
function* delegatingGenerator() {
    yield 'start';
    yield* anotherGenerator();
    yield 'end';
}

function* anotherGenerator() {
    yield 'middle1';
    yield 'middle2';
}

// Generator arrow function (not valid, but testing parser)
// const genArrow = *() => { yield 1; }; // This would be a syntax error

// Complex generator
function* fibonacci() {
    let [prev, curr] = [0, 1];
    while (true) {
        yield curr;
        [prev, curr] = [curr, prev + curr];
    }
}
""",
        )

        chunks = chunk_file(test_file, "javascript")

        # Should find generator functions
        generator_chunks = [
            c for c in chunks if c.node_type == "generator_function_declaration"
        ]
        assert (
            len(generator_chunks) >= 3
        )  # simpleGenerator, delegatingGenerator, anotherGenerator, fibonacci

        # Check for generator methods
        generator_methods = [
            c for c in chunks if c.node_type == "method_definition" and "*" in c.content
        ]
        assert len(generator_methods) >= 2  # generate, asyncGenerate

        # Verify generator content
        all_content = "".join(c.content for c in chunks)
        assert "yield" in all_content
        assert "yield*" in all_content
        assert "function*" in all_content

    def test_javascript_specific_edge_cases(self, tmp_path):
        """Test JavaScript-specific edge cases and syntax variations."""
        test_file = tmp_path / "edge_cases.js"
        test_file.write_text(
            """
// Function with default parameters and rest operator
function complexParams(a = 1, b = 2, ...rest) {
    return [a, b, ...rest];
}

// Computed property names
const propName = 'dynamicKey';
const obj = {
    [propName]: 'value',
    [`computed_${propName}`]: 'computed',
    methodName() {
        return 'shorthand method';
    }
};

// Destructuring in parameters
const destructureParams = ({ name, age = 18 }) => {
    return `${name} is ${age}`;
};

// Array methods with arrow functions
const processArray = (arr) => {
    return arr
        .filter(x => x > 0)
        .map(x => x * 2)
        .reduce((acc, x) => acc + x, 0);
};

// Optional chaining and nullish coalescing
const safeAccess = (obj) => {
    return obj?.property?.nested ?? 'default';
};

// BigInt literals
const bigNumber = 123456789012345678901234567890n;
const bigIntFunc = (n) => n * 2n;

// Symbol usage
const sym = Symbol('mySymbol');
const objWithSymbol = {
    [sym]: 'symbol value',
    [Symbol.iterator]: function* () {
        yield 1;
        yield 2;
    }
};

// Proxy and Reflect
const handler = {
    get(target, prop) {
        return Reflect.get(target, prop);
    }
};
const proxy = new Proxy({}, handler);

// Tagged template literals
const myTag = (strings, ...values) => {
    return strings.reduce((acc, str, i) => {
        return acc + str + (values[i] || '');
    }, '');
};
const tagged = myTag`Hello ${name}!`;

// Function with block scope
function blockScopes() {
    let outer = 1;
    {
        let inner = 2;
        const blockConst = 3;
    }
    // inner and blockConst not accessible here
}
""",
        )

        chunks = chunk_file(test_file, "javascript")

        # Verify various functions are captured
        function_chunks = [
            c for c in chunks if "function" in c.content or "=>" in c.content
        ]
        assert len(function_chunks) >= 6

        # Check for functions with rest parameters
        rest_param_chunks = [c for c in chunks if "...rest" in c.content]
        assert len(rest_param_chunks) >= 1

        # Check for arrow functions with destructuring
        destructure_chunks = [c for c in chunks if "({ name, age" in c.content]
        assert len(destructure_chunks) >= 1

        # Check for generator in object
        generator_in_obj = [
            c
            for c in chunks
            if "Symbol.iterator" in c.content and "function*" in c.content
        ]
        assert len(generator_in_obj) >= 1

        # Check for tagged template function
        tagged_chunks = [c for c in chunks if "strings, ...values" in c.content]
        assert len(tagged_chunks) >= 1

    def test_nested_functions_and_closures(self, tmp_path):
        """Test nested functions and closure patterns."""
        test_file = tmp_path / "nested.js"
        test_file.write_text(
            """
// Factory function with closures
function createCounter(initial = 0) {
    let count = initial;

    function increment() {
        count++;
        return count;
    }

    function decrement() {
        count--;
        return count;
    }

    const getCount = () => count;

    return {
        increment,
        decrement,
        getCount,
        // Inline arrow function
        reset: () => { count = initial; }
    };
}

// Deeply nested functions
function outerFunction() {
    function middleFunction() {
        function innerFunction() {
            function deeplyNested() {
                return "very deep";
            }
            return deeplyNested();
        }
        return innerFunction();
    }
    return middleFunction();
}

// IIFE with nested functions
const module = (function() {
    const privateVar = "private";

    function privateFunction() {
        return privateVar;
    }

    return {
        publicMethod: function() {
            return privateFunction();
        },
        anotherMethod: () => {
            const nested = () => privateVar.toUpperCase();
            return nested();
        }
    };
})();

// Class with nested functions in methods
class NestedInClass {
    processData(data) {
        function validateItem(item) {
            return item != null;
        }

        const transformItem = (item) => {
            const processNested = (value) => value * 2;
            return processNested(item.value);
        };

        return data
            .filter(validateItem)
            .map(transformItem);
    }
}
""",
        )

        chunks = chunk_file(test_file, "javascript")

        # Should find all functions including nested ones
        all_functions = [
            c
            for c in chunks
            if c.node_type
            in [
                "function_declaration",
                "function_expression",
                "arrow_function",
                "method_definition",
            ]
            or "function" in c.content
            or "=>" in c.content
        ]
        assert len(all_functions) >= 10  # Many nested functions

        # Check for functions with correct parent context
        nested_in_factory = [
            c
            for c in chunks
            if c.parent_context == "function_declaration"
            and (
                "increment" in c.content
                or "decrement" in c.content
                or "getCount" in c.content
            )
        ]
        assert len(nested_in_factory) >= 3

        # Check for deeply nested function
        deeply_nested = [c for c in chunks if "deeplyNested" in c.content]
        assert len(deeply_nested) >= 1
        # Parent context may not be preserved for deeply nested functions in basic config
        # Just verify it exists

        # Check for IIFE content
        iife_chunks = [
            c
            for c in chunks
            if "privateFunction" in c.content or "publicMethod" in c.content
        ]
        assert len(iife_chunks) >= 2


class TestJavaScriptPluginIntegration:
    """Test JavaScript plugin integration with the chunker system."""

    def setup_method(self):
        """Register JavaScript config for tests."""
        # Clear and register JavaScript config
        if not language_config_registry.get("javascript"):
            language_config_registry.register(JavaScriptConfig())

    def teardown_method(self):
        """Clean up after tests."""
        # Remove JavaScript config if it was added by tests
        if language_config_registry.get("javascript"):
            language_config_registry._configs.pop("javascript", None)

    def test_javascript_file_extensions(self, tmp_path):
        """Test that JavaScript plugin handles various file extensions."""
        extensions = [".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"]

        for ext in extensions:
            test_file = tmp_path / f"test{ext}"
            test_file.write_text(
                """
function testFunction() {
    return "test";
}

const arrowFunc = () => "arrow";

class TestClass {
    method() {
        return "method";
    }
}
""",
            )

            # Should be able to chunk files with any JavaScript extension
            chunks = chunk_file(test_file, "javascript")
            assert len(chunks) >= 3  # function, arrow, class

            # Verify chunks have correct file path
            for chunk in chunks:
                assert chunk.file_path == str(test_file)

    def test_export_statement_handling(self, tmp_path):
        """Test that export statements are properly processed."""
        test_file = tmp_path / "exports.js"
        test_file.write_text(
            """
// Export with function declaration
export function exportedFunction() {
    return "exported";
}

// Export with class
export class ExportedClass {
    method() {
        return "class method";
    }
}

// Export with const arrow function
export const exportedArrow = () => "arrow";

// Export default function
export default function defaultFunc() {
    return "default";
}

// Named exports at bottom
function helperFunc() {
    return "helper";
}

class HelperClass {
    assist() {
        return "assist";
    }
}

export { helperFunc, HelperClass };
""",
        )

        chunks = chunk_file(test_file, "javascript")

        # Should find exported items
        exported_chunks = [c for c in chunks if "export" in c.content]
        assert len(exported_chunks) >= 4

        # Verify we capture the actual function/class, not just the export statement
        func_names = [
            "exportedFunction",
            "ExportedClass",
            "exportedArrow",
            "defaultFunc",
        ]
        for name in func_names:
            assert any(name in c.content for c in chunks)

    def test_variable_declarator_filtering(self, tmp_path):
        """Test variable declarator handling with functions."""
        test_file = tmp_path / "variables.js"
        test_file.write_text(
            """
// Should be included (contains function)
const funcVar = function() { return 1; };
const arrowVar = () => 2;
let asyncVar = async () => await fetch('/api');

// Should NOT be included (no function) - but our test config includes all variable_declarators
const numberVar = 42;
let stringVar = "hello";
var boolVar = true;
const objectVar = { key: "value" };
const arrayVar = [1, 2, 3];

// Mixed declarations
const mixed1 = 100, mixed2 = () => 200;

// Complex function assignments
const higherOrder = (x) => (y) => x + y;
const composed = compose(
    x => x * 2,
    x => x + 1
);
""",
        )

        chunks = chunk_file(test_file, "javascript")

        # With our test config, all variable declarators are included
        var_chunks = [c for c in chunks if c.node_type == "variable_declarator"]

        # Count those that have functions
        func_var_chunks = [
            c for c in var_chunks if "function" in c.content or "=>" in c.content
        ]
        assert (
            len(func_var_chunks) >= 5
        )  # funcVar, arrowVar, asyncVar, mixed2, higherOrder, composed

        # Also check that arrow functions themselves are captured
        arrow_chunks = [c for c in chunks if c.node_type == "arrow_function"]
        assert len(arrow_chunks) >= 5

        # Note: The JavaScript plugin would filter out non-function variable declarators,
        # but our test config doesn't have that logic

    def test_complex_real_world_patterns(self, tmp_path):
        """Test complex real-world JavaScript patterns."""
        test_file = tmp_path / "real_world.js"
        test_file.write_text(
            """
// React-like component
const TodoList = ({ todos, onToggle }) => {
    const [filter, setFilter] = useState('all');

    const filteredTodos = useMemo(() => {
        switch (filter) {
            case 'active':
                return todos.filter(todo => !todo.completed);
            case 'completed':
                return todos.filter(todo => todo.completed);
            default:
                return todos;
        }
    }, [todos, filter]);

    return (
        <div>
            {filteredTodos.map(todo => (
                <TodoItem
                    key={todo.id}
                    todo={todo}
                    onToggle={onToggle}
                />
            ))}
        </div>
    );
};

// Express-like route handler
const createUserHandler = async (req, res, next) => {
    try {
        const { name, email } = req.body;

        const existingUser = await User.findOne({ email });
        if (existingUser) {
            return res.status(400).json({ error: 'User already exists' });
        }

        const newUser = new User({ name, email });
        await newUser.save();

        res.status(201).json({
            message: 'User created successfully',
            user: newUser
        });
    } catch (error) {
        next(error);
    }
};

// Redux-like reducer
const todosReducer = (state = initialState, action) => {
    switch (action.type) {
        case 'ADD_TODO':
            return {
                ...state,
                todos: [...state.todos, action.payload]
            };
        case 'TOGGLE_TODO':
            return {
                ...state,
                todos: state.todos.map(todo =>
                    todo.id === action.payload
                        ? { ...todo, completed: !todo.completed }
                        : todo
                )
            };
        default:
            return state;
    }
};

// Utility with currying
const pipe = (...fns) => x => fns.reduce((v, f) => f(v), x);

const processData = pipe(
    data => data.filter(item => item.active),
    data => data.map(item => ({ ...item, processed: true })),
    data => data.sort((a, b) => a.name.localeCompare(b.name))
);

// Class with decorators (if supported)
class APIController {
    @authenticated
    @rateLimit(100)
    async getUsers(req, res) {
        const users = await this.userService.findAll();
        res.json(users);
    }

    @authenticated
    @validateBody(userSchema)
    async createUser(req, res) {
        const user = await this.userService.create(req.body);
        res.status(201).json(user);
    }
}
""",
        )

        chunks = chunk_file(test_file, "javascript")

        # Should find various real-world patterns
        assert len(chunks) >= 6

        # Check for React component
        react_chunks = [c for c in chunks if "TodoList" in c.content]
        assert len(react_chunks) >= 1
        assert "useState" in react_chunks[0].content

        # Check for async handler
        async_handlers = [
            c for c in chunks if "async" in c.content and "req, res" in c.content
        ]
        assert len(async_handlers) >= 1

        # Check for reducer pattern
        reducer_chunks = [c for c in chunks if "todosReducer" in c.content]
        assert len(reducer_chunks) >= 1
        assert "switch" in reducer_chunks[0].content

        # Check for curried functions
        curry_chunks = [
            c
            for c in chunks
            if "pipe" in c.content or ("=>" in c.content and "reduce" in c.content)
        ]
        assert len(curry_chunks) >= 1

        # Check for class methods
        method_chunks = [c for c in chunks if c.node_type == "method_definition"]
        assert len(method_chunks) >= 2  # getUsers, createUser
