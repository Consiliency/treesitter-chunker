"""Test C++-specific language features for the chunker.

Note: The C++ language plugin (CppPlugin) exists and supports many C++ constructs
including classes, namespaces, templates, constructors/destructors, etc. However,
without a proper LanguageConfig registration (like Python has), the chunker falls
back to default chunk types which only includes function_definition, class_definition,
and method_definition.

As a result, these tests verify that C++ code can be parsed and that functions/methods
are properly detected, but more advanced chunking (classes, namespaces, templates as
separate chunks) requires proper configuration setup.
"""

import importlib

import pytest

import chunker.languages.cpp
from chunker import chunk_file, get_parser
from chunker.exceptions import LanguageNotFoundError, ParserInitError
from chunker.languages import language_config_registry


class TestCppLanguageFeatures:
    """Test C++-specific language features."""

    def setup_method(self):
        """Setup for each test."""
        # Clear and ensure C++ config is loaded
        language_config_registry.clear()

        # Force re-import of cpp config


        importlib.reload(chunker.languages.cpp)

    def test_cpp_parser_available(self):
        """Test that C++ parser is available."""
        try:
            parser = get_parser("cpp")
            assert parser is not None
        except (LanguageNotFoundError, ParserInitError):
            pytest.skip("C++ parser not available")

    def test_template_function(self, tmp_path):
        """Test template function chunking."""
        test_file = tmp_path / "template.cpp"
        test_file.write_text(
            """
template<typename T>
T max(T a, T b) {
    return (a > b) ? a : b;
}

template<typename T, typename U>
auto add(T a, U b) -> decltype(a + b) {
    return a + b;
}
""",
        )

        chunks = chunk_file(test_file, "cpp")
        assert len(chunks) == 2

        # Check template functions are detected
        # Note: Templates are detected as regular function_definition
        # but the content includes the template declaration
        for chunk in chunks:
            assert chunk.node_type == "function_definition"
            # The actual template syntax might not be in the chunk content
            # since it's processed at the function level

        # Check specific function names
        assert any("max" in chunk.content for chunk in chunks)
        assert any("add" in chunk.content for chunk in chunks)

    def test_template_class(self, tmp_path):
        """Test template class chunking."""
        test_file = tmp_path / "template_class.cpp"
        test_file.write_text(
            """
template<typename T>
class Vector {
public:
    Vector() : size_(0), capacity_(0), data_(nullptr) {}

    void push_back(const T& value) {
        // Implementation
    }

    T& operator[](size_t index) {
        return data_[index];
    }

private:
    size_t size_;
    size_t capacity_;
    T* data_;
};

// Template specialization
template<>
class Vector<bool> {
public:
    Vector() : size_(0) {}

    void push_back(bool value) {
        // Bit-packed implementation
    }

private:
    size_t size_;
    std::vector<uint8_t> data_;
};
""",
        )

        chunks = chunk_file(test_file, "cpp")

        # With the current implementation, only functions are detected by default
        # Classes themselves are not chunked without proper language config
        assert len(chunks) >= 4  # Constructor and methods from both classes

        # Check that we find the methods
        method_names = [
            c.content.split("(")[0].split()[-1] for c in chunks if "(" in c.content
        ]
        assert "Vector" in method_names  # Constructors
        assert "push_back" in method_names
        assert "operator[]" in method_names or "operator" in " ".join(method_names)

    def test_namespace_handling(self, tmp_path):
        """Test namespace definitions and nested namespaces."""
        test_file = tmp_path / "namespace.cpp"
        test_file.write_text(
            """
namespace MyLib {
    void globalFunction() {
        // Global function in namespace
    }

    class Logger {
    public:
        void log(const std::string& msg) {
            // Implementation
        }
    };

    namespace Utils {
        template<typename T>
        void swap(T& a, T& b) {
            T temp = a;
            a = b;
            b = temp;
        }

        class Helper {
        public:
            static void help() {
                // Implementation
            }
        };
    }
}

namespace MyLib::Network {  // C++17 nested namespace
    class Socket {
    public:
        void connect(const std::string& host, int port) {
            // Implementation
        }
        void disconnect() {
            // Implementation
        }
    };
}
""",
        )

        chunks = chunk_file(test_file, "cpp")

        # With default config, only functions are chunked
        function_chunks = [c for c in chunks if c.node_type == "function_definition"]
        assert (
            len(function_chunks) >= 5
        )  # globalFunction, log, swap, help, connect, disconnect

        # Check that we find functions from different contexts
        assert any("swap" in c.content for c in chunks)
        assert any("log" in c.content for c in chunks)
        assert any("connect" in c.content for c in chunks)

    def test_virtual_functions_and_inheritance(self, tmp_path):
        """Test virtual functions and class inheritance."""
        test_file = tmp_path / "virtual.cpp"
        test_file.write_text(
            """
class Shape {
public:
    virtual ~Shape() = default;

    virtual double area() const = 0;
    virtual double perimeter() const = 0;

    virtual void draw() {
        // Default implementation
    }
};

class Circle : public Shape {
public:
    Circle(double radius) : radius_(radius) {}

    double area() const override {
        return 3.14159 * radius_ * radius_;
    }

    double perimeter() const override {
        return 2 * 3.14159 * radius_;
    }

    void draw() override {
        // Circle-specific drawing
    }

private:
    double radius_;
};

class Rectangle final : public Shape {
public:
    Rectangle(double width, double height)
        : width_(width), height_(height) {}

    double area() const override {
        return width_ * height_;
    }

    double perimeter() const override {
        return 2 * (width_ + height_);
    }

private:
    double width_;
    double height_;
};
""",
        )

        chunks = chunk_file(test_file, "cpp")

        # With default config, functions are detected
        function_chunks = [c for c in chunks if c.node_type == "function_definition"]
        assert len(function_chunks) >= 8  # Multiple methods from all classes

        # Check virtual functions and overrides are found
        virtual_methods = [
            c for c in chunks if "virtual" in c.content or "override" in c.content
        ]
        assert len(virtual_methods) >= 6  # Multiple virtual/override methods

        # Note: Destructors may not be separately chunked with default config
        # Check that we at least find the area/perimeter methods
        assert any("area" in c.content for c in chunks)
        assert any("perimeter" in c.content for c in chunks)

    def test_operator_overloading(self, tmp_path):
        """Test operator overloading detection."""
        test_file = tmp_path / "operators.cpp"
        test_file.write_text(
            """
class Complex {
public:
    Complex(double real = 0, double imag = 0)
        : real_(real), imag_(imag) {}

    // Arithmetic operators
    Complex operator+(const Complex& other) const {
        return Complex(real_ + other.real_, imag_ + other.imag_);
    }

    Complex operator-(const Complex& other) const {
        return Complex(real_ - other.real_, imag_ - other.imag_);
    }

    Complex& operator+=(const Complex& other) {
        real_ += other.real_;
        imag_ += other.imag_;
        return *this;
    }

    // Comparison operators
    bool operator==(const Complex& other) const {
        return real_ == other.real_ && imag_ == other.imag_;
    }

    bool operator!=(const Complex& other) const {
        return !(*this == other);
    }

    // Stream operators (friend functions)
    friend std::ostream& operator<<(std::ostream& os, const Complex& c) {
        os << c.real_ << " + " << c.imag_ << "i";
        return os;
    }

    // Conversion operator
    operator double() const {
        return std::sqrt(real_ * real_ + imag_ * imag_);
    }

    // Function call operator
    double operator()() const {
        return real_ * real_ + imag_ * imag_;
    }

    // Subscript operator
    double& operator[](int index) {
        return (index == 0) ? real_ : imag_;
    }

private:
    double real_;
    double imag_;
};

// Global operator
Complex operator*(double scalar, const Complex& c) {
    return Complex(scalar * c.real_, scalar * c.imag_);
}
""",
        )

        chunks = chunk_file(test_file, "cpp")

        # Check operator methods are found
        operator_chunks = [c for c in chunks if "operator" in c.content]
        assert len(operator_chunks) >= 10  # Many operators defined

        # Check specific operators
        assert any("operator+" in c.content for c in operator_chunks)
        assert any("operator==" in c.content for c in operator_chunks)
        assert any("operator<<" in c.content for c in operator_chunks)
        assert any("operator()" in c.content for c in operator_chunks)
        assert any("operator[]" in c.content for c in operator_chunks)

    def test_stl_usage_patterns(self, tmp_path):
        """Test STL container and algorithm usage."""
        test_file = tmp_path / "stl_usage.cpp"
        test_file.write_text(
            """
#include <vector>
#include <map>
#include <algorithm>
#include <memory>
#include <functional>

class DataProcessor {
public:
    using DataMap = std::map<std::string, std::vector<int>>;
    using ProcessFunc = std::function<void(int&)>;

    void addData(const std::string& key, std::initializer_list<int> values) {
        data_[key] = std::vector<int>(values);
    }

    void processAll(ProcessFunc func) {
        for (auto& [key, values] : data_) {
            std::for_each(values.begin(), values.end(), func);
        }
    }

    std::vector<int> getSorted(const std::string& key) {
        auto it = data_.find(key);
        if (it != data_.end()) {
            std::vector<int> sorted = it->second;
            std::sort(sorted.begin(), sorted.end());
            return sorted;
        }
        return {};
    }

    template<typename Predicate>
    std::vector<int> filter(const std::string& key, Predicate pred) {
        std::vector<int> result;
        auto it = data_.find(key);
        if (it != data_.end()) {
            std::copy_if(it->second.begin(), it->second.end(),
                        std::back_inserter(result), pred);
        }
        return result;
    }

private:
    DataMap data_;
    std::unique_ptr<ProcessFunc> custom_processor_;
};

// Function using modern C++ features
auto makeProcessor() -> std::unique_ptr<DataProcessor> {
    return std::make_unique<DataProcessor>();
}

// Lambda and STL algorithms
void demonstrateSTL() {
    std::vector<int> nums = {1, 2, 3, 4, 5};

    // Lambda with capture
    int sum = 0;
    std::for_each(nums.begin(), nums.end(), [&sum](int n) {
        sum += n;
    });

    // Transform with lambda
    std::vector<int> squares;
    std::transform(nums.begin(), nums.end(), std::back_inserter(squares),
                  [](int n) { return n * n; });
}
""",
        )

        chunks = chunk_file(test_file, "cpp")

        # With default config, only functions are detected
        function_chunks = [c for c in chunks if c.node_type == "function_definition"]
        assert (
            len(function_chunks) >= 6
        )  # addData, processAll, getSorted, filter, makeProcessor, demonstrateSTL

        # Check template methods
        template_methods = [c for c in chunks if "filter" in c.content]
        assert len(template_methods) >= 1

        # Check functions with modern syntax
        auto_functions = [c for c in chunks if "makeProcessor" in c.content]
        assert len(auto_functions) >= 1  # makeProcessor

        # Check STL usage functions
        stl_demo = [c for c in chunks if "demonstrateSTL" in c.content]
        assert len(stl_demo) >= 1

    def test_constructor_destructor(self, tmp_path):
        """Test constructor and destructor detection."""
        test_file = tmp_path / "ctor_dtor.cpp"
        test_file.write_text(
            """
class Resource {
public:
    // Default constructor
    Resource() : data_(nullptr), size_(0) {
        std::cout << "Default constructor\\n";
    }

    // Parameterized constructor
    Resource(size_t size) : size_(size) {
        data_ = new int[size];
        std::cout << "Parameterized constructor\\n";
    }

    // Copy constructor
    Resource(const Resource& other) : size_(other.size_) {
        data_ = new int[size_];
        std::copy(other.data_, other.data_ + size_, data_);
        std::cout << "Copy constructor\\n";
    }

    // Move constructor
    Resource(Resource&& other) noexcept
        : data_(other.data_), size_(other.size_) {
        other.data_ = nullptr;
        other.size_ = 0;
        std::cout << "Move constructor\\n";
    }

    // Destructor
    ~Resource() {
        delete[] data_;
        std::cout << "Destructor\\n";
    }

    // Copy assignment
    Resource& operator=(const Resource& other) {
        if (this != &other) {
            delete[] data_;
            size_ = other.size_;
            data_ = new int[size_];
            std::copy(other.data_, other.data_ + size_, data_);
        }
        return *this;
    }

    // Move assignment
    Resource& operator=(Resource&& other) noexcept {
        if (this != &other) {
            delete[] data_;
            data_ = other.data_;
            size_ = other.size_;
            other.data_ = nullptr;
            other.size_ = 0;
        }
        return *this;
    }

private:
    int* data_;
    size_t size_;
};
""",
        )

        chunks = chunk_file(test_file, "cpp")

        # With default config, all functions including constructors/destructors are function_definition
        all_functions = [c for c in chunks if c.node_type == "function_definition"]
        assert len(all_functions) >= 7  # Multiple constructors, destructor, assignments

        # Check specific functions by content
        constructor_like = [c for c in chunks if "Resource(" in c.content]
        assert len(constructor_like) >= 3  # Some constructors

        # Check destructor exists
        destructor_like = [c for c in chunks if "~Resource" in c.content]
        assert len(destructor_like) >= 1

        # Check assignment operators
        assignment_chunks = [c for c in chunks if "operator=" in c.content]
        assert len(assignment_chunks) == 2  # Copy and move assignment

    def test_cpp_specific_features(self, tmp_path):
        """Test various C++-specific features."""
        test_file = tmp_path / "cpp_features.cpp"
        test_file.write_text(
            """
// Inline namespace
inline namespace v1 {
    class Version1 {
    public:
        void feature() { /* v1 implementation */ }
    };
}

// Constexpr function
constexpr int factorial(int n) {
    return (n <= 1) ? 1 : n * factorial(n - 1);
}

// Variadic template
template<typename... Args>
void print(Args... args) {
    ((std::cout << args << " "), ...);
}

// Enum class
enum class Color : uint8_t {
    Red = 0,
    Green = 1,
    Blue = 2
};

// Structured binding example
struct Point {
    double x, y, z;
};

Point getPoint() {
    return {1.0, 2.0, 3.0};
}

// Using declaration
using ColorType = std::underlying_type_t<Color>;

// Concept (C++20)
template<typename T>
concept Arithmetic = std::is_arithmetic_v<T>;

template<Arithmetic T>
T add(T a, T b) {
    return a + b;
}

// Class with deleted functions
class NonCopyable {
public:
    NonCopyable() = default;
    NonCopyable(const NonCopyable&) = delete;
    NonCopyable& operator=(const NonCopyable&) = delete;
    NonCopyable(NonCopyable&&) = default;
    NonCopyable& operator=(NonCopyable&&) = default;
};
""",
        )

        chunks = chunk_file(test_file, "cpp")

        # Check various functions are detected
        assert len(chunks) >= 4  # factorial, print, getPoint, add

        # Check for constexpr function
        constexpr_chunks = [
            c for c in chunks if "constexpr" in c.content and "factorial" in c.content
        ]
        assert len(constexpr_chunks) >= 1

        # Check for variadic template function
        variadic_chunks = [
            c for c in chunks if "print" in c.content and "..." in c.content
        ]
        assert len(variadic_chunks) >= 1

        # Check for template with concept
        concept_chunks = [
            c
            for c in chunks
            if "add" in c.content and c.node_type == "function_definition"
        ]
        assert len(concept_chunks) >= 1

        # Check getPoint function
        assert any("getPoint" in c.content for c in chunks)

    def test_nested_classes_and_structs(self, tmp_path):
        """Test nested classes and structs."""
        test_file = tmp_path / "nested.cpp"
        test_file.write_text(
            """
class OuterClass {
public:
    class InnerClass {
    public:
        void innerMethod() {
            // Inner class method
        }

        struct InnerStruct {
            int value;
            void structMethod() {
                // Struct method
            }
        };
    };

    struct OuterStruct {
        void outerStructMethod() {
            // Outer struct method
        }
    };

private:
    class PrivateNested {
        void privateMethod() {
            // Private nested class
        }
    };
};

// Test struct with nested types
struct Container {
    struct Node {
        int data;
        Node* next;

        Node(int val) : data(val), next(nullptr) {}
    };

    class Iterator {
    public:
        Iterator(Node* node) : current_(node) {}

        Iterator& operator++() {
            current_ = current_->next;
            return *this;
        }

    private:
        Node* current_;
    };
};
""",
        )

        chunks = chunk_file(test_file, "cpp")

        # With default config, methods/functions are detected
        function_chunks = [c for c in chunks if c.node_type == "function_definition"]
        assert len(function_chunks) >= 5  # Various methods from nested classes/structs

        # Check nested methods are found
        inner_method_chunks = [c for c in chunks if "innerMethod" in c.content]
        assert len(inner_method_chunks) >= 1

        # Check other nested functions
        assert any("structMethod" in c.content for c in chunks)
        assert any("operator++" in c.content for c in chunks)

        # Note: With default config, parent context may not reflect the full nesting structure
