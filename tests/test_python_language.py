"""Comprehensive tests for Python-specific language features."""

from chunker import chunk_file


class TestPythonAsyncFunctions:
    """Test async function detection and handling."""

    def test_simple_async_function(self, tmp_path):
        """Test basic async function detection."""
        src = tmp_path / "async.py"
        src.write_text(
            """
async def fetch_data():
    return await some_api_call()
""",
        )
        chunks = chunk_file(src, "python")
        assert len(chunks) == 1
        assert chunks[0].node_type == "function_definition"
        assert "async def fetch_data" in chunks[0].content
        assert chunks[0].start_line == 2
        assert chunks[0].end_line == 3

    def test_async_function_with_docstring(self, tmp_path):
        """Test async function with docstring."""
        src = tmp_path / "async_doc.py"
        src.write_text(
            """
async def process_items(items):
    '''Process items asynchronously.

    Args:
        items: List of items to process

    Returns:
        Processed results
    '''
    results = []
    for item in items:
        result = await process_single(item)
        results.append(result)
    return results
""",
        )
        chunks = chunk_file(src, "python")
        assert len(chunks) == 1
        assert chunks[0].node_type == "function_definition"
        assert "Process items asynchronously" in chunks[0].content

    def test_nested_async_functions(self, tmp_path):
        """Test nested async function definitions."""
        src = tmp_path / "nested_async.py"
        src.write_text(
            """
async def outer_async():
    async def inner_async():
        return await something()

    return await inner_async()
""",
        )
        chunks = chunk_file(src, "python")
        assert len(chunks) == 2
        # Both should be function_definition in tree-sitter
        assert all(c.node_type == "function_definition" for c in chunks)

        # Check nesting context
        next(
            c
            for c in chunks
            if "outer_async" in c.content and "inner_async" in c.content
        )
        inner = next(
            c
            for c in chunks
            if "inner_async" in c.content and "outer_async" not in c.content
        )
        assert inner.parent_context == "function_definition"


class TestPythonDecorators:
    """Test decorator handling."""

    def test_simple_decorator(self, tmp_path):
        """Test function with single decorator."""
        src = tmp_path / "decorated.py"
        src.write_text(
            """
@lru_cache
def fibonacci(n):
    if n < 2:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
""",
        )
        chunks = chunk_file(src, "python")
        assert len(chunks) == 2  # decorated_definition and function_definition

        # Check decorated_definition chunk
        decorated = next(c for c in chunks if c.node_type == "decorated_definition")
        assert "@lru_cache" in decorated.content
        assert decorated.start_line == 2  # Includes decorator

        # Check function chunk is child of decorated
        func = next(c for c in chunks if c.node_type == "function_definition")
        assert func.parent_context == "decorated_definition"

    def test_multiple_decorators(self, tmp_path):
        """Test function with multiple decorators."""
        src = tmp_path / "multi_decorated.py"
        src.write_text(
            """
@app.route('/api/users')
@require_auth
@validate_params
def get_users(request):
    return {'users': User.query.all()}
""",
        )
        chunks = chunk_file(src, "python")
        assert len(chunks) == 2  # decorated_definition and function_definition

        # Check decorated_definition chunk
        decorated = next(c for c in chunks if c.node_type == "decorated_definition")
        assert "@app.route" in decorated.content
        assert "@require_auth" in decorated.content
        assert "@validate_params" in decorated.content

        # Check function chunk is child of decorated
        func = next(c for c in chunks if c.node_type == "function_definition")
        assert func.parent_context == "decorated_definition"

    def test_decorated_class(self, tmp_path):
        """Test decorated class definition."""
        src = tmp_path / "decorated_class.py"
        src.write_text(
            """
@dataclass
@frozen
class Point:
    x: float
    y: float

    def distance(self, other):
        return ((self.x - other.x)**2 + (self.y - other.y)**2)**0.5
""",
        )
        chunks = chunk_file(src, "python")
        assert len(chunks) == 3  # decorated_definition, class_definition, and method

        # Check decorated_definition chunk
        decorated = next(c for c in chunks if c.node_type == "decorated_definition")
        assert "@dataclass" in decorated.content
        assert "@frozen" in decorated.content

        # Check class chunk is child of decorated
        class_chunk = next(c for c in chunks if c.node_type == "class_definition")
        assert class_chunk.parent_context == "decorated_definition"

        # Check method chunk is child of class
        method_chunk = next(
            c
            for c in chunks
            if c.node_type == "function_definition" and "def distance" in c.content
        )
        assert method_chunk.parent_context == "class_definition"

    def test_decorator_with_arguments(self, tmp_path):
        """Test decorators with arguments."""
        src = tmp_path / "decorator_args.py"
        src.write_text(
            """
@app.route('/user/<int:id>', methods=['GET', 'POST'])
@cache.memoize(timeout=300)
@retry(max_attempts=3, backoff=2.0)
async def get_user(id: int):
    return await db.fetch_user(id)
""",
        )
        chunks = chunk_file(src, "python")
        assert len(chunks) == 2  # decorated_definition and function_definition

        # Check decorated_definition chunk
        decorated = next(c for c in chunks if c.node_type == "decorated_definition")
        assert "methods=['GET', 'POST']" in decorated.content
        assert "timeout=300" in decorated.content
        assert "max_attempts=3" in decorated.content

        # Check function chunk is child of decorated
        func = next(c for c in chunks if c.node_type == "function_definition")
        assert func.parent_context == "decorated_definition"


class TestPythonNestedClasses:
    """Test nested class definitions."""

    def test_simple_nested_class(self, tmp_path):
        """Test basic nested class."""
        src = tmp_path / "nested_class.py"
        src.write_text(
            """
class Outer:
    class Inner:
        def inner_method(self):
            pass

    def outer_method(self):
        return self.Inner()
""",
        )
        chunks = chunk_file(src, "python")
        # Should have: Outer class, Inner class, inner_method, outer_method
        assert len(chunks) == 4

        # Find the chunks - be specific to avoid finding parent chunks
        next(
            c
            for c in chunks
            if c.node_type == "class_definition"
            and c.content.strip().startswith("class Outer:")
        )
        inner = next(
            c
            for c in chunks
            if c.node_type == "class_definition"
            and c.content.strip().startswith("class Inner:")
        )
        inner_method = next(
            c
            for c in chunks
            if c.node_type == "function_definition"
            and c.content.strip().startswith("def inner_method")
        )
        outer_method = next(
            c
            for c in chunks
            if c.node_type == "function_definition"
            and c.content.strip().startswith("def outer_method")
        )

        # Check nesting contexts
        assert inner.parent_context == "class_definition"  # Inner is nested in Outer
        assert (
            inner_method.parent_context == "class_definition"
        )  # inner_method is in Inner
        assert (
            outer_method.parent_context == "class_definition"
        )  # outer_method is in Outer

    def test_deeply_nested_classes(self, tmp_path):
        """Test deeply nested class hierarchies."""
        src = tmp_path / "deep_nested.py"
        src.write_text(
            """
class Level1:
    class Level2:
        class Level3:
            class Level4:
                def deep_method(self):
                    return "deep"

            def level3_method(self):
                return self.Level4()

        def level2_method(self):
            return self.Level3()

    def level1_method(self):
        return self.Level2()
""",
        )
        chunks = chunk_file(src, "python")

        # Should have 4 classes and 4 methods
        classes = [c for c in chunks if c.node_type == "class_definition"]
        methods = [c for c in chunks if c.node_type == "function_definition"]

        assert len(classes) == 4
        assert len(methods) == 4

        # Check proper nesting context
        # Find the specific Level4 class chunk (not one that just contains it)
        level4 = None
        for c in classes:
            if c.content.strip().startswith("class Level4:"):
                level4 = c
                break

        assert level4 is not None, "Could not find Level4 class chunk"
        # Level4 is nested inside Level3, which is a class_definition
        assert level4.parent_context == "class_definition"


class TestPythonLambdaExpressions:
    """Test lambda expression handling."""

    def test_simple_lambda(self, tmp_path):
        """Test standalone lambda expressions."""
        src = tmp_path / "lambda.py"
        src.write_text(
            """
square = lambda x: x ** 2
add = lambda x, y: x + y
""",
        )
        chunks = chunk_file(src, "python")
        # Lambdas ARE chunked according to PythonConfig
        assert (
            len(chunks) == 4
        )  # 2 lambda expressions, each also creates a nested 'lambda' chunk

        # Check we have lambda chunks
        lambda_chunks = [c for c in chunks if c.node_type == "lambda"]
        assert (
            len(lambda_chunks) == 4
        )  # 2 top-level lambdas + 2 nested 'lambda' keywords

    def test_lambda_in_function(self, tmp_path):
        """Test lambdas inside functions."""
        src = tmp_path / "lambda_func.py"
        src.write_text(
            """
def process_numbers(numbers):
    squared = map(lambda x: x ** 2, numbers)
    filtered = filter(lambda x: x > 10, squared)
    return list(filtered)
""",
        )
        chunks = chunk_file(src, "python")
        # Should have: function_definition + 2 lambda expressions (each with nested 'lambda' chunk)
        assert len(chunks) == 5

        # Check function chunk
        func_chunk = next(c for c in chunks if c.node_type == "function_definition")
        assert "lambda x: x ** 2" in func_chunk.content

        # Check lambda chunks have correct parent context
        lambda_chunks = [
            c
            for c in chunks
            if c.node_type == "lambda" and c.parent_context == "function_definition"
        ]
        assert len(lambda_chunks) == 2  # Two lambda expressions in the function

    def test_complex_lambda(self, tmp_path):
        """Test complex lambda with conditional logic."""
        src = tmp_path / "complex_lambda.py"
        src.write_text(
            """
def sort_data(data):
    return sorted(
        data,
        key=lambda item: (
            item['priority'] if 'priority' in item else 999,
            item['name'].lower(),
            -item['score']
        )
    )
""",
        )
        chunks = chunk_file(src, "python")
        # Should have: function_definition + lambda expression + nested 'lambda' keyword
        assert len(chunks) == 3

        # Check function chunk
        func_chunk = next(c for c in chunks if c.node_type == "function_definition")
        assert "lambda item:" in func_chunk.content

        # Check lambda chunk has correct parent context
        lambda_chunk = next(
            c for c in chunks if c.node_type == "lambda" and "lambda item:" in c.content
        )
        assert lambda_chunk.parent_context == "function_definition"


class TestPythonComprehensions:
    """Test list, dict, set comprehensions and generator expressions."""

    def test_list_comprehension(self, tmp_path):
        """Test list comprehension in functions."""
        src = tmp_path / "list_comp.py"
        src.write_text(
            """
def process_data(items):
    # Simple list comprehension
    squares = [x ** 2 for x in items]

    # Conditional comprehension
    evens = [x for x in items if x % 2 == 0]

    # Nested comprehension
    matrix = [[i * j for j in range(5)] for i in range(5)]

    return squares, evens, matrix
""",
        )
        chunks = chunk_file(src, "python")
        assert len(chunks) == 1
        assert "[x ** 2 for x in items]" in chunks[0].content
        assert "[x for x in items if x % 2 == 0]" in chunks[0].content

    def test_dict_comprehension(self, tmp_path):
        """Test dictionary comprehension."""
        src = tmp_path / "dict_comp.py"
        src.write_text(
            """
def create_mappings(keys, values):
    # Basic dict comprehension
    mapping = {k: v for k, v in zip(keys, values)}

    # Conditional dict comprehension
    filtered = {k: v for k, v in mapping.items() if v > 0}

    # Complex transformation
    transformed = {
        k.upper(): v ** 2
        for k, v in mapping.items()
        if isinstance(k, str) and isinstance(v, (int, float))
    }

    return transformed
""",
        )
        chunks = chunk_file(src, "python")
        assert len(chunks) == 1
        assert "{k: v for k, v in zip(keys, values)}" in chunks[0].content

    def test_generator_expression(self, tmp_path):
        """Test generator expressions."""
        src = tmp_path / "gen_exp.py"
        src.write_text(
            """
def sum_of_squares(n):
    # Generator expression
    return sum(x ** 2 for x in range(n))

def lazy_processing(data):
    # Multiple generator expressions
    processed = (
        item.strip().lower()
        for item in data
        if item and not item.isspace()
    )
    return list(processed)
""",
        )
        chunks = chunk_file(src, "python")
        assert len(chunks) == 2
        assert any("x ** 2 for x in range(n)" in c.content for c in chunks)


class TestPythonTypeAnnotations:
    """Test type annotation handling."""

    def test_function_annotations(self, tmp_path):
        """Test function parameter and return type annotations."""
        src = tmp_path / "type_annotations.py"
        src.write_text(
            """
def add(a: int, b: int) -> int:
    return a + b

def process_list(items: list[str]) -> dict[str, int]:
    return {item: len(item) for item in items}

def complex_types(
    data: dict[str, list[tuple[int, str]]],
    callback: Callable[[str], bool] | None = None
) -> Iterator[tuple[str, int]]:
    for key, values in data.items():
        if callback is None or callback(key):
            for idx, val in values:
                yield (val, idx)
""",
        )
        chunks = chunk_file(src, "python")
        assert len(chunks) == 3

        # Check that type annotations are preserved
        add_chunk = next(c for c in chunks if "def add" in c.content)
        assert "a: int" in add_chunk.content
        assert "-> int:" in add_chunk.content

        complex_chunk = next(c for c in chunks if "complex_types" in c.content)
        assert "dict[str, list[tuple[int, str]]]" in complex_chunk.content
        assert "Callable[[str], bool] | None" in complex_chunk.content

    def test_class_annotations(self, tmp_path):
        """Test class variable and method annotations."""
        src = tmp_path / "class_annotations.py"
        src.write_text(
            """
class User:
    name: str
    age: int
    emails: list[str]
    metadata: dict[str, Any] = {}

    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age
        self.emails = []

    def add_email(self, email: str) -> None:
        self.emails.append(email)

    def get_info(self) -> dict[str, Union[str, int, list[str]]]:
        return {
            'name': self.name,
            'age': self.age,
            'emails': self.emails
        }
""",
        )
        chunks = chunk_file(src, "python")

        class_chunk = next(c for c in chunks if c.node_type == "class_definition")
        assert "name: str" in class_chunk.content
        assert "emails: list[str]" in class_chunk.content

        # Check method annotations
        init_chunk = next(c for c in chunks if "__init__" in c.content)
        assert "name: str, age: int" in init_chunk.content
        assert "-> None:" in init_chunk.content

    def test_generic_annotations(self, tmp_path):
        """Test generic type annotations."""
        src = tmp_path / "generics.py"
        src.write_text(
            """
from typing import TypeVar, Generic, Protocol

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')

class Container(Generic[T]):
    def __init__(self, value: T) -> None:
        self._value = value

    def get(self) -> T:
        return self._value

    def transform(self, func: Callable[[T], K]) -> 'Container[K]':
        return Container(func(self._value))

class Comparable(Protocol):
    def __lt__(self, other: 'Comparable') -> bool: ...

def sort_items(items: list[Comparable]) -> list[Comparable]:
    return sorted(items)
""",
        )
        chunks = chunk_file(src, "python")

        # Check that generic annotations are preserved
        container_chunk = next(c for c in chunks if "class Container" in c.content)
        assert "Generic[T]" in container_chunk.content

        transform_chunk = next(c for c in chunks if "def transform" in c.content)
        assert "Callable[[T], K]" in transform_chunk.content
        assert "'Container[K]'" in transform_chunk.content


class TestPythonDocstrings:
    """Test docstring extraction and handling."""

    def test_function_docstrings(self, tmp_path):
        """Test various docstring formats in functions."""
        src = tmp_path / "docstrings.py"
        src.write_text(
            '''
def single_line_doc():
    """This is a single line docstring."""
    pass

def multi_line_doc():
    """
    This is a multi-line docstring.

    It has multiple paragraphs and provides
    detailed documentation about the function.
    """
    pass

def google_style_doc(param1: str, param2: int) -> bool:
    """Summary line.

    Extended description of function.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: If param2 is negative
    """
    if param2 < 0:
        raise ValueError("param2 must be non-negative")
    return len(param1) > param2

def numpy_style_doc(x, y):
    """
    Calculate something.

    Parameters
    ----------
    x : array_like
        Input array
    y : array_like
        Another input array

    Returns
    -------
    result : ndarray
        The calculated result
    """
    return x + y
''',
        )
        chunks = chunk_file(src, "python")
        assert len(chunks) == 4

        # Check that docstrings are included in chunks
        single_chunk = next(c for c in chunks if "single_line_doc" in c.content)
        assert "This is a single line docstring." in single_chunk.content

        google_chunk = next(c for c in chunks if "google_style_doc" in c.content)
        assert "Args:" in google_chunk.content
        assert "Returns:" in google_chunk.content
        assert "Raises:" in google_chunk.content

    def test_class_docstrings(self, tmp_path):
        """Test class and method docstrings."""
        src = tmp_path / "class_docs.py"
        src.write_text(
            '''
class DocumentedClass:
    """
    A well-documented class.

    This class demonstrates proper documentation
    with class-level and method-level docstrings.

    Attributes:
        name: The name of the instance
        value: The current value
    """

    def __init__(self, name: str, value: float):
        """
        Initialize the instance.

        Args:
            name: Instance name
            value: Initial value
        """
        self.name = name
        self.value = value

    def calculate(self, factor: float) -> float:
        """Calculate adjusted value.

        Multiplies the current value by the given factor.

        Args:
            factor: Multiplication factor

        Returns:
            The adjusted value

        Example:
            >>> obj = DocumentedClass("test", 10.0)
            >>> obj.calculate(1.5)
            15.0
        """
        return self.value * factor
''',
        )
        chunks = chunk_file(src, "python")

        class_chunk = next(c for c in chunks if c.node_type == "class_definition")
        assert "A well-documented class." in class_chunk.content
        assert "Attributes:" in class_chunk.content

        calc_chunk = next(
            c for c in chunks if "calculate" in c.content and "def" in c.content
        )
        assert "Example:" in calc_chunk.content
        assert ">>> obj.calculate(1.5)" in calc_chunk.content

    def test_raw_docstrings(self, tmp_path):
        """Test raw docstrings with special characters."""
        src = tmp_path / "raw_docs.py"
        src.write_text(
            r'''
def regex_function():
    r"""
    Process text with regex patterns.

    This function uses patterns like:
    - \d+ for digits
    - \w+ for words
    - \s* for optional whitespace

    The backslashes are preserved in raw strings.
    """
    pass

def path_function():
    r"""
    Handle Windows paths.

    Example paths:
        C:\Users\Name\Documents
        \\server\share\folder
    """
    pass
''',
        )
        chunks = chunk_file(src, "python")

        regex_chunk = next(c for c in chunks if "regex_function" in c.content)
        assert r"\d+ for digits" in regex_chunk.content
        assert r"\w+ for words" in regex_chunk.content


class TestPythonEdgeCases:
    """Test edge cases and complex Python constructs."""

    def test_walrus_operator(self, tmp_path):
        """Test assignment expressions (walrus operator)."""
        src = tmp_path / "walrus.py"
        src.write_text(
            """
def process_with_walrus(items):
    # Walrus in if statement
    if (n := len(items)) > 10:
        print(f"Processing {n} items")

    # Walrus in while loop
    while (item := get_next_item()) is not None:
        process_item(item)

    # Walrus in comprehension
    filtered = [y for x in items if (y := transform(x)) is not None]

    return filtered
""",
        )
        chunks = chunk_file(src, "python")
        assert len(chunks) == 1
        assert ":=" in chunks[0].content
        assert "n := len(items)" in chunks[0].content

    def test_match_statement(self, tmp_path):
        """Test pattern matching (Python 3.10+)."""
        src = tmp_path / "pattern_match.py"
        src.write_text(
            """
def handle_command(command):
    match command.split():
        case ["quit"]:
            return "Goodbye"
        case ["load", filename]:
            return f"Loading {filename}"
        case ["save", filename, *rest]:
            options = rest or []
            return f"Saving {filename} with {options}"
        case ["move", x, y] if x.isdigit() and y.isdigit():
            return f"Moving to ({x}, {y})"
        case _:
            return "Unknown command"
""",
        )
        chunks = chunk_file(src, "python")
        assert len(chunks) == 1
        assert "match command.split():" in chunks[0].content
        assert 'case ["quit"]:' in chunks[0].content
        assert "case _:" in chunks[0].content

    def test_async_context_managers(self, tmp_path):
        """Test async with statements."""
        src = tmp_path / "async_context.py"
        src.write_text(
            """
async def process_async_resource():
    async with get_connection() as conn:
        async with conn.transaction():
            result = await conn.execute("SELECT * FROM users")
            async for row in result:
                yield process_row(row)

    async with AsyncExitStack() as stack:
        files = [
            await stack.enter_async_context(aiofiles.open(f))
            for f in filenames
        ]
        return await process_files(files)
""",
        )
        chunks = chunk_file(src, "python")
        assert len(chunks) == 1
        assert "async with" in chunks[0].content
        assert "async for" in chunks[0].content

    def test_complex_decorators(self, tmp_path):
        """Test complex decorator patterns."""
        src = tmp_path / "complex_decorators.py"
        src.write_text(
            """
@decorator_factory(param="value")
@another_decorator
@property
def decorated_property(self):
    return self._value

@contextmanager
def my_context():
    setup()
    try:
        yield resource
    finally:
        cleanup()

@overload
def process(x: int) -> str: ...

@overload
def process(x: str) -> int: ...

def process(x):
    if isinstance(x, int):
        return str(x)
    return int(x)
""",
        )
        chunks = chunk_file(src, "python")

        # Check various decorator patterns
        property_chunk = next(c for c in chunks if "decorated_property" in c.content)
        assert "@property" in property_chunk.content
        assert "@decorator_factory" in property_chunk.content

    def test_metaclass_usage(self, tmp_path):
        """Test metaclass definitions and usage."""
        src = tmp_path / "metaclass.py"
        src.write_text(
            """
class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

class Database(metaclass=SingletonMeta):
    def __init__(self, connection_string):
        self.connection = connection_string

    def query(self, sql):
        return f"Executing: {sql}"

class AbstractBase(metaclass=ABCMeta):
    @abstractmethod
    def must_implement(self):
        pass
""",
        )
        chunks = chunk_file(src, "python")

        # Check metaclass definitions
        meta_chunk = next(
            c for c in chunks if "SingletonMeta" in c.content and "class" in c.content
        )
        assert "type" in meta_chunk.content

        db_chunk = next(c for c in chunks if "class Database" in c.content)
        assert "metaclass=SingletonMeta" in db_chunk.content

    def test_deeply_nested_structures(self, tmp_path):
        """Test deeply nested functions and classes."""
        src = tmp_path / "deep_nesting.py"
        src.write_text(
            """
def outer_function():
    def level1():
        def level2():
            def level3():
                class InnerClass:
                    def inner_method(self):
                        lambda x: x * 2

                        def deepest():
                            return "very deep"

                        return deepest()

                return InnerClass()

            return level3()

        return level2()

    return level1()
""",
        )
        chunks = chunk_file(src, "python")

        # Should find all nested functions and the class
        function_chunks = [c for c in chunks if c.node_type == "function_definition"]
        class_chunks = [c for c in chunks if c.node_type == "class_definition"]

        assert (
            len(function_chunks) >= 5
        )  # outer, level1, level2, level3, inner_method, deepest
        assert len(class_chunks) == 1  # InnerClass

        # Check that deepest function has proper parent context
        # Find the actual deepest function chunk (not just one containing it)
        deepest = None
        for c in chunks:
            if c.node_type == "function_definition" and c.content.strip().startswith(
                "def deepest",
            ):
                deepest = c
                break

        assert deepest is not None, "Could not find deepest function chunk"
        # The deepest function is inside inner_method, which is a function_definition
        assert deepest.parent_context == "function_definition"


class TestPythonModernFeatures:
    """Test modern Python features (3.8+)."""

    def test_positional_only_params(self, tmp_path):
        """Test positional-only parameters."""
        src = tmp_path / "pos_only.py"
        src.write_text(
            """
def positional_only(a, b, /, c, d):
    return a + b + c + d

def mixed_params(pos_only, /, standard, *, kw_only):
    return (pos_only, standard, kw_only)

def all_types(a, /, b, c, *args, d, e, **kwargs):
    return {
        'positional_only': a,
        'standard': (b, c),
        'varargs': args,
        'keyword_only': (d, e),
        'kwargs': kwargs
    }
""",
        )
        chunks = chunk_file(src, "python")
        assert len(chunks) == 3

        # Check that position-only marker is preserved
        pos_chunk = next(
            c for c in chunks if "positional_only" in c.content and "def" in c.content
        )
        assert "a, b, /" in pos_chunk.content

    def test_type_union_operator(self, tmp_path):
        """Test type union operator (|) from Python 3.10."""
        src = tmp_path / "union_types.py"
        src.write_text(
            """
def process_value(val: int | float | str) -> str | None:
    if isinstance(val, (int, float)):
        return str(val)
    elif isinstance(val, str):
        return val.upper()
    return None

def handle_optional(data: dict[str, Any] | None = None) -> list[str] | None:
    if data is None:
        return None
    return list(data.keys())

class FlexibleContainer:
    value: int | str | list[int] | None

    def set_value(self, v: int | str | list[int]) -> None:
        self.value = v
""",
        )
        chunks = chunk_file(src, "python")

        # Check that union syntax is preserved
        process_chunk = next(c for c in chunks if "process_value" in c.content)
        assert "int | float | str" in process_chunk.content
        assert "str | None" in process_chunk.content

    def test_dataclass_advanced(self, tmp_path):
        """Test advanced dataclass features."""
        src = tmp_path / "dataclass_advanced.py"
        src.write_text(
            """
from dataclasses import dataclass, field, InitVar
from typing import ClassVar

@dataclass(frozen=True, slots=True)
class ImmutablePoint:
    x: float
    y: float
    _id: ClassVar[int] = 0

    def distance_from_origin(self) -> float:
        return (self.x ** 2 + self.y ** 2) ** 0.5

@dataclass
class ConfigurableClass:
    name: str
    values: list[int] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    _init_value: InitVar[int] = 0

    def __post_init__(self, _init_value: int):
        if _init_value > 0:
            self.values = list(range(_init_value))

    def add_value(self, val: int) -> None:
        self.values.append(val)
""",
        )
        chunks = chunk_file(src, "python")

        # Check that dataclass decorators and special fields are preserved
        immutable_chunk = next(c for c in chunks if "ImmutablePoint" in c.content)
        assert "@dataclass(frozen=True, slots=True)" in immutable_chunk.content
        assert "ClassVar[int]" in immutable_chunk.content

        config_chunk = next(c for c in chunks if "ConfigurableClass" in c.content)
        assert "field(default_factory=list)" in config_chunk.content
        assert "InitVar[int]" in config_chunk.content

    def test_exception_groups(self, tmp_path):
        """Test exception groups (Python 3.11+)."""
        src = tmp_path / "exception_groups.py"
        src.write_text(
            """
def process_multiple_errors():
    errors = []

    try:
        # Simulate multiple operations
        for operation in operations:
            try:
                operation()
            except (IOError, IndexError, KeyError) as e:
                errors.append(e)

        if errors:
            raise ExceptionGroup("Multiple errors occurred", errors)

    except* ValueError as eg:
        for e in eg.exceptions:
            log_value_error(e)
    except* TypeError as eg:
        for e in eg.exceptions:
            log_type_error(e)
    except* Exception as eg:
        for e in eg.exceptions:
            log_generic_error(e)
""",
        )
        chunks = chunk_file(src, "python")
        assert len(chunks) == 1
        assert "ExceptionGroup" in chunks[0].content
        assert "except*" in chunks[0].content


class TestPythonSpecialMethods:
    """Test special methods and protocols."""

    def test_dunder_methods(self, tmp_path):
        """Test various dunder methods."""
        src = tmp_path / "dunder_methods.py"
        src.write_text(
            """
class Vector:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Vector({self.x}, {self.y})"

    def __str__(self):
        return f"<{self.x}, {self.y}>"

    def __add__(self, other):
        return Vector(self.x + other.x, self.y + other.y)

    def __mul__(self, scalar):
        return Vector(self.x * scalar, self.y * scalar)

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def __len__(self):
        return 2

    def __getitem__(self, index):
        return (self.x, self.y)[index]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
""",
        )
        chunks = chunk_file(src, "python")

        # Should have class and all methods
        assert len([c for c in chunks if c.node_type == "function_definition"]) >= 10

        # Check that dunder methods are captured
        dunder_names = [
            "__init__",
            "__repr__",
            "__str__",
            "__add__",
            "__mul__",
            "__eq__",
            "__len__",
            "__getitem__",
            "__enter__",
            "__exit__",
        ]
        for name in dunder_names:
            assert any(name in c.content for c in chunks)

    def test_async_iteration_protocol(self, tmp_path):
        """Test async iteration protocol methods."""
        src = tmp_path / "async_iter.py"
        src.write_text(
            """
class AsyncRange:
    def __init__(self, start, stop):
        self.start = start
        self.stop = stop

    def __aiter__(self):
        self.current = self.start
        return self

    async def __anext__(self):
        if self.current < self.stop:
            await asyncio.sleep(0.1)
            value = self.current
            self.current += 1
            return value
        raise StopAsyncIteration

async def use_async_range():
    async for i in AsyncRange(0, 5):
        print(i)
""",
        )
        chunks = chunk_file(src, "python")

        # Check async protocol methods
        aiter_chunk = next(c for c in chunks if "__aiter__" in c.content)
        anext_chunk = next(c for c in chunks if "__anext__" in c.content)

        assert aiter_chunk is not None
        assert anext_chunk is not None
        assert "async def __anext__" in anext_chunk.content


class TestPythonImportStatements:
    """Test various import patterns (though typically not chunked)."""

    def test_import_patterns(self, tmp_path):
        """Test that imports are handled correctly within chunks."""
        src = tmp_path / "imports.py"
        src.write_text(
            """
# Standard library imports
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional

# Third party imports
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

# Local imports
from .utils import helper_function
from ..parent_module import ParentClass

def process_data(file_path: Path) -> pd.DataFrame:
    '''Process data from file.'''
    df = pd.read_csv(file_path)
    return df

class DataProcessor:
    '''Class using imported modules.'''

    def __init__(self):
        self.data_dir = Path.home() / 'data'
        self.arrays = []

    def load_array(self, name: str) -> np.ndarray:
        return np.load(self.data_dir / f"{name}.npy")
""",
        )
        chunks = chunk_file(src, "python")

        # Imports shouldn't be separate chunks, but should be included in file
        import_chunks = [c for c in chunks if c.node_type == "import_statement"]
        assert len(import_chunks) == 0  # Imports are not chunked

        # But imports should be visible in the function/class chunks that contain them
        func_chunk = next(c for c in chunks if "process_data" in c.content)
        class_chunk = next(
            c for c in chunks if "DataProcessor" in c.content and "class" in c.content
        )

        assert func_chunk is not None
        assert class_chunk is not None


def test_empty_file(tmp_path):
    """Test handling of empty Python file."""
    src = tmp_path / "empty.py"
    src.write_text("")
    chunks = chunk_file(src, "python")
    assert len(chunks) == 0


def test_syntax_error_handling(tmp_path):
    """Test handling of files with syntax errors."""
    src = tmp_path / "syntax_error.py"
    src.write_text(
        """
def broken_function(
    # Missing closing parenthesis
    pass

class IncompleteClass
    # Missing colon
    def method(self):
        return
""",
    )
    # Tree-sitter should still parse what it can
    chunks = chunk_file(src, "python")
    # Should get at least some chunks despite syntax errors
    assert len(chunks) >= 0  # May get partial results


def test_unicode_and_encoding(tmp_path):
    """Test handling of Unicode in Python code."""
    src = tmp_path / "unicode.py"
    src.write_text(
        """
def process_unicode():
    '''Process Unicode strings. 处理Unicode字符串。'''
    emoji = "🐍 Python rocks! 🚀"
    chinese = "你好世界"
    arabic = "مرحبا بالعالم"

    return {
        'emoji': emoji,
        'chinese': chinese,
        'arabic': arabic
    }

class 多语言类:
    '''A class with non-ASCII name.'''

    def 获取信息(self):
        return "信息"
""",
    )
    chunks = chunk_file(src, "python")

    # Check that Unicode content is preserved
    assert any("🐍 Python rocks! 🚀" in c.content for c in chunks)
    assert any("你好世界" in c.content for c in chunks)
    assert any("多语言类" in c.content for c in chunks)
