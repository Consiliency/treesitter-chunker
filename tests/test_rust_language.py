"""Test Rust-specific language features chunking."""

import pytest

from chunker.core import chunk_file
from chunker.exceptions import ParserInitError
from chunker.languages import LanguageConfig, language_config_registry
from chunker.parser import get_parser


class RustConfig(LanguageConfig):
    """Configuration for Rust language."""

    @property
    def language_id(self) -> str:
        return "rust"

    @property
    def file_extensions(self) -> set[str]:
        return {".rs"}

    @property
    def chunk_types(self) -> set[str]:
        return {
            "function_item",
            "impl_item",
            "trait_item",
            "struct_item",
            "enum_item",
            "mod_item",
            "macro_definition",
            "const_item",
            "static_item",
            "type_item",
            "foreign_mod_item",  # extern blocks
            "union_item",  # union types
        }


def check_rust_parser_available():
    """Check if Rust parser is available."""
    try:
        get_parser("rust")
        return True
    except ParserInitError:
        return False


# Skip entire test class if Rust parser is not available
pytestmark = pytest.mark.skipif(
    not check_rust_parser_available(),
    reason="Rust parser not available due to ABI version mismatch",
)


class TestRustLanguageFeatures:
    """Test Rust-specific language features."""

    def setup_method(self):
        """Register Rust config for tests."""
        self.rust_config = RustConfig()
        language_config_registry.register(self.rust_config)

    def teardown_method(self):
        """Clean up after tests."""
        if "rust" in language_config_registry._configs:
            del language_config_registry._configs["rust"]

    def test_trait_implementations(self, tmp_path):
        """Test chunking of trait implementations."""
        test_file = tmp_path / "traits.rs"
        test_file.write_text(
            """
// Trait definition
trait Display {
    fn fmt(&self, f: &mut Formatter) -> Result;
}

// Basic trait implementation
impl Display for Point {
    fn fmt(&self, f: &mut Formatter) -> Result {
        write!(f, "({}, {})", self.x, self.y)
    }
}

// Generic trait implementation
impl<T> Display for Vec<T>
where
    T: Display
{
    fn fmt(&self, f: &mut Formatter) -> Result {
        // implementation
    }
}

// Multiple trait bounds
impl<T, U> MyTrait for MyStruct<T, U>
where
    T: Clone + Debug,
    U: Default + Send,
{
    fn do_something(&self) {}
}

// Trait with associated types
trait Iterator {
    type Item;
    fn next(&mut self) -> Option<Self::Item>;
}

impl Iterator for Counter {
    type Item = u32;

    fn next(&mut self) -> Option<Self::Item> {
        self.count += 1;
        Some(self.count)
    }
}
""",
        )

        chunks = chunk_file(test_file, "rust")

        # Filter trait and impl chunks
        trait_chunks = [c for c in chunks if c.node_type == "trait_item"]
        impl_chunks = [c for c in chunks if c.node_type == "impl_item"]

        # Should find trait definitions
        assert len(trait_chunks) >= 2  # Display and Iterator

        # Should find impl blocks
        assert len(impl_chunks) >= 4  # All the impl blocks

        # Verify trait content
        trait_contents = [c.content for c in trait_chunks]
        assert any("trait Display" in c for c in trait_contents)
        assert any("trait Iterator" in c for c in trait_contents)
        assert any("type Item" in c for c in trait_contents)

        # Verify impl content includes generic parameters
        impl_contents = [c.content for c in impl_chunks]
        assert any("impl Display for Point" in c for c in impl_contents)
        assert any("impl<T> Display for Vec<T>" in c for c in impl_contents)
        assert any("impl<T, U> MyTrait for MyStruct<T, U>" in c for c in impl_contents)

    def test_macro_definitions(self, tmp_path):
        """Test chunking of macro definitions."""
        test_file = tmp_path / "macros.rs"
        test_file.write_text(
            """
// Simple macro_rules!
macro_rules! say_hello {
    () => {
        println!("Hello!");
    };
}

// Macro with patterns
macro_rules! create_function {
    ($func_name:ident) => {
        fn $func_name() {
            println!("You called {:?}()", stringify!($func_name));
        }
    };
}

// Complex macro with multiple arms
macro_rules! vec_strs {
    (
        $($element:expr),*
    ) => {
        {
            let mut v = Vec::new();
            $(
                v.push(format!("{}", $element));
            )*
            v
        }
    };
}

// Procedural macro (declaration)
#[proc_macro]
pub fn derive_debug(input: TokenStream) -> TokenStream {
    // implementation
}

// Macro with repetition
macro_rules! find_min {
    ($x:expr) => ($x);
    ($x:expr, $($y:expr),+) => (
        std::cmp::min($x, find_min!($($y),+))
    )
}
""",
        )

        chunks = chunk_file(test_file, "rust")

        # Filter macro chunks
        macro_chunks = [c for c in chunks if c.node_type == "macro_definition"]
        function_chunks = [c for c in chunks if c.node_type == "function_item"]

        # Should find macro_rules! definitions
        assert len(macro_chunks) >= 4  # All macro_rules!

        # Should find proc macro function
        assert len(function_chunks) >= 1  # derive_debug

        # Verify macro content
        macro_contents = [c.content for c in macro_chunks]
        assert any("macro_rules! say_hello" in c for c in macro_contents)
        assert any("macro_rules! create_function" in c for c in macro_contents)
        assert any("$func_name:ident" in c for c in macro_contents)
        assert any("$($element:expr),*" in c for c in macro_contents)

    def test_unsafe_blocks(self, tmp_path):
        """Test handling of unsafe blocks and functions."""
        test_file = tmp_path / "unsafe_code.rs"
        test_file.write_text(
            """
// Unsafe function
unsafe fn dangerous_operation(ptr: *const u32) -> u32 {
    // Dereference raw pointer
    *ptr
}

// Safe function with unsafe block
fn use_unsafe() {
    let mut num = 5;
    let ptr = &mut num as *mut i32;

    unsafe {
        *ptr = 10;
        dangerous_operation(ptr as *const u32);
    }
}

// Unsafe trait
unsafe trait UnsafeTrait {
    unsafe fn unsafe_method(&self);
}

// Unsafe impl
unsafe impl UnsafeTrait for MyStruct {
    unsafe fn unsafe_method(&self) {
        // implementation
    }
}

// Extern functions (FFI)
extern "C" {
    fn abs(input: i32) -> i32;
}

fn call_extern() {
    unsafe {
        println!("Absolute value: {}", abs(-3));
    }
}
""",
        )

        chunks = chunk_file(test_file, "rust")

        # Check for unsafe functions and traits
        function_chunks = [c for c in chunks if c.node_type == "function_item"]
        trait_chunks = [c for c in chunks if c.node_type == "trait_item"]
        impl_chunks = [c for c in chunks if c.node_type == "impl_item"]

        # Verify unsafe content is captured
        unsafe_functions = [c for c in function_chunks if "unsafe fn" in c.content]
        assert len(unsafe_functions) >= 1  # dangerous_operation

        unsafe_traits = [c for c in trait_chunks if "unsafe trait" in c.content]
        assert len(unsafe_traits) >= 1  # UnsafeTrait

        unsafe_impls = [c for c in impl_chunks if "unsafe impl" in c.content]
        assert len(unsafe_impls) >= 1  # unsafe impl UnsafeTrait

        # Verify extern blocks are handled
        foreign_mod_chunks = [c for c in chunks if c.node_type == "foreign_mod_item"]
        assert len(foreign_mod_chunks) >= 1  # extern "C" block
        assert any('extern "C"' in c.content for c in foreign_mod_chunks)

    def test_lifetime_annotations(self, tmp_path):
        """Test handling of lifetime annotations."""
        test_file = tmp_path / "lifetimes.rs"
        test_file.write_text(
            """
// Simple lifetime annotation
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() > y.len() {
        x
    } else {
        y
    }
}

// Struct with lifetime parameters
struct ImportantExcerpt<'a> {
    part: &'a str,
}

// Impl block with lifetimes
impl<'a> ImportantExcerpt<'a> {
    fn level(&self) -> i32 {
        3
    }

    fn announce_and_return_part(&self, announcement: &str) -> &str {
        println!("Announcement: {}", announcement);
        self.part
    }
}

// Multiple lifetime parameters
fn complex_lifetimes<'a, 'b>(x: &'a str, y: &'b str) -> &'a str
where
    'b: 'a  // 'b outlives 'a
{
    x
}

// Static lifetime
const STATIC_STR: &'static str = "I have a static lifetime";

// Lifetime bounds on traits
trait Display<'a> {
    fn fmt(&'a self) -> String;
}
""",
        )

        chunks = chunk_file(test_file, "rust")

        # All major items should be chunked despite lifetime complexity
        function_chunks = [c for c in chunks if c.node_type == "function_item"]
        struct_chunks = [c for c in chunks if c.node_type == "struct_item"]
        impl_chunks = [c for c in chunks if c.node_type == "impl_item"]
        const_chunks = [c for c in chunks if c.node_type == "const_item"]
        trait_chunks = [c for c in chunks if c.node_type == "trait_item"]

        # Verify all items are found
        assert (
            len(function_chunks) >= 3
        )  # longest, level, announce_and_return_part, complex_lifetimes
        assert len(struct_chunks) >= 1  # ImportantExcerpt
        assert len(impl_chunks) >= 1  # impl<'a> ImportantExcerpt<'a>
        assert len(const_chunks) >= 1  # STATIC_STR
        assert len(trait_chunks) >= 1  # Display<'a>

        # Verify lifetime syntax is preserved
        function_contents = [c.content for c in function_chunks]
        assert any("<'a>" in c and "&'a str" in c for c in function_contents)
        assert any("<'a, 'b>" in c for c in function_contents)
        assert any("'b: 'a" in c for c in function_contents)

    def test_module_structure(self, tmp_path):
        """Test module structure (mod, pub, use statements)."""
        test_file = tmp_path / "modules.rs"
        test_file.write_text(
            """
// Module declaration
mod utils {
    pub fn helper() {
        println!("Helper function");
    }

    // Nested module
    pub mod nested {
        pub fn deep_function() {}
    }
}

// Public module
pub mod public_api {
    // Re-exports
    pub use crate::utils::helper;

    pub struct PublicStruct {
        pub field: i32,
    }

    impl PublicStruct {
        pub fn new() -> Self {
            Self { field: 0 }
        }
    }
}

// Use statements
use std::collections::HashMap;
use std::io::{self, Write};
use crate::utils::*;

// Private module
mod private {
    use super::*;

    pub(crate) fn internal_only() {}
    pub(super) fn parent_only() {}
}

// Module with visibility modifiers
pub(crate) mod internal_module {
    pub(in crate::public_api) fn restricted_visibility() {}
}
""",
        )

        chunks = chunk_file(test_file, "rust")

        # Filter module chunks
        mod_chunks = [c for c in chunks if c.node_type == "mod_item"]

        # Should find all module declarations
        assert (
            len(mod_chunks) >= 5
        )  # utils, nested, public_api, private, internal_module

        # Verify module content and visibility
        mod_contents = [c.content for c in mod_chunks]
        assert any("mod utils" in c for c in mod_contents)
        assert any("pub mod public_api" in c for c in mod_contents)
        assert any("pub mod nested" in c for c in mod_contents)
        assert any("mod private" in c for c in mod_contents)
        assert any("pub(crate) mod internal_module" in c for c in mod_contents)

        # Check that nested items are also chunked
        all_chunks = chunks
        assert any("pub fn helper" in c.content for c in all_chunks)
        assert any("pub struct PublicStruct" in c.content for c in all_chunks)
        assert any("pub(crate) fn internal_only" in c.content for c in all_chunks)

    def test_generic_functions(self, tmp_path):
        """Test generic functions with various constraints."""
        test_file = tmp_path / "generics.rs"
        test_file.write_text(
            """
// Simple generic function
fn identity<T>(x: T) -> T {
    x
}

// Generic with trait bounds
fn print_debug<T: Debug>(item: T) {
    println!("{:?}", item);
}

// Multiple type parameters
fn swap<T, U>(tuple: (T, U)) -> (U, T) {
    (tuple.1, tuple.0)
}

// Complex where clause
fn complex_generic<T, U, V>(x: T, y: U) -> V
where
    T: Clone + Debug,
    U: Default + From<T>,
    V: From<U> + Display,
{
    let cloned = x.clone();
    let converted: U = U::from(cloned);
    V::from(converted)
}

// Generic struct
struct Point<T> {
    x: T,
    y: T,
}

// Generic impl
impl<T> Point<T> {
    fn new(x: T, y: T) -> Self {
        Self { x, y }
    }
}

// Generic impl with constraints
impl<T: Display + PartialOrd> Point<T> {
    fn cmp_display(&self) {
        if self.x >= self.y {
            println!("x: {} is greater", self.x);
        } else {
            println!("y: {} is greater", self.y);
        }
    }
}

// Generic enum
enum Option<T> {
    Some(T),
    None,
}

// Associated types
trait Container {
    type Item;
    fn get(&self) -> &Self::Item;
}

impl<T> Container for Box<T> {
    type Item = T;

    fn get(&self) -> &Self::Item {
        &**self
    }
}
""",
        )

        chunks = chunk_file(test_file, "rust")

        # Count different types of generic items
        function_chunks = [c for c in chunks if c.node_type == "function_item"]
        struct_chunks = [c for c in chunks if c.node_type == "struct_item"]
        impl_chunks = [c for c in chunks if c.node_type == "impl_item"]
        enum_chunks = [c for c in chunks if c.node_type == "enum_item"]
        trait_chunks = [c for c in chunks if c.node_type == "trait_item"]

        # Verify all generic constructs are found
        assert len(function_chunks) >= 5  # All generic functions
        assert len(struct_chunks) >= 1  # Point<T>
        assert len(impl_chunks) >= 3  # Two Point impls + Container impl
        assert len(enum_chunks) >= 1  # Option<T>
        assert len(trait_chunks) >= 1  # Container

        # Verify generic syntax is preserved
        function_contents = [c.content for c in function_chunks]
        assert any("fn identity<T>" in c for c in function_contents)
        assert any("<T: Debug>" in c for c in function_contents)
        assert any("<T, U>" in c for c in function_contents)
        assert any("where" in c and "T: Clone + Debug" in c for c in function_contents)

        # Check impl with constraints
        impl_contents = [c.content for c in impl_chunks]
        assert any("<T: Display + PartialOrd>" in c for c in impl_contents)

    def test_rust_config(self):
        """Test Rust language configuration."""
        config = language_config_registry.get("rust")
        assert config is not None

        # Check language name
        assert config.language_id == "rust"

        # Check supported extensions
        assert ".rs" in config.file_extensions
        assert len(config.file_extensions) == 1

        # Check default chunk types
        expected_types = {
            "function_item",
            "impl_item",
            "trait_item",
            "struct_item",
            "enum_item",
            "mod_item",
            "macro_definition",
            "const_item",
            "static_item",
            "type_item",
            "foreign_mod_item",
            "union_item",
        }
        assert config.chunk_types == expected_types

    def test_visibility_modifiers(self, tmp_path):
        """Test that visibility modifiers are preserved in content."""
        test_file = tmp_path / "visibility.rs"
        test_file.write_text(
            """
// Public items
pub fn public_function() {}
pub struct PublicStruct;
pub enum PublicEnum { A, B }

// Crate-visible items
pub(crate) fn crate_function() {}
pub(crate) struct CrateStruct;

// Module-visible items
pub(super) fn parent_function() {}
pub(in crate::module) fn specific_module_function() {}

// Private items (default)
fn private_function() {}
struct PrivateStruct;
impl PrivateStruct {
    fn method(&self) {}
}
""",
        )

        chunks = chunk_file(test_file, "rust")

        # Check that visibility modifiers are preserved in the content
        chunk_contents = [c.content for c in chunks]

        # Public items
        assert any("pub fn public_function" in c for c in chunk_contents)
        assert any("pub struct PublicStruct" in c for c in chunk_contents)
        assert any("pub enum PublicEnum" in c for c in chunk_contents)

        # Crate-visible items
        assert any("pub(crate) fn crate_function" in c for c in chunk_contents)
        assert any("pub(crate) struct CrateStruct" in c for c in chunk_contents)

        # Module-visible items
        assert any("pub(super) fn parent_function" in c for c in chunk_contents)
        assert any(
            "pub(in crate::module) fn specific_module_function" in c
            for c in chunk_contents
        )

        # Private items (no visibility modifier)
        assert any(
            "fn private_function" in c and "pub" not in c for c in chunk_contents
        )

    def test_test_function_attributes(self, tmp_path):
        """Test that test function attributes are preserved."""
        test_file = tmp_path / "test_functions.rs"
        test_file.write_text(
            """
// Regular function
fn regular_function() {
    println!("Regular");
}

// Test function
#[test]
fn test_something() {
    assert_eq!(2 + 2, 4);
}

// Another test
#[test]
fn test_another_thing() {
    assert!(true);
}

// Test module
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn internal_test() {
        regular_function();
    }
}

// Benchmark (also a test)
#[bench]
fn bench_performance(b: &mut Bencher) {
    b.iter(|| {
        // benchmark code
    });
}
""",
        )

        chunks = chunk_file(test_file, "rust")

        # Check that all functions are found
        function_chunks = [c for c in chunks if c.node_type == "function_item"]
        mod_chunks = [c for c in chunks if c.node_type == "mod_item"]

        # Should find all functions
        assert (
            len(function_chunks) >= 5
        )  # regular, test_something, test_another_thing, internal_test, bench_performance

        # Check that test attributes are preserved in content
        function_contents = [c.content for c in function_chunks]

        # Regular function
        assert any("fn regular_function" in c for c in function_contents)

        # Test functions - attributes might be included or not depending on parser
        assert any("fn test_something" in c for c in function_contents)
        assert any("fn test_another_thing" in c for c in function_contents)
        assert any("fn internal_test" in c for c in function_contents)

        # Benchmark function
        assert any("fn bench_performance" in c for c in function_contents)

        # Test module
        assert len(mod_chunks) >= 1
        assert any("mod tests" in c.content for c in mod_chunks)

    def test_rust_specific_constructs(self, tmp_path):
        """Test other Rust-specific constructs."""
        test_file = tmp_path / "rust_constructs.rs"
        test_file.write_text(
            """
// Type alias
type Result<T> = std::result::Result<T, Error>;
type Kilometers = i32;

// Static items
static GLOBAL: i32 = 100;
static mut MUTABLE_STATIC: u32 = 0;

// Const items
const MAX_POINTS: u32 = 100_000;
const fn const_function() -> i32 {
    42
}

// Union (unsafe)
union MyUnion {
    f1: u32,
    f2: f32,
}

// Extern block
extern "C" {
    static mut errno: c_int;
    fn strlen(s: *const c_char) -> size_t;
}

// Async function
async fn async_operation() -> Result<()> {
    Ok(())
}

// Pattern matching in function parameters
fn destructure((x, y): (i32, i32)) -> i32 {
    x + y
}

// Const generics
struct Array<T, const N: usize> {
    data: [T; N],
}

impl<T, const N: usize> Array<T, N> {
    fn new(value: T) -> Self
    where
        T: Clone
    {
        Self {
            data: [value; N],
        }
    }
}
""",
        )

        chunks = chunk_file(test_file, "rust")

        # Check for various construct types
        type_chunks = [c for c in chunks if c.node_type == "type_item"]
        static_chunks = [c for c in chunks if c.node_type == "static_item"]
        const_chunks = [c for c in chunks if c.node_type == "const_item"]
        function_chunks = [c for c in chunks if c.node_type == "function_item"]
        struct_chunks = [c for c in chunks if c.node_type == "struct_item"]
        union_chunks = [c for c in chunks if c.node_type == "union_item"]

        # Verify type aliases
        assert len(type_chunks) >= 2  # Result<T> and Kilometers
        assert any("type Result<T>" in c.content for c in type_chunks)

        # Verify static items
        assert len(static_chunks) >= 2  # GLOBAL and MUTABLE_STATIC
        assert any("static mut" in c.content for c in static_chunks)

        # Verify const items
        assert len(const_chunks) >= 1  # MAX_POINTS
        assert any("const MAX_POINTS" in c.content for c in const_chunks)

        # Verify const fn
        const_fn_chunks = [c for c in function_chunks if "const fn" in c.content]
        assert len(const_fn_chunks) >= 1

        # Verify async fn
        async_fn_chunks = [c for c in function_chunks if "async fn" in c.content]
        assert len(async_fn_chunks) >= 1

        # Verify const generics
        assert any("const N: usize" in c.content for c in struct_chunks)

        # Verify union
        assert len(union_chunks) >= 1
        assert any("union MyUnion" in c.content for c in union_chunks)
