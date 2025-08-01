"""Test C-specific language features and chunking."""
import pytest

from chunker.core import chunk_file
from chunker.exceptions import ParserInitError
from chunker.languages.c import CPlugin
from chunker.parser import get_parser


def check_c_parser_available():
    """Check if C parser is available."""
    try:
        get_parser("c")
        return True
    except ParserInitError:
        return False


pytestmark = pytest.mark.skipif(not check_c_parser_available(), reason="C parser not available due to ABI version mismatch")


class TestCLanguageFeatures:
    """Test C language specific features."""

    @classmethod
    def test_c_plugin_properties(cls):
        """Test that C plugin has correct properties."""
        plugin = CPlugin()
        assert plugin.language_name == "c"
        assert plugin.supported_extensions == {".c", ".h"}
        assert plugin.default_chunk_types == {"function_definition",
            "struct_specifier", "union_specifier", "enum_specifier",
            "type_definition"}

    @staticmethod
    def test_basic_function_chunking(tmp_path):
        """Test chunking of basic C functions."""
        test_file = tmp_path / "functions.c"
        test_file.write_text(
            """
int add(int a, int b) {
    return a + b;
}

void print_hello() {
    printf("Hello, World!\\n");
}

static inline int square(int x) {
    return x * x;
}
""",
            )
        chunks = chunk_file(test_file, "c")
        assert len(chunks) == 3
        assert all(chunk.node_type == "function_definition" for chunk in chunks
            )
        contents = [chunk.content for chunk in chunks]
        assert any("add(int a, int b)" in content for content in contents)
        assert any("print_hello()" in content for content in contents)
        assert any("square(int x)" in content for content in contents)

    @staticmethod
    def test_struct_and_union_chunking(tmp_path):
        """Test chunking of struct and union definitions."""
        test_file = tmp_path / "structs.c"
        test_file.write_text(
            """
struct Point {
    int x;
    int y;
};

typedef struct {
    char name[50];
    int age;
} Person;

union Data {
    int i;
    float f;
    char str[20];
};

struct Node {
    int value;
    struct Node* next;
};
""",
            )
        chunks = chunk_file(test_file, "c")
        assert len(chunks) >= 3
        chunk_types = {chunk.node_type for chunk in chunks}
        assert "struct_specifier" in chunk_types
        assert "union_specifier" in chunk_types
        contents = [chunk.content for chunk in chunks]
        assert any("struct Point" in content for content in contents)
        assert any("union Data" in content for content in contents)
        assert any("struct Node" in content for content in contents)

    @staticmethod
    def test_enum_chunking(tmp_path):
        """Test chunking of enum definitions."""
        test_file = tmp_path / "enums.c"
        test_file.write_text(
            """
enum Color {
    RED,
    GREEN,
    BLUE
};

typedef enum {
    MONDAY = 1,
    TUESDAY,
    WEDNESDAY,
    THURSDAY,
    FRIDAY,
    SATURDAY,
    SUNDAY
} Weekday;

enum ErrorCode {
    ERROR_NONE = 0,
    ERROR_FILE_NOT_FOUND = -1,
    ERROR_ACCESS_DENIED = -2
};
""",
            )
        chunks = chunk_file(test_file, "c")
        enum_chunks = [c for c in chunks if c.node_type == "enum_specifier"]
        assert len(enum_chunks) >= 2
        enum_contents = [chunk.content for chunk in enum_chunks]
        assert any("enum Color" in content for content in enum_contents)
        assert any("enum ErrorCode" in content for content in enum_contents)

    @staticmethod
    def test_typedef_chunking(tmp_path):
        """Test chunking of typedef definitions."""
        test_file = tmp_path / "typedefs.c"
        test_file.write_text(
            """
typedef int Integer;

typedef struct Point {
    double x;
    double y;
} Point;

typedef void (*callback_func)(int, const char*);

typedef enum {
    SUCCESS = 0,
    FAILURE = 1
} Status;
""",
            )
        chunks = chunk_file(test_file, "c")
        typedef_chunks = [c for c in chunks if c.node_type == "type_definition"
            ]
        assert len(typedef_chunks) >= 1
        all_types = {chunk.node_type for chunk in chunks}
        assert "struct_specifier" in all_types or "type_definition" in all_types

    @staticmethod
    def test_function_pointers(tmp_path):
        """Test handling of function pointers."""
        test_file = tmp_path / "func_ptrs.c"
        test_file.write_text(
            """
// Function pointer typedef
typedef int (*operation)(int, int);

// Function that takes a function pointer
int apply_operation(int a, int b, operation op) {
    return op(a, b);
}

// Function returning a function pointer
operation get_operation(char op) {
    switch (op) {
        case '+': return add;
        case '-': return subtract;
        default: return NULL;
    }
}

// Array of function pointers
void (*handlers[10])(int);
""",
            )
        chunks = chunk_file(test_file, "c")
        func_chunks = [c for c in chunks if c.node_type ==
            "function_definition"]
        assert len(func_chunks) >= 2
        func_contents = [chunk.content for chunk in func_chunks]
        assert any("apply_operation(int a, int b, operation op)" in content for
            content in func_contents)
        assert any("get_operation(char op)" in content for content in
            func_contents)

    @staticmethod
    def test_preprocessor_directives(tmp_path):
        """Test handling of preprocessor directives."""
        test_file = tmp_path / "preprocessor.c"
        test_file.write_text(
            """
#define MAX_SIZE 100
#define MIN(a, b) ((a) < (b) ? (a) : (b))

#ifdef DEBUG
    #define LOG(msg) printf("DEBUG: %s\\n", msg)
#else
    #define LOG(msg) // No-op
#endif

#include <stdio.h>
#include "myheader.h"

#ifndef MYHEADER_H
#define MYHEADER_H

struct Config {
    int debug_level;
    char log_file[256];
};

#endif // MYHEADER_H

int process_data(int* data, int size) {
    #ifdef BOUNDS_CHECK
    if (size > MAX_SIZE) {
        return -1;
    }
    #endif

    for (int i = 0; i < size; i++) {
        data[i] = data[i] * 2;
    }
    return 0;
}
""",
            )
        chunks = chunk_file(test_file, "c")
        func_chunks = [c for c in chunks if c.node_type ==
            "function_definition"]
        assert len(func_chunks) >= 1
        assert any("process_data(int* data, int size)" in chunk.content for
            chunk in func_chunks)
        struct_chunks = [c for c in chunks if c.node_type == "struct_specifier"
            ]
        assert len(struct_chunks) >= 1
        assert any("struct Config" in chunk.content for chunk in struct_chunks)

    @staticmethod
    def test_nested_structures(tmp_path):
        """Test handling of nested structures."""
        test_file = tmp_path / "nested.c"
        test_file.write_text(
            """
struct Company {
    char name[100];
    struct {
        char street[100];
        char city[50];
        int zipcode;
    } address;

    struct Employee {
        char name[50];
        int id;
        struct {
            int day;
            int month;
            int year;
        } hire_date;
    } employees[100];
};

union Variant {
    int i;
    float f;
    struct {
        char* data;
        size_t len;
    } string;
};
""",
            )
        chunks = chunk_file(test_file, "c")
        contents = [chunk.content for chunk in chunks]
        assert any("struct Company" in content for content in contents)
        assert any("union Variant" in content for content in contents)
        chunk_types = {chunk.node_type for chunk in chunks}
        assert "struct_specifier" in chunk_types
        assert "union_specifier" in chunk_types

    @staticmethod
    def test_complex_declarations(tmp_path):
        """Test handling of complex C declarations."""
        test_file = tmp_path / "complex.c"
        test_file.write_text(
            """
// Array of pointers to functions
int (*func_array[10])(int, int);

// Pointer to array of ints
int (*ptr_to_array)[10];

// Function returning pointer to array
int (*get_array())[10] {
    static int arr[10];
    return &arr;
}

// Const pointer to const data
const char* const error_messages[] = {
    "Success",
    "File not found",
    "Permission denied"
};

// Complex struct with bit fields
struct Flags {
    unsigned int is_active : 1;
    unsigned int is_visible : 1;
    unsigned int priority : 4;
    unsigned int reserved : 26;
};
""",
            )
        chunks = chunk_file(test_file, "c")
        func_chunks = [c for c in chunks if c.node_type ==
            "function_definition"]
        assert any("get_array()" in chunk.content for chunk in func_chunks)
        struct_chunks = [c for c in chunks if c.node_type == "struct_specifier"
            ]
        assert any("struct Flags" in chunk.content for chunk in struct_chunks)

    @staticmethod
    def test_header_file_parsing(tmp_path):
        """Test parsing of header files."""
        header_file = tmp_path / "test.h"
        header_file.write_text(
            """
#ifndef TEST_H
#define TEST_H

#include <stdint.h>
#include <stdbool.h>

// Constants
#define BUFFER_SIZE 1024
#define MAX_CONNECTIONS 100

// Type definitions
typedef struct Connection Connection;
typedef void (*EventHandler)(Connection*, int);

// Structures
struct Connection {
    int socket_fd;
    char buffer[BUFFER_SIZE];
    EventHandler on_data;
    EventHandler on_close;
    bool is_active;
};

// Function declarations
Connection* connection_create(int socket_fd);
void connection_destroy(Connection* conn);
int connection_send(Connection* conn, const char* data, size_t len);
int connection_receive(Connection* conn, char* buffer, size_t max_len);

// Inline functions
static inline bool connection_is_active(const Connection* conn) {
    return conn && conn->is_active;
}

#endif // TEST_H
""",
            )
        chunks = chunk_file(header_file, "c")
        chunk_types = {chunk.node_type for chunk in chunks}
        assert "struct_specifier" in chunk_types
        assert "function_definition" in chunk_types
        contents = [chunk.content for chunk in chunks]
        assert any("struct Connection" in content for content in contents)
        assert any("connection_is_active(const Connection* conn)" in
            content for content in contents)

    @staticmethod
    def test_context_preservation(tmp_path):
        """Test that context is properly preserved in nested structures."""
        test_file = tmp_path / "context.c"
        test_file.write_text(
            """
struct Outer {
    int outer_field;

    struct Inner {
        int inner_field;

        union Data {
            int i;
            float f;
        } data;
    } inner;
};

void process_outer(struct Outer* o) {
    o->outer_field = 10;
    o->inner.inner_field = 20;
    o->inner.data.i = 30;
}
""",
            )
        chunks = chunk_file(test_file, "c")
        struct_chunks = [c for c in chunks if c.node_type == "struct_specifier"
            ]
        assert any("struct Outer" in chunk.content for chunk in struct_chunks)
        func_chunks = [c for c in chunks if c.node_type ==
            "function_definition"]
        assert any("process_outer(struct Outer* o)" in chunk.content for
            chunk in func_chunks)

    @staticmethod
    def test_inline_assembly(tmp_path):
        """Test handling of inline assembly code."""
        test_file = tmp_path / "assembly.c"
        test_file.write_text(
            """
int atomic_add(int* ptr, int value) {
    int result;
    __asm__ volatile(
        "lock xaddl %0, %1"
        : "=r" (result), "+m" (*ptr)
        : "0" (value)
        : "memory"
    );
    return result;
}

void memory_barrier() {
    __asm__ volatile("mfence" ::: "memory");
}

int get_cpu_id() {
    int cpu;
    __asm__("movl %%gs:0, %0" : "=r" (cpu));
    return cpu;
}
""",
            )
        chunks = chunk_file(test_file, "c")
        func_chunks = [c for c in chunks if c.node_type ==
            "function_definition"]
        assert len(func_chunks) == 3
        func_contents = [chunk.content for chunk in func_chunks]
        assert any("atomic_add(int* ptr, int value)" in content for content in
            func_contents)
        assert any("memory_barrier()" in content for content in func_contents)
        assert any("get_cpu_id()" in content for content in func_contents)

    @staticmethod
    def test_complex_macros(tmp_path):
        """Test handling of complex macro definitions."""
        test_file = tmp_path / "macros.c"
        test_file.write_text(
            """
#define FOREACH(item, array, size) \\
    for (int _i = 0; _i < (size); _i++) \\
        if ((item = &(array)[_i]), 1)

#define CONTAINER_OF(ptr, type, member) \\
    ((type *)((char *)(ptr) - offsetof(type, member)))

#define DECLARE_LIST(name, type) \\
    struct name##_node { \\
        type data; \\
        struct name##_node* next; \\
    }; \\
    struct name { \\
        struct name##_node* head; \\
        struct name##_node* tail; \\
        size_t size; \\
    }

DECLARE_LIST(int_list, int);

void process_list(struct int_list* list) {
    struct int_list_node* node;
    FOREACH(node, list->head, list->size) {
        node->data *= 2;
    }
}
""",
            )
        chunks = chunk_file(test_file, "c")
        func_chunks = [c for c in chunks if c.node_type ==
            "function_definition"]
        assert any("process_list(struct int_list* list)" in chunk.content for
            chunk in func_chunks)

    @staticmethod
    def test_forward_declarations(tmp_path):
        """Test handling of forward declarations."""
        test_file = tmp_path / "forward.c"
        test_file.write_text(
            """
// Forward declarations
struct Node;
typedef struct Node Node;

// Function using forward declared type
Node* create_node(int value);
void link_nodes(Node* a, Node* b);

// Actual definition
struct Node {
    int value;
    Node* next;
    Node* prev;
};

// Function implementations
Node* create_node(int value) {
    Node* node = malloc(sizeof(Node));
    node->value = value;
    node->next = NULL;
    node->prev = NULL;
    return node;
}

void link_nodes(Node* a, Node* b) {
    if (a) a->next = b;
    if (b) b->prev = a;
}
""",
            )
        chunks = chunk_file(test_file, "c")
        struct_chunks = [c for c in chunks if c.node_type == "struct_specifier"
            ]
        assert any("struct Node" in chunk.content for chunk in struct_chunks)
        func_chunks = [c for c in chunks if c.node_type ==
            "function_definition"]
        func_contents = [chunk.content for chunk in func_chunks]
        assert any("create_node(int value)" in content for content in
            func_contents)
        assert any("link_nodes(Node* a, Node* b)" in content for content in
            func_contents)


class TestCEdgeCases:
    """Test edge cases and complex C patterns."""

    @staticmethod
    def test_k_and_r_style_functions(tmp_path):
        """Test old K&R style function definitions."""
        test_file = tmp_path / "kr_style.c"
        test_file.write_text(
            """
// K&R style function definition
int old_style_func(a, b, c)
int a;
char* b;
double c;
{
    return a + strlen(b) + (int)c;
}

// Modern ANSI C style
int modern_func(int a, char* b, double c) {
    return a + strlen(b) + (int)c;
}
""",
            )
        chunks = chunk_file(test_file, "c")
        func_chunks = [c for c in chunks if c.node_type ==
            "function_definition"]
        assert len(func_chunks) >= 1
        assert any("modern_func(int a, char* b, double c)" in chunk.content for
            chunk in func_chunks)

    @staticmethod
    def test_variadic_functions(tmp_path):
        """Test variadic function definitions."""
        test_file = tmp_path / "variadic.c"
        test_file.write_text(
            """
#include <stdarg.h>

int sum(int count, ...) {
    va_list args;
    va_start(args, count);

    int total = 0;
    for (int i = 0; i < count; i++) {
        total += va_arg(args, int);
    }

    va_end(args);
    return total;
}

void log_message(const char* format, ...) {
    va_list args;
    va_start(args, format);
    vprintf(format, args);
    va_end(args);
}
""",
            )
        chunks = chunk_file(test_file, "c")
        func_chunks = [c for c in chunks if c.node_type ==
            "function_definition"]
        assert len(func_chunks) == 2
        func_contents = [chunk.content for chunk in func_chunks]
        assert any("sum(int count, ...)" in content for content in
            func_contents)
        assert any("log_message(const char* format, ...)" in content for
            content in func_contents)

    @staticmethod
    def test_anonymous_structures(tmp_path):
        """Test anonymous structs and unions."""
        test_file = tmp_path / "anonymous.c"
        test_file.write_text(
            """
struct Message {
    int type;
    union {
        struct {
            int x;
            int y;
        } point;
        struct {
            float radius;
            float angle;
        } polar;
        char text[100];
    };  // Anonymous union
};

typedef struct {
    enum { INT, FLOAT, STRING } type;
    union {
        int i;
        float f;
        char* s;
    };  // Anonymous union in anonymous struct
} Variant;
""",
            )
        chunks = chunk_file(test_file, "c")
        struct_chunks = [c for c in chunks if c.node_type == "struct_specifier"
            ]
        assert any("struct Message" in chunk.content for chunk in struct_chunks
            )

    @staticmethod
    def test_gnu_extensions(tmp_path):
        """Test GNU C extensions."""
        test_file = tmp_path / "gnu_ext.c"
        test_file.write_text(
            """
// GNU C statement expressions
#define MAX(a, b) ({ \\
    typeof(a) _a = (a); \\
    typeof(b) _b = (b); \\
    _a > _b ? _a : _b; \\
})

// Nested functions (GNU extension)
int outer_function(int x) {
    int inner_function(int y) {
        return x + y;
    }

    return inner_function(10);
}

// Designated initializers
struct Point points[] = {
    [0] = { .x = 1, .y = 2 },
    [5] = { .x = 5, .y = 10 },
};
""",
            )
        chunks = chunk_file(test_file, "c")
        func_chunks = [c for c in chunks if c.node_type ==
            "function_definition"]
        assert any("outer_function(int x)" in chunk.content for chunk in
            func_chunks)
