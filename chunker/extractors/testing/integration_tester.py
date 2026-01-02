# chunker/extractors/testing/integration_tester.py

import concurrent.futures
import json
import logging
import os
import statistics
import sys
import tempfile
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Import from all other tasks
from ..core.extraction_framework import (
    BaseExtractor,
    CallSite,
    ExtractionResult,
    ExtractionUtils,
)
from ..javascript.javascript_extractor import JavaScriptExtractor
from ..multi_language.multi_extractor import (
    CExtractor,
    CppExtractor,
    GoExtractor,
    JavaExtractor,
    OtherLanguagesExtractor,
)
from ..python.python_extractor import PythonExtractor
from ..rust.rust_extractor import RustExtractor

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Comprehensive test result with detailed metrics."""

    test_name: str
    language: str
    passed: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    execution_time: float = 0.0
    call_sites_found: int = 0
    accuracy_score: float = 0.0
    performance_metrics: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_error(self, error: str, exception: Exception | None = None) -> None:
        """Add error with optional exception details."""
        if exception:
            error_msg = f"{error}: {exception!s}\nTraceback: {traceback.format_exc()}"
        else:
            error_msg = error

        self.errors.append(error_msg)
        self.passed = False
        logger.error(f"Test {self.test_name} failed: {error_msg}")

    def add_warning(self, warning: str) -> None:
        """Add warning message."""
        self.warnings.append(warning)
        logger.warning(f"Test {self.test_name}: {warning}")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "test_name": self.test_name,
            "language": self.language,
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
            "execution_time": self.execution_time,
            "call_sites_found": self.call_sites_found,
            "accuracy_score": self.accuracy_score,
            "performance_metrics": self.performance_metrics,
            "metadata": self.metadata,
        }


@dataclass
class ExtractorTestSuite:
    """Complete test suite for all language extractors."""

    def __init__(self):
        """Initialize the test suite."""
        self.extractors = {
            "python": PythonExtractor(),
            "javascript": JavaScriptExtractor(),
            "rust": RustExtractor(),
            "go": GoExtractor(),
            "c": CExtractor(),
            "cpp": CppExtractor(),
            "java": JavaExtractor(),
        }

        # Test data for different languages
        self.test_samples = {
            "python": {
                "basic_calls": """
def main():
    print("Hello World")
    result = calculate_sum(10, 20)
    obj.method_call()
    return process_data(result)

class Calculator:
    def __init__(self):
        super().__init__()
        self.value = 0

    def add(self, x):
        self.value += x
        return math.sqrt(self.value)

calc = Calculator()
calc.add(5)
""",
                "complex_calls": """
import asyncio
from functools import wraps

@decorator_function
async def complex_function():
    await asyncio.sleep(1)
    result = [func(x) for x in range(10)]
    nested_call(lambda x: x.process())
    return sum(map(lambda y: y**2, filter(None, result)))

class DataProcessor:
    def __init__(self, **kwargs):
        self.config = dict(**kwargs)

    def process(self):
        with open("file.txt") as f:
            data = json.loads(f.read())

        return {
            'result': self.transform(data),
            'metadata': self.get_metadata()
        }

processor = DataProcessor(timeout=30)
result = processor.process()
""",
                "edge_cases": """
# Edge case scenarios
def test_edge_cases():
    # Nested function calls
    result = func1(func2(func3()))

    # Method chaining
    obj.method1().method2().method3()

    # Complex expressions
    value = (lambda x: x*2)(func_call())

    # Dictionary/list operations
    data = {"key": func_value()}
    items = [process(x) for x in get_data()]

    # Try/except with calls
    try:
        risky_operation()
    except Exception as e:
        handle_error(e)
    finally:
        cleanup_resources()

    return validate_result(result)
""",
            },
            "javascript": {
                "basic_calls": """
function main() {
    console.log("Hello World");
    const result = calculateSum(10, 20);
    obj.methodCall();
    return processData(result);
}

class Calculator {
    constructor() {
        super();
        this.value = 0;
    }

    add(x) {
        this.value += x;
        return Math.sqrt(this.value);
    }
}

const calc = new Calculator();
calc.add(5);
""",
                "complex_calls": """
import { Component } from 'react';

const AsyncComponent = async () => {
    await fetchData();
    const results = await Promise.all([
        api.getData(),
        cache.get('key'),
        db.query('SELECT * FROM table')
    ]);

    return results.map(r => r.process());
};

class DataProcessor extends Component {
    constructor(props) {
        super(props);
        this.state = { data: [] };
    }

    componentDidMount() {
        this.loadData();
    }

    async loadData() {
        try {
            const response = await fetch('/api/data');
            const data = await response.json();
            this.setState({ data: data.map(item => item.transform()) });
        } catch (error) {
            console.error('Failed to load data:', error);
            this.handleError(error);
        }
    }

    render() {
        return <div>{this.renderData()}</div>;
    }
}
""",
                "edge_cases": """
// JSX and template literals
const Component = ({ onClick }) => (
    <div>
        <Button onClick={handleClick} />
        <List>{items.map(item => <Item key={item.id} {...item} />)}</List>
    </div>
);

// Template literals with calls
const message = `Hello ${getName()}, balance: ${account.getBalance()}`;

// Chained calls and destructuring
const { data, error } = await api.fetch().then(response => response.json());

// Arrow functions and callbacks
const processed = data
    .filter(item => item.isValid())
    .map(item => item.transform())
    .reduce((acc, item) => acc.combine(item), new Accumulator());

// Event handlers
element.addEventListener('click', (event) => {
    event.preventDefault();
    handler.onClick(event);
});
""",
            },
            "rust": {
                "basic_calls": """
fn main() {
    println!("Hello World");
    let result = calculate_sum(10, 20);
    obj.method_call();
    process_data(result);
}

struct Calculator {
    value: i32,
}

impl Calculator {
    fn new() -> Self {
        Self { value: 0 }
    }

    fn add(&mut self, x: i32) {
        self.value += x;
        std::println!("Value: {}", self.value);
    }
}

let mut calc = Calculator::new();
calc.add(5);
""",
                "complex_calls": """
use std::collections::HashMap;
use tokio::time::{sleep, Duration};

#[derive(Debug)]
struct DataProcessor {
    config: HashMap<String, String>,
}

impl DataProcessor {
    async fn process(&self) -> Result<Vec<u32>, Box<dyn std::error::Error>> {
        let data = self.load_data().await?;
        let results = futures::stream::iter(data)
            .map(|item| async move { self.transform(item).await })
            .buffer_unordered(10)
            .collect::<Vec<_>>()
            .await;

        Ok(results.into_iter().collect::<Result<Vec<_>, _>>()?)
    }

    async fn load_data(&self) -> Result<Vec<String>, std::io::Error> {
        tokio::fs::read_to_string("data.txt")
            .await
            .map(|content| content.lines().map(String::from).collect())
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let processor = DataProcessor::new();
    let results = processor.process().await?;
    println!("Processed {} items", results.len());
    Ok(())
}
""",
                "edge_cases": """
// Macro calls
println!("Debug: {:?}", data);
vec![1, 2, 3].iter().map(|x| x * 2).collect::<Vec<_>>();
format!("Value: {}", calculate_result());

// Method chaining
let result = data
    .iter()
    .filter(|&x| x.is_valid())
    .map(|x| x.transform())
    .collect::<Vec<_>>();

// Pattern matching with calls
match get_value() {
    Some(val) => process_value(val),
    None => handle_none(),
}

// Closure calls
let closure = |x| x * 2;
let mapped = data.iter().map(|&x| closure(x)).collect();

// Trait method calls
impl Iterator for MyStruct {
    type Item = i32;

    fn next(&mut self) -> Option<Self::Item> {
        self.generate_next()
    }
}
""",
            },
            "go": {
                "basic_calls": """
package main

import "fmt"

func main() {
    fmt.Println("Hello World")
    result := calculateSum(10, 20)
    obj.MethodCall()
    processData(result)
}

type Calculator struct {
    value int
}

func NewCalculator() *Calculator {
    return &Calculator{value: 0}
}

func (c *Calculator) Add(x int) {
    c.value += x
    fmt.Printf("Value: %d\\n", c.value)
}

func example() {
    calc := NewCalculator()
    calc.Add(5)
}
""",
                "complex_calls": """
package main

import (
    "context"
    "sync"
    "time"
)

type DataProcessor struct {
    config map[string]string
    mu     sync.RWMutex
}

func (dp *DataProcessor) Process(ctx context.Context) ([]int, error) {
    data, err := dp.loadData(ctx)
    if err != nil {
        return nil, handleError(err)
    }

    var wg sync.WaitGroup
    results := make([]int, len(data))

    for i, item := range data {
        wg.Add(1)
        go func(idx int, val string) {
            defer wg.Done()
            results[idx] = dp.transform(val)
        }(i, item)
    }

    wg.Wait()
    return validateResults(results), nil
}

func main() {
    ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
    defer cancel()

    processor := &DataProcessor{config: make(map[string]string)}
    results, err := processor.Process(ctx)
    if err != nil {
        log.Fatal(handleFatalError(err))
    }

    fmt.Printf("Processed %d items\\n", len(results))
}
""",
                "edge_cases": """
// Defer and goroutines
func complexFunction() {
    defer cleanup()
    defer func() { recover() }()

    go backgroundProcess()
    go func() {
        processAsync()
    }()

    // Channel operations
    ch := make(chan int)
    go sender(ch)
    result := <-ch

    // Interface calls
    var processor interface{} = &DataProcessor{}
    if p, ok := processor.(Processor); ok {
        p.Process()
    }

    // Method expressions
    fn := (*Calculator).Add
    fn(calc, 10)
}

// Package-level function calls
func init() {
    registerHandlers()
    setupLogging()
}
""",
            },
            "c": {
                "basic_calls": """
#include <stdio.h>
#include <stdlib.h>

int main() {
    printf("Hello World\\n");
    int result = calculate_sum(10, 20);
    process_data(result);
    return 0;
}

int calculate_sum(int a, int b) {
    return add_numbers(a, b);
}

void process_data(int data) {
    validate_input(data);
    transform_data(data);
    store_result(data);
}
""",
                "complex_calls": """
#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>

typedef struct {
    int (*process)(int);
    void (*cleanup)(void);
} processor_t;

void* worker_thread(void* arg) {
    processor_t* proc = (processor_t*)arg;
    int result = proc->process(get_input());
    proc->cleanup();
    return NULL;
}

int main() {
    processor_t processor = {
        .process = process_function,
        .cleanup = cleanup_function
    };

    pthread_t thread;
    pthread_create(&thread, NULL, worker_thread, &processor);
    pthread_join(thread, NULL);

    FILE* file = fopen("output.txt", "w");
    if (file) {
        fprintf(file, "Result: %d\\n", calculate_final_result());
        fclose(file);
    }

    return 0;
}
""",
                "edge_cases": """
// Function pointers and callbacks
typedef int (*callback_t)(int);

void register_callback(callback_t cb) {
    global_callback = cb;
}

// Macro calls
#define CALL_FUNC(name, arg) name##_function(arg)
#define LOG(msg) printf("[LOG] %s\\n", msg)

int complex_main() {
    CALL_FUNC(process, 42);
    LOG("Processing started");

    // Function pointer calls
    int (*operation)(int, int) = &add_numbers;
    int result = operation(10, 20);

    // Variadic function calls
    printf("Values: %d, %s, %f\\n", result, "test", 3.14);

    return validate_and_exit(result);
}
""",
            },
            "cpp": {
                "basic_calls": """
#include <iostream>
#include <memory>

class Calculator {
private:
    int value;

public:
    Calculator() : value(0) {
        initialize();
    }

    void add(int x) {
        value += x;
        std::cout << "Value: " << value << std::endl;
    }

    ~Calculator() {
        cleanup();
    }
};

int main() {
    std::cout << "Hello World" << std::endl;
    auto calc = std::make_unique<Calculator>();
    calc->add(5);

    int result = calculateSum(10, 20);
    processData(result);

    return 0;
}
""",
                "complex_calls": """
#include <algorithm>
#include <vector>
#include <future>
#include <memory>

template<typename T>
class DataProcessor {
private:
    std::vector<T> data;

public:
    template<typename Func>
    auto process(Func transformer) -> std::vector<decltype(transformer(T{}))> {
        std::vector<decltype(transformer(T{}))> results;

        std::transform(data.begin(), data.end(),
                      std::back_inserter(results),
                      [&](const T& item) {
                          return transformer(item);
                      });

        return results;
    }

    std::future<void> async_process() {
        return std::async(std::launch::async, [this]() {
            for (auto& item : data) {
                item.transform();
                this->validate(item);
            }
        });
    }
};

int main() {
    DataProcessor<int> processor;

    auto results = processor.process([](int x) {
        return std::to_string(x);
    });

    auto future = processor.async_process();
    future.wait();

    std::for_each(results.begin(), results.end(),
                  [](const std::string& s) {
                      std::cout << s << std::endl;
                  });

    return 0;
}
""",
                "edge_cases": """
// Template metaprogramming and operator overloading
template<typename T>
class SmartPointer {
public:
    T& operator*() { return get_reference(); }
    T* operator->() { return get_pointer(); }
    operator bool() const { return is_valid(); }
};

// RAII and constructor calls
class ResourceManager {
public:
    ResourceManager() : resource(acquire_resource()) {
        register_cleanup(std::bind(&ResourceManager::cleanup, this));
    }

    ~ResourceManager() {
        release_resource(resource);
    }
};

// STL algorithm usage
void stl_example() {
    std::vector<int> data = {1, 2, 3, 4, 5};

    std::sort(data.begin(), data.end(), std::greater<int>());

    auto it = std::find_if(data.begin(), data.end(),
                          [](int x) { return x > 3; });

    if (it != data.end()) {
        process_found_element(*it);
    }
}
""",
            },
            "java": {
                "basic_calls": """
public class Main {
    public static void main(String[] args) {
        System.out.println("Hello World");
        int result = calculateSum(10, 20);
        Calculator calc = new Calculator();
        calc.add(5);
        processData(result);
    }

    private static int calculateSum(int a, int b) {
        return Math.addExact(a, b);
    }
}

class Calculator {
    private int value;

    public Calculator() {
        super();
        this.value = 0;
        initialize();
    }

    public void add(int x) {
        this.value += x;
        System.out.println("Value: " + this.value);
    }
}
""",
                "complex_calls": """
import java.util.concurrent.*;
import java.util.stream.*;

public class DataProcessor {
    private final ExecutorService executor = Executors.newFixedThreadPool(10);

    public CompletableFuture<List<String>> processAsync(List<Integer> data) {
        return CompletableFuture.supplyAsync(() -> {
            return data.stream()
                      .parallel()
                      .map(this::transform)
                      .filter(Objects::nonNull)
                      .collect(Collectors.toList());
        }, executor);
    }

    private String transform(Integer value) {
        try {
            Thread.sleep(100);
            return String.valueOf(Math.sqrt(value));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            handleInterruption(e);
            return null;
        }
    }

    public void cleanup() {
        executor.shutdown();
        try {
            executor.awaitTermination(60, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            executor.shutdownNow();
        }
    }
}
""",
                "edge_cases": """
// Generics, lambdas, and method references
public class GenericProcessor<T extends Comparable<T>> {

    public <R> Stream<R> process(List<T> data, Function<T, R> mapper) {
        return data.stream()
                   .sorted(T::compareTo)
                   .map(mapper)
                   .filter(Objects::nonNull);
    }

    // Anonymous inner classes
    private final Comparator<T> customComparator = new Comparator<T>() {
        @Override
        public int compare(T o1, T o2) {
            return o1.compareTo(o2);
        }
    };

    // Method chaining with builder pattern
    public static Builder builder() {
        return new Builder()
                   .withTimeout(30)
                   .withRetries(3)
                   .withCallback(System.out::println);
    }
}

// Reflection and dynamic calls
public void reflectionExample() throws Exception {
    Class<?> clazz = Class.forName("com.example.Calculator");
    Object instance = clazz.getDeclaredConstructor().newInstance();

    Method method = clazz.getMethod("add", int.class);
    method.invoke(instance, 42);
}
""",
            },
        }

        # Performance benchmarks for validation
        self.performance_thresholds = {
            "python": {"max_time_per_kb": 0.05, "min_accuracy": 0.90},
            "javascript": {"max_time_per_kb": 0.03, "min_accuracy": 0.85},
            "rust": {"max_time_per_kb": 0.04, "min_accuracy": 0.88},
            "go": {"max_time_per_kb": 0.03, "min_accuracy": 0.85},
            "c": {"max_time_per_kb": 0.03, "min_accuracy": 0.80},
            "cpp": {"max_time_per_kb": 0.04, "min_accuracy": 0.82},
            "java": {"max_time_per_kb": 0.04, "min_accuracy": 0.85},
        }

        self.logger = logging.getLogger(__name__)

    def run_all_tests(self) -> dict[str, Any]:
        """Run complete test suite for all extractors."""
        start_time = time.perf_counter()
        results = {
            "overall_passed": True,
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "execution_time": 0.0,
            "language_results": {},
            "summary": {},
            "errors": [],
            "performance_summary": {},
        }

        self.logger.info("Starting comprehensive extractor test suite")

        try:
            # Run language-specific tests
            language_results = self.test_language_extractors()
            results["language_results"] = language_results

            # Run cross-language integration tests
            integration_results = self.test_cross_language_integration()
            results["integration_results"] = integration_results

            # Run performance benchmarks
            benchmark_results = self.benchmark_performance()
            results["benchmark_results"] = benchmark_results

            # Calculate overall statistics
            for lang_result in language_results.values():
                results["total_tests"] += len(lang_result.get("tests", []))
                for test in lang_result.get("tests", []):
                    if test.get("passed", False):
                        results["passed_tests"] += 1
                    else:
                        results["failed_tests"] += 1
                        results["overall_passed"] = False

            # Generate summary
            results["summary"] = self._generate_test_summary(results)
            results["performance_summary"] = self._generate_performance_summary(
                benchmark_results,
            )

        except Exception as e:
            results["overall_passed"] = False
            results["errors"].append(f"Critical error in test suite: {e!s}")
            self.logger.error(f"Test suite failed with error: {e}", exc_info=True)

        results["execution_time"] = time.perf_counter() - start_time
        self.logger.info(f"Test suite completed in {results['execution_time']:.2f}s")

        return results

    def test_language_extractors(self) -> dict[str, Any]:
        """Test individual language extractors."""
        results = {}

        self.logger.info("Testing individual language extractors")

        # Test each extractor
        for language, extractor in self.extractors.items():
            self.logger.info(f"Testing {language} extractor")

            lang_results = {
                "extractor_class": extractor.__class__.__name__,
                "tests": [],
                "overall_passed": True,
                "total_time": 0.0,
                "errors": [],
                "warnings": [],
            }

            try:
                # Test basic functionality
                basic_test = self._test_basic_extraction(language, extractor)
                lang_results["tests"].append(basic_test.to_dict())
                lang_results["total_time"] += basic_test.execution_time

                if not basic_test.passed:
                    lang_results["overall_passed"] = False

                # Test complex scenarios
                complex_test = self._test_complex_extraction(language, extractor)
                lang_results["tests"].append(complex_test.to_dict())
                lang_results["total_time"] += complex_test.execution_time

                if not complex_test.passed:
                    lang_results["overall_passed"] = False

                # Test edge cases
                edge_test = self._test_edge_cases(language, extractor)
                lang_results["tests"].append(edge_test.to_dict())
                lang_results["total_time"] += edge_test.execution_time

                if not edge_test.passed:
                    lang_results["overall_passed"] = False

                # Test error handling
                error_test = self._test_error_handling(language, extractor)
                lang_results["tests"].append(error_test.to_dict())
                lang_results["total_time"] += error_test.execution_time

                if not error_test.passed:
                    lang_results["overall_passed"] = False

                # Test validation
                validation_test = self._test_validation(language, extractor)
                lang_results["tests"].append(validation_test.to_dict())
                lang_results["total_time"] += validation_test.execution_time

                if not validation_test.passed:
                    lang_results["overall_passed"] = False

            except Exception as e:
                lang_results["overall_passed"] = False
                lang_results["errors"].append(
                    f"Critical error testing {language}: {e!s}",
                )
                self.logger.error(
                    f"Error testing {language} extractor: {e}",
                    exc_info=True,
                )

            results[language] = lang_results

        return results

    def test_cross_language_integration(self) -> dict[str, Any]:
        """Test integration between different language extractors."""
        self.logger.info("Testing cross-language integration")

        results = {
            "consistency_tests": [],
            "multi_file_tests": [],
            "performance_comparison": {},
            "overall_passed": True,
            "execution_time": 0.0,
        }

        start_time = time.perf_counter()

        try:
            # Test consistency across extractors
            consistency_results = self._test_extractor_consistency()
            results["consistency_tests"] = consistency_results

            # Test multi-file scenarios
            multi_file_results = self._test_multi_file_scenarios()
            results["multi_file_tests"] = multi_file_results

            # Compare performance across languages
            performance_comparison = self._compare_extractor_performance()
            results["performance_comparison"] = performance_comparison

            # Check if any tests failed
            all_tests = consistency_results + multi_file_results
            for test in all_tests:
                if (isinstance(test, dict) and not test.get("passed", True)) or (
                    hasattr(test, "passed") and not test.passed
                ):
                    results["overall_passed"] = False

        except Exception as e:
            results["overall_passed"] = False
            results["errors"] = [f"Integration testing failed: {e!s}"]
            self.logger.error(f"Integration testing failed: {e}", exc_info=True)

        results["execution_time"] = time.perf_counter() - start_time
        return results

    def benchmark_performance(self) -> dict[str, Any]:
        """Benchmark performance of all extractors."""
        self.logger.info("Benchmarking extractor performance")

        results = {
            "language_benchmarks": {},
            "comparative_analysis": {},
            "performance_regression_check": {},
            "resource_usage": {},
            "execution_time": 0.0,
        }

        start_time = time.perf_counter()

        try:
            # Generate test files of varying sizes
            test_files = self._generate_performance_test_files()

            # Benchmark each extractor
            for language, extractor in self.extractors.items():
                self.logger.info(f"Benchmarking {language} extractor")

                lang_benchmarks = {
                    "small_files": [],
                    "medium_files": [],
                    "large_files": [],
                    "memory_usage": {},
                    "cpu_usage": {},
                    "accuracy_scores": [],
                }

                # Test different file sizes
                for file_size, content in test_files.items():
                    lang_content = content.get(language, content.get("generic", ""))
                    if lang_content:
                        benchmark_result = self._benchmark_single_extractor(
                            extractor,
                            lang_content,
                            f"{language}_{file_size}",
                        )
                        lang_benchmarks[file_size].append(benchmark_result)

                results["language_benchmarks"][language] = lang_benchmarks

            # Generate comparative analysis
            results["comparative_analysis"] = self._generate_comparative_analysis(
                results["language_benchmarks"],
            )

            # Check for performance regressions
            results["performance_regression_check"] = (
                self._check_performance_regressions(results["language_benchmarks"])
            )

            # Clean up test files
            self._cleanup_performance_test_files(test_files)

        except Exception as e:
            results["errors"] = [f"Performance benchmarking failed: {e!s}"]
            self.logger.error(f"Performance benchmarking failed: {e}", exc_info=True)

        results["execution_time"] = time.perf_counter() - start_time
        return results

    def _test_basic_extraction(
        self,
        language: str,
        extractor: BaseExtractor,
    ) -> TestResult:
        """Test basic extraction functionality."""
        test_result = TestResult("basic_extraction", language)

        try:
            start_time = time.perf_counter()

            # Get test sample
            sample_code = self.test_samples[language]["basic_calls"]

            # Extract calls
            extraction_result = extractor.extract_calls(sample_code)

            test_result.execution_time = time.perf_counter() - start_time
            test_result.call_sites_found = len(extraction_result.call_sites)

            # Validate extraction result
            if not isinstance(extraction_result, ExtractionResult):
                test_result.add_error("Expected ExtractionResult object")
                return test_result

            # Check for successful extraction
            if extraction_result.errors:
                test_result.add_warning(
                    f"Extraction had errors: {extraction_result.errors}",
                )

            # Validate call sites
            valid_calls = 0
            for call_site in extraction_result.call_sites:
                if isinstance(call_site, CallSite):
                    validation_errors = ExtractionUtils.validate_call_site(
                        call_site,
                        sample_code,
                    )
                    if not validation_errors:
                        valid_calls += 1
                    else:
                        test_result.add_warning(
                            f"Invalid call site: {validation_errors}",
                        )

            # Calculate accuracy
            if test_result.call_sites_found > 0:
                test_result.accuracy_score = valid_calls / test_result.call_sites_found
            else:
                test_result.accuracy_score = 0.0
                test_result.add_warning("No call sites found")

            # Check minimum requirements
            min_expected_calls = 3  # Based on test samples
            if test_result.call_sites_found < min_expected_calls:
                test_result.add_warning(
                    f"Expected at least {min_expected_calls} calls, found {test_result.call_sites_found}",
                )

            # Performance check
            threshold = self.performance_thresholds[language]
            code_size_kb = len(sample_code.encode("utf-8")) / 1024
            time_per_kb = (
                test_result.execution_time / code_size_kb
                if code_size_kb > 0
                else float("inf")
            )

            if time_per_kb > threshold["max_time_per_kb"]:
                test_result.add_warning(
                    f"Performance below threshold: {time_per_kb:.4f}s/KB > {threshold['max_time_per_kb']}s/KB",
                )

            if test_result.accuracy_score < threshold["min_accuracy"]:
                test_result.add_warning(
                    f"Accuracy below threshold: {test_result.accuracy_score:.2f} < {threshold['min_accuracy']}",
                )

            # Test passes if no errors
            test_result.passed = len(test_result.errors) == 0

            test_result.metadata = {
                "sample_size_bytes": len(sample_code.encode("utf-8")),
                "valid_calls": valid_calls,
                "time_per_kb": time_per_kb,
                "extraction_metadata": extraction_result.metadata,
            }

        except Exception as e:
            test_result.add_error("Basic extraction test failed", e)

        return test_result

    def _test_complex_extraction(
        self,
        language: str,
        extractor: BaseExtractor,
    ) -> TestResult:
        """Test complex extraction scenarios."""
        test_result = TestResult("complex_extraction", language)

        try:
            start_time = time.perf_counter()

            # Get complex test sample
            sample_code = self.test_samples[language]["complex_calls"]

            # Extract calls
            extraction_result = extractor.extract_calls(sample_code)

            test_result.execution_time = time.perf_counter() - start_time
            test_result.call_sites_found = len(extraction_result.call_sites)

            # Validate complex patterns
            complex_patterns_found = 0
            for call_site in extraction_result.call_sites:
                # Check for complex call types
                if call_site.call_type in ["method", "async", "lambda", "complex"]:
                    complex_patterns_found += 1

                # Validate position information
                validation_errors = ExtractionUtils.validate_call_site(
                    call_site,
                    sample_code,
                )
                if validation_errors:
                    test_result.add_warning(
                        f"Complex call validation failed: {validation_errors}",
                    )

            # Check for expected complex patterns
            if complex_patterns_found == 0:
                test_result.add_warning("No complex patterns detected")

            # Calculate accuracy for complex scenarios
            expected_complex_calls = self._count_expected_complex_calls(language)
            if expected_complex_calls > 0:
                test_result.accuracy_score = min(
                    1.0,
                    complex_patterns_found / expected_complex_calls,
                )
            else:
                test_result.accuracy_score = (
                    1.0 if test_result.call_sites_found > 0 else 0.0
                )

            test_result.passed = (
                len(test_result.errors) == 0 and test_result.accuracy_score > 0.5
            )

            test_result.metadata = {
                "complex_patterns_found": complex_patterns_found,
                "expected_complex_calls": expected_complex_calls,
                "sample_complexity": len(sample_code.splitlines()),
            }

        except Exception as e:
            test_result.add_error("Complex extraction test failed", e)

        return test_result

    def _test_edge_cases(self, language: str, extractor: BaseExtractor) -> TestResult:
        """Test edge case scenarios."""
        test_result = TestResult("edge_cases", language)

        try:
            start_time = time.perf_counter()

            # Get edge case sample
            sample_code = self.test_samples[language]["edge_cases"]

            # Extract calls
            extraction_result = extractor.extract_calls(sample_code)

            test_result.execution_time = time.perf_counter() - start_time
            test_result.call_sites_found = len(extraction_result.call_sites)

            # Test specific edge cases
            edge_case_coverage = 0
            edge_cases_to_check = self._get_edge_cases_for_language(language)

            for edge_case in edge_cases_to_check:
                if self._check_edge_case_coverage(
                    extraction_result.call_sites,
                    edge_case,
                ):
                    edge_case_coverage += 1

            if edge_cases_to_check:
                test_result.accuracy_score = edge_case_coverage / len(
                    edge_cases_to_check,
                )
            else:
                test_result.accuracy_score = 1.0

            # Check for robustness
            if extraction_result.errors:
                test_result.add_warning(
                    f"Edge case extraction had errors: {extraction_result.errors}",
                )

            test_result.passed = (
                len(test_result.errors) == 0 and test_result.accuracy_score > 0.3
            )

            test_result.metadata = {
                "edge_cases_checked": len(edge_cases_to_check),
                "edge_cases_covered": edge_case_coverage,
                "robustness_score": test_result.accuracy_score,
            }

        except Exception as e:
            test_result.add_error("Edge case test failed", e)

        return test_result

    def _test_error_handling(
        self,
        language: str,
        extractor: BaseExtractor,
    ) -> TestResult:
        """Test error handling capabilities."""
        test_result = TestResult("error_handling", language)

        try:
            start_time = time.perf_counter()

            error_scenarios = [
                ("empty_code", ""),
                ("whitespace_only", "   \n\t  \n"),
                ("invalid_syntax", "def invalid syntax here {"),
                ("malformed_calls", "func(((((incomplete"),
                ("unicode_content", "def функция(): вызов_функции()"),
                ("very_long_line", "a" * 10000 + "()"),
            ]

            passed_scenarios = 0
            total_scenarios = len(error_scenarios)

            for scenario_name, test_code in error_scenarios:
                try:
                    result = extractor.extract_calls(test_code)

                    # Error handling should not crash
                    if isinstance(result, ExtractionResult):
                        passed_scenarios += 1
                    else:
                        test_result.add_warning(
                            f"Scenario '{scenario_name}' returned non-result",
                        )

                except Exception as e:
                    # Some errors might be expected, but crashes should be handled
                    test_result.add_warning(
                        f"Scenario '{scenario_name}' caused exception: {e!s}",
                    )

            test_result.execution_time = time.perf_counter() - start_time
            test_result.accuracy_score = (
                passed_scenarios / total_scenarios if total_scenarios > 0 else 1.0
            )
            test_result.passed = test_result.accuracy_score > 0.8  # Allow some failures

            test_result.metadata = {
                "total_scenarios": total_scenarios,
                "passed_scenarios": passed_scenarios,
                "error_handling_score": test_result.accuracy_score,
            }

        except Exception as e:
            test_result.add_error("Error handling test failed", e)

        return test_result

    def _test_validation(self, language: str, extractor: BaseExtractor) -> TestResult:
        """Test validation functionality."""
        test_result = TestResult("validation", language)

        try:
            start_time = time.perf_counter()

            # Test validate_source method
            validation_tests = [
                ("valid_code", self.test_samples[language]["basic_calls"], True),
                ("empty_code", "", True),  # Empty is often valid
                ("invalid_syntax", "def invalid: syntax {", False),
                ("random_text", "This is not code at all!", False),
            ]

            passed_validations = 0
            for test_name, code, expected_valid in validation_tests:
                try:
                    is_valid = extractor.validate_source(code)
                    if is_valid == expected_valid:
                        passed_validations += 1
                    else:
                        test_result.add_warning(
                            f"Validation '{test_name}': expected {expected_valid}, got {is_valid}",
                        )
                except Exception as e:
                    test_result.add_warning(
                        f"Validation '{test_name}' failed: {e!s}",
                    )

            test_result.execution_time = time.perf_counter() - start_time
            test_result.accuracy_score = passed_validations / len(validation_tests)
            test_result.passed = test_result.accuracy_score > 0.7

            test_result.metadata = {
                "validation_tests": len(validation_tests),
                "passed_validations": passed_validations,
            }

        except Exception as e:
            test_result.add_error("Validation test failed", e)

        return test_result

    def _test_extractor_consistency(self) -> list[dict[str, Any]]:
        """Test consistency across different extractors."""
        consistency_tests = []

        # Test common patterns across languages
        common_patterns = {
            "simple_function_call": {
                "python": 'print("hello")',
                "javascript": 'console.log("hello");',
                "java": 'System.out.println("hello");',
                "c": 'printf("hello");',
                "cpp": 'std::cout << "hello";',
            },
        }

        for pattern_name, implementations in common_patterns.items():
            test = {
                "pattern": pattern_name,
                "results": {},
                "passed": True,
                "consistency_score": 0.0,
            }

            call_counts = []
            for language, code in implementations.items():
                if language in self.extractors:
                    try:
                        result = self.extractors[language].extract_calls(code)
                        call_count = len(result.call_sites)
                        call_counts.append(call_count)
                        test["results"][language] = {
                            "call_count": call_count,
                            "extraction_time": result.extraction_time,
                            "errors": result.errors,
                        }
                    except Exception as e:
                        test["results"][language] = {"error": str(e)}
                        test["passed"] = False

            # Calculate consistency score
            if call_counts and len(set(call_counts)) == 1:
                test["consistency_score"] = 1.0
            elif call_counts:
                test["consistency_score"] = 1.0 - (
                    max(call_counts) - min(call_counts)
                ) / max(call_counts, default=1)

            consistency_tests.append(test)

        return consistency_tests

    def _test_multi_file_scenarios(self) -> list[dict[str, Any]]:
        """Test multi-file processing scenarios."""
        multi_file_tests = []

        # Create temporary directory with test files
        with tempfile.TemporaryDirectory() as temp_dir:
            test_files = {}

            # Create test files for each language
            for language, samples in self.test_samples.items():
                if language in self.extractors:
                    file_ext = {
                        "python": ".py",
                        "javascript": ".js",
                        "rust": ".rs",
                        "go": ".go",
                        "c": ".c",
                        "cpp": ".cpp",
                        "java": ".java",
                    }.get(language, ".txt")

                    file_path = Path(temp_dir) / f"test_{language}{file_ext}"
                    file_path.write_text(samples["basic_calls"])
                    test_files[language] = file_path

            # Test processing multiple files
            multi_file_test = {
                "test_name": "multi_file_processing",
                "files_processed": 0,
                "total_calls_found": 0,
                "processing_time": 0.0,
                "passed": True,
                "errors": [],
            }

            start_time = time.perf_counter()

            for language, file_path in test_files.items():
                try:
                    code = file_path.read_text()
                    result = self.extractors[language].extract_calls(code, file_path)

                    multi_file_test["files_processed"] += 1
                    multi_file_test["total_calls_found"] += len(result.call_sites)

                    # Verify file path is preserved
                    for call_site in result.call_sites:
                        if call_site.file_path != file_path:
                            multi_file_test["errors"].append(
                                f"File path mismatch in {language}",
                            )

                except Exception as e:
                    multi_file_test["errors"].append(
                        f"Error processing {language}: {e!s}",
                    )
                    multi_file_test["passed"] = False

            multi_file_test["processing_time"] = time.perf_counter() - start_time
            multi_file_tests.append(multi_file_test)

        return multi_file_tests

    def _compare_extractor_performance(self) -> dict[str, Any]:
        """Compare performance across extractors."""
        comparison = {
            "processing_speeds": {},
            "accuracy_scores": {},
            "resource_efficiency": {},
            "reliability_scores": {},
        }

        # Common test code for comparison
        test_code = "function test() { call1(); call2(); return result(); }"

        for language, extractor in self.extractors.items():
            start_time = time.perf_counter()

            try:
                # Run multiple iterations for average
                iterations = 10
                total_calls = 0

                for _ in range(iterations):
                    result = extractor.extract_calls(test_code)
                    total_calls += len(result.call_sites)

                processing_time = time.perf_counter() - start_time
                avg_calls = total_calls / iterations

                comparison["processing_speeds"][language] = processing_time / iterations
                comparison["accuracy_scores"][language] = min(
                    1.0,
                    avg_calls / 3,
                )  # Expected 3 calls
                comparison["reliability_scores"][language] = 1.0  # No errors

            except Exception:
                comparison["processing_speeds"][language] = float("inf")
                comparison["accuracy_scores"][language] = 0.0
                comparison["reliability_scores"][language] = 0.0

        return comparison

    def _generate_performance_test_files(self) -> dict[str, dict[str, str]]:
        """Generate test files of varying sizes for performance testing."""
        test_files = {"small_files": {}, "medium_files": {}, "large_files": {}}

        # Generate small files (< 1KB)
        for language in self.extractors:
            test_files["small_files"][language] = self.test_samples[language][
                "basic_calls"
            ]

        # Generate medium files (~10KB)
        for language in self.extractors:
            base_code = self.test_samples[language]["basic_calls"]
            medium_code = base_code
            while len(medium_code.encode("utf-8")) < 10000:
                medium_code += "\n" + base_code
            test_files["medium_files"][language] = medium_code

        # Generate large files (~100KB)
        for language in self.extractors:
            medium_code = test_files["medium_files"][language]
            large_code = medium_code
            while len(large_code.encode("utf-8")) < 100000:
                large_code += "\n" + medium_code
            test_files["large_files"][language] = large_code

        return test_files

    def _benchmark_single_extractor(
        self,
        extractor: BaseExtractor,
        code: str,
        test_name: str,
    ) -> dict[str, Any]:
        """Benchmark a single extractor with given code."""
        benchmark = {
            "test_name": test_name,
            "code_size_bytes": len(code.encode("utf-8")),
            "execution_time": 0.0,
            "calls_found": 0,
            "memory_peak_mb": 0.0,
            "throughput_kb_per_second": 0.0,
            "errors": [],
        }

        try:
            import os

            import psutil

            process = psutil.Process(os.getpid())
            memory_before = process.memory_info().rss / 1024 / 1024  # MB

            start_time = time.perf_counter()
            result = extractor.extract_calls(code)
            execution_time = time.perf_counter() - start_time

            memory_after = process.memory_info().rss / 1024 / 1024  # MB

            benchmark["execution_time"] = execution_time
            benchmark["calls_found"] = len(result.call_sites)
            benchmark["memory_peak_mb"] = memory_after - memory_before

            if execution_time > 0:
                benchmark["throughput_kb_per_second"] = (
                    benchmark["code_size_bytes"] / 1024
                ) / execution_time

            if result.errors:
                benchmark["errors"] = result.errors

        except ImportError:
            # Fallback without memory monitoring
            start_time = time.perf_counter()
            result = extractor.extract_calls(code)
            execution_time = time.perf_counter() - start_time

            benchmark["execution_time"] = execution_time
            benchmark["calls_found"] = len(result.call_sites)

            if execution_time > 0:
                benchmark["throughput_kb_per_second"] = (
                    benchmark["code_size_bytes"] / 1024
                ) / execution_time

        except Exception as e:
            benchmark["errors"].append(str(e))

        return benchmark

    def _generate_comparative_analysis(
        self,
        language_benchmarks: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate comparative analysis of benchmark results."""
        analysis = {
            "fastest_extractor": None,
            "most_accurate_extractor": None,
            "most_memory_efficient": None,
            "performance_rankings": {},
            "recommendations": [],
        }

        try:
            # Collect performance metrics
            extractor_metrics = {}

            for language, benchmarks in language_benchmarks.items():
                metrics = {
                    "avg_execution_time": 0.0,
                    "avg_throughput": 0.0,
                    "avg_accuracy": 0.0,
                    "avg_memory_usage": 0.0,
                    "total_benchmarks": 0,
                }

                all_benchmarks = []
                for file_size in ["small_files", "medium_files", "large_files"]:
                    all_benchmarks.extend(benchmarks.get(file_size, []))

                if all_benchmarks:
                    metrics["avg_execution_time"] = statistics.mean(
                        b.get("execution_time", 0) for b in all_benchmarks
                    )
                    metrics["avg_throughput"] = statistics.mean(
                        b.get("throughput_kb_per_second", 0) for b in all_benchmarks
                    )
                    metrics["avg_memory_usage"] = statistics.mean(
                        b.get("memory_peak_mb", 0) for b in all_benchmarks
                    )
                    metrics["total_benchmarks"] = len(all_benchmarks)

                extractor_metrics[language] = metrics

            # Find best performers
            if extractor_metrics:
                analysis["fastest_extractor"] = min(
                    extractor_metrics.items(),
                    key=lambda x: x[1]["avg_execution_time"],
                )[0]

                analysis["most_memory_efficient"] = min(
                    extractor_metrics.items(),
                    key=lambda x: x[1]["avg_memory_usage"],
                )[0]

                # Create performance rankings
                for metric in [
                    "avg_execution_time",
                    "avg_throughput",
                    "avg_memory_usage",
                ]:
                    rankings = sorted(
                        extractor_metrics.items(),
                        key=lambda x: x[1][metric],
                        reverse=(metric == "avg_throughput"),
                    )
                    analysis["performance_rankings"][metric] = [
                        lang for lang, _ in rankings
                    ]

            # Generate recommendations
            analysis["recommendations"] = self._generate_performance_recommendations(
                extractor_metrics,
            )

        except Exception as e:
            analysis["error"] = f"Analysis generation failed: {e!s}"

        return analysis

    def _check_performance_regressions(
        self,
        language_benchmarks: dict[str, Any],
    ) -> dict[str, Any]:
        """Check for performance regressions against thresholds."""
        regression_check = {
            "regressions_found": [],
            "performance_status": {},
            "recommendations": [],
        }

        for language, benchmarks in language_benchmarks.items():
            if language in self.performance_thresholds:
                threshold = self.performance_thresholds[language]
                status = {
                    "meets_time_threshold": True,
                    "meets_accuracy_threshold": True,
                    "issues": [],
                }

                # Check all benchmark results
                all_benchmarks = []
                for file_size in ["small_files", "medium_files", "large_files"]:
                    all_benchmarks.extend(benchmarks.get(file_size, []))

                for benchmark in all_benchmarks:
                    # Check time threshold
                    if benchmark.get("code_size_bytes", 0) > 0:
                        time_per_kb = benchmark.get("execution_time", 0) / (
                            benchmark["code_size_bytes"] / 1024
                        )
                        if time_per_kb > threshold["max_time_per_kb"]:
                            status["meets_time_threshold"] = False
                            status["issues"].append(
                                f"Slow performance: {time_per_kb:.4f}s/KB > {threshold['max_time_per_kb']}s/KB",
                            )
                            regression_check["regressions_found"].append(
                                {
                                    "language": language,
                                    "issue": "performance_regression",
                                    "details": "Time per KB exceeded threshold",
                                },
                            )

                regression_check["performance_status"][language] = status

        return regression_check

    def _cleanup_performance_test_files(
        self,
        test_files: dict[str, dict[str, str]],
    ) -> None:
        """Clean up any temporary files created during performance testing."""
        # In this implementation, we're using in-memory content, so no cleanup needed
        # This method exists for completeness and future file-based testing

    def _generate_test_summary(self, results: dict[str, Any]) -> dict[str, Any]:
        """Generate comprehensive test summary."""
        summary = {
            "test_completion_status": "COMPLETED",
            "overall_success_rate": 0.0,
            "total_test_time": results.get("execution_time", 0.0),
            "language_performance": {},
            "critical_issues": [],
            "recommendations": [],
        }

        try:
            if results["total_tests"] > 0:
                summary["overall_success_rate"] = (
                    results["passed_tests"] / results["total_tests"]
                )

            # Summarize language performance
            for language, lang_result in results.get("language_results", {}).items():
                lang_tests = lang_result.get("tests", [])
                if lang_tests:
                    passed = sum(1 for t in lang_tests if t.get("passed", False))
                    summary["language_performance"][language] = {
                        "success_rate": passed / len(lang_tests),
                        "avg_accuracy": statistics.mean(
                            t.get("accuracy_score", 0.0) for t in lang_tests
                        ),
                        "avg_execution_time": statistics.mean(
                            t.get("execution_time", 0.0) for t in lang_tests
                        ),
                        "total_calls_found": sum(
                            t.get("call_sites_found", 0) for t in lang_tests
                        ),
                    }

            # Identify critical issues
            for language, perf in summary["language_performance"].items():
                if perf["success_rate"] < 0.7:
                    summary["critical_issues"].append(
                        f"{language} extractor has low success rate: {perf['success_rate']:.2f}",
                    )

                if perf["avg_accuracy"] < 0.5:
                    summary["critical_issues"].append(
                        f"{language} extractor has low accuracy: {perf['avg_accuracy']:.2f}",
                    )

            # Generate recommendations
            if summary["overall_success_rate"] < 0.8:
                summary["recommendations"].append(
                    "Overall test success rate is below 80% - review failing extractors",
                )

            if len(summary["critical_issues"]) > 0:
                summary["recommendations"].append(
                    "Address critical issues before production deployment",
                )

        except Exception as e:
            summary["generation_error"] = str(e)

        return summary

    def _generate_performance_summary(
        self,
        benchmark_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate performance summary from benchmark results."""
        perf_summary = {
            "overall_performance_grade": "A",
            "fastest_languages": [],
            "memory_efficient_languages": [],
            "performance_concerns": [],
            "optimization_suggestions": [],
        }

        try:
            comparative_analysis = benchmark_results.get("comparative_analysis", {})

            # Extract performance rankings
            if "performance_rankings" in comparative_analysis:
                rankings = comparative_analysis["performance_rankings"]
                perf_summary["fastest_languages"] = rankings.get(
                    "avg_execution_time",
                    [],
                )[:3]
                perf_summary["memory_efficient_languages"] = rankings.get(
                    "avg_memory_usage",
                    [],
                )[:3]

            # Check for performance concerns
            regression_check = benchmark_results.get("performance_regression_check", {})
            if regression_check.get("regressions_found"):
                perf_summary["performance_grade"] = "C"
                perf_summary["performance_concerns"] = [
                    reg["details"] for reg in regression_check["regressions_found"]
                ]

            # Generate optimization suggestions
            if perf_summary["performance_concerns"]:
                perf_summary["optimization_suggestions"].append(
                    "Review and optimize extractors with performance regressions",
                )

            if comparative_analysis.get("fastest_extractor"):
                perf_summary["optimization_suggestions"].append(
                    f"Consider using {comparative_analysis['fastest_extractor']} extractor patterns for optimization",
                )

        except Exception as e:
            perf_summary["generation_error"] = str(e)

        return perf_summary

    def _count_expected_complex_calls(self, language: str) -> int:
        """Count expected complex calls for a language."""
        complex_indicators = {
            "python": ["async", "await", "lambda", "map", "filter"],
            "javascript": ["async", "await", "=>", "Promise", ".then"],
            "rust": ["async", "await", "::"],
            "go": ["go ", "defer"],
            "c": ["->"],
            "cpp": ["::", "std::", "template"],
            "java": ["new ", "CompletableFuture", ".stream"],
        }

        sample = self.test_samples[language]["complex_calls"]
        indicators = complex_indicators.get(language, [])

        count = 0
        for indicator in indicators:
            count += sample.count(indicator)

        return max(3, count)  # At least 3 expected

    def _get_edge_cases_for_language(self, language: str) -> list[str]:
        """Get edge cases to check for a specific language."""
        edge_cases = {
            "python": [
                "nested_calls",
                "lambda_calls",
                "method_chaining",
                "comprehensions",
            ],
            "javascript": [
                "arrow_functions",
                "template_literals",
                "method_chaining",
                "jsx",
            ],
            "rust": ["macro_calls", "method_chaining", "trait_methods"],
            "go": ["defer_calls", "goroutines", "package_calls"],
            "c": ["function_pointers", "macro_calls", "variadic_calls"],
            "cpp": ["template_calls", "operator_overloading", "stl_algorithms"],
            "java": ["generics", "lambda_expressions", "method_references"],
        }

        return edge_cases.get(language, ["basic_edge_cases"])

    def _check_edge_case_coverage(
        self,
        call_sites: list[CallSite],
        edge_case: str,
    ) -> bool:
        """Check if an edge case is covered by the call sites."""
        # Simple heuristic - in a real implementation, this would be more sophisticated
        edge_case_patterns = {
            "nested_calls": lambda sites: any(
                "(" in site.context.get("text_snippet", "") for site in sites
            ),
            "lambda_calls": lambda sites: any(
                "lambda" in str(site.context) for site in sites
            ),
            "method_chaining": lambda sites: any(
                "." in site.function_name for site in sites
            ),
            "macro_calls": lambda sites: any(
                site.call_type == "macro" for site in sites
            ),
            "jsx": lambda sites: any("<" in str(site.context) for site in sites),
            "template_literals": lambda sites: any(
                "${" in str(site.context) for site in sites
            ),
            "arrow_functions": lambda sites: any(
                "=>" in str(site.context) for site in sites
            ),
            "defer_calls": lambda sites: any(
                site.call_type == "defer" for site in sites
            ),
            "goroutines": lambda sites: any(
                "go " in str(site.context) for site in sites
            ),
            "function_pointers": lambda sites: any(
                "->" in str(site.context) for site in sites
            ),
            "template_calls": lambda sites: any(
                "template" in str(site.context) for site in sites
            ),
            "generics": lambda sites: any("<" in site.function_name for site in sites),
            "basic_edge_cases": lambda sites: len(sites) > 0,
        }

        checker = edge_case_patterns.get(edge_case, lambda sites: False)
        return checker(call_sites)

    def _generate_performance_recommendations(
        self,
        extractor_metrics: dict[str, dict[str, Any]],
    ) -> list[str]:
        """Generate performance optimization recommendations."""
        recommendations = []

        try:
            if not extractor_metrics:
                return ["No performance data available for recommendations"]

            # Find slowest extractor
            slowest = max(
                extractor_metrics.items(),
                key=lambda x: x[1]["avg_execution_time"],
            )
            if slowest[1]["avg_execution_time"] > 0.1:  # 100ms threshold
                recommendations.append(
                    f"Consider optimizing {slowest[0]} extractor - average execution time is high",
                )

            # Find memory-heavy extractors
            memory_heavy = [
                lang
                for lang, metrics in extractor_metrics.items()
                if metrics["avg_memory_usage"] > 100
            ]  # 100MB threshold
            if memory_heavy:
                recommendations.append(
                    f"Review memory usage for extractors: {', '.join(memory_heavy)}",
                )

            # Check for inconsistent performance
            execution_times = [
                metrics["avg_execution_time"] for metrics in extractor_metrics.values()
            ]
            if execution_times and max(execution_times) > 10 * min(execution_times):
                recommendations.append(
                    "Large performance variance detected - consider standardizing extractor implementations",
                )

            if not recommendations:
                recommendations.append("All extractors meet performance expectations")

        except Exception as e:
            recommendations.append(f"Could not generate recommendations: {e!s}")

        return recommendations


class IntegrationTester:
    """Integration testing for the complete extractor system."""

    def __init__(self):
        """Initialize integration tester."""
        self.test_suite = ExtractorTestSuite()
        self.logger = logging.getLogger(__name__)

    def test_complete_workflow(self) -> dict[str, Any]:
        """Test complete extraction workflow."""
        self.logger.info("Testing complete extraction workflow")

        workflow_results = {
            "workflow_stages": [],
            "end_to_end_success": True,
            "total_time": 0.0,
            "data_integrity_check": {},
            "error_recovery_test": {},
        }

        start_time = time.perf_counter()

        try:
            # Stage 1: Initialize all extractors
            stage1 = self._test_extractor_initialization()
            workflow_results["workflow_stages"].append(stage1)

            if not stage1["passed"]:
                workflow_results["end_to_end_success"] = False

            # Stage 2: Test extraction workflow
            stage2 = self._test_extraction_workflow()
            workflow_results["workflow_stages"].append(stage2)

            if not stage2["passed"]:
                workflow_results["end_to_end_success"] = False

            # Stage 3: Test result aggregation
            stage3 = self._test_result_aggregation()
            workflow_results["workflow_stages"].append(stage3)

            if not stage3["passed"]:
                workflow_results["end_to_end_success"] = False

            # Stage 4: Test cleanup and resource management
            stage4 = self._test_cleanup_workflow()
            workflow_results["workflow_stages"].append(stage4)

            if not stage4["passed"]:
                workflow_results["end_to_end_success"] = False

            # Data integrity check
            workflow_results["data_integrity_check"] = self._test_data_integrity()

            # Error recovery test
            workflow_results["error_recovery_test"] = self._test_error_recovery()

        except Exception as e:
            workflow_results["end_to_end_success"] = False
            workflow_results["critical_error"] = str(e)
            self.logger.error(f"Workflow testing failed: {e}", exc_info=True)

        workflow_results["total_time"] = time.perf_counter() - start_time
        return workflow_results

    def validate_accuracy(self) -> dict[str, Any]:
        """Validate accuracy of all extractors."""
        self.logger.info("Validating extractor accuracy")

        accuracy_results = {
            "overall_accuracy": 0.0,
            "language_accuracy": {},
            "accuracy_test_results": [],
            "validation_methodology": {},
            "confidence_intervals": {},
        }

        try:
            total_accuracy = 0.0
            language_count = 0

            # Test accuracy for each language
            for language, extractor in self.test_suite.extractors.items():
                lang_accuracy = self._validate_language_accuracy(language, extractor)
                accuracy_results["language_accuracy"][language] = lang_accuracy

                if lang_accuracy["overall_score"] >= 0:
                    total_accuracy += lang_accuracy["overall_score"]
                    language_count += 1

            if language_count > 0:
                accuracy_results["overall_accuracy"] = total_accuracy / language_count

            # Generate validation methodology report
            accuracy_results["validation_methodology"] = {
                "test_samples_per_language": 3,
                "validation_criteria": [
                    "position_accuracy",
                    "function_name_accuracy",
                    "call_type_accuracy",
                    "context_completeness",
                ],
                "scoring_method": "weighted_average",
            }

        except Exception as e:
            accuracy_results["validation_error"] = str(e)
            self.logger.error(f"Accuracy validation failed: {e}", exc_info=True)

        return accuracy_results

    def test_error_handling(self) -> dict[str, Any]:
        """Test error handling across all extractors."""
        self.logger.info("Testing error handling across extractors")

        error_handling_results = {
            "robustness_score": 0.0,
            "language_error_handling": {},
            "critical_failures": [],
            "recovery_mechanisms": {},
            "error_categories_tested": [],
        }

        try:
            # Error scenarios to test
            error_scenarios = [
                ("syntax_errors", "def invalid_syntax {"),
                (
                    "encoding_errors",
                    b"\xff\xfe invalid encoding".decode("utf-8", errors="ignore"),
                ),
                ("memory_stress", "x" * 1000000),
                ("nested_structures", "(" * 1000 + ")" * 1000),
                ("unicode_mixed", 'function ಠ_ಠ() { console.log("test"); }'),
                ("empty_input", ""),
                ("null_characters", "test\x00function"),
            ]

            error_handling_results["error_categories_tested"] = [
                scenario[0] for scenario in error_scenarios
            ]

            total_robustness = 0.0
            extractor_count = 0

            for language, extractor in self.test_suite.extractors.items():
                lang_error_results = {
                    "scenarios_tested": len(error_scenarios),
                    "scenarios_passed": 0,
                    "crashes": 0,
                    "graceful_failures": 0,
                    "error_details": [],
                }

                for scenario_name, test_input in error_scenarios:
                    try:
                        result = extractor.extract_calls(test_input)

                        if isinstance(result, ExtractionResult):
                            lang_error_results["scenarios_passed"] += 1
                            if result.errors:
                                lang_error_results["graceful_failures"] += 1
                        else:
                            lang_error_results["error_details"].append(
                                f"Invalid result type for {scenario_name}",
                            )

                    except Exception as e:
                        lang_error_results["crashes"] += 1
                        lang_error_results["error_details"].append(
                            f"Crash in {scenario_name}: {e!s}",
                        )

                        if scenario_name in ["syntax_errors", "encoding_errors"]:
                            # These crashes are critical
                            error_handling_results["critical_failures"].append(
                                {
                                    "language": language,
                                    "scenario": scenario_name,
                                    "error": str(e),
                                },
                            )

                # Calculate robustness score for this language
                if lang_error_results["scenarios_tested"] > 0:
                    robustness = (
                        lang_error_results["scenarios_passed"]
                        - lang_error_results["crashes"]
                    ) / lang_error_results["scenarios_tested"]
                    lang_error_results["robustness_score"] = max(0.0, robustness)
                    total_robustness += lang_error_results["robustness_score"]
                    extractor_count += 1

                error_handling_results["language_error_handling"][
                    language
                ] = lang_error_results

            # Calculate overall robustness
            if extractor_count > 0:
                error_handling_results["robustness_score"] = (
                    total_robustness / extractor_count
                )

            # Test recovery mechanisms
            error_handling_results["recovery_mechanisms"] = (
                self._test_recovery_mechanisms()
            )

        except Exception as e:
            error_handling_results["testing_error"] = str(e)
            self.logger.error(f"Error handling testing failed: {e}", exc_info=True)

        return error_handling_results

    def test_performance_integration(self) -> dict[str, Any]:
        """Test performance integration."""
        self.logger.info("Testing performance integration")

        performance_results = {
            "concurrent_processing": {},
            "memory_efficiency": {},
            "scalability_analysis": {},
            "performance_degradation_check": {},
            "resource_utilization": {},
        }

        try:
            # Test concurrent processing
            performance_results["concurrent_processing"] = (
                self._test_concurrent_processing()
            )

            # Test memory efficiency
            performance_results["memory_efficiency"] = self._test_memory_efficiency()

            # Test scalability
            performance_results["scalability_analysis"] = self._test_scalability()

            # Check for performance degradation
            performance_results["performance_degradation_check"] = (
                self._test_performance_degradation()
            )

            # Monitor resource utilization
            performance_results["resource_utilization"] = (
                self._test_resource_utilization()
            )

        except Exception as e:
            performance_results["testing_error"] = str(e)
            self.logger.error(
                f"Performance integration testing failed: {e}",
                exc_info=True,
            )

        return performance_results

    def _test_extractor_initialization(self) -> dict[str, Any]:
        """Test extractor initialization workflow stage."""
        stage_result = {
            "stage_name": "extractor_initialization",
            "passed": True,
            "extractors_initialized": 0,
            "initialization_errors": [],
            "performance_metrics": {},
        }

        start_time = time.perf_counter()

        for language, extractor in self.test_suite.extractors.items():
            try:
                # Test basic properties
                if not hasattr(extractor, "language"):
                    stage_result["initialization_errors"].append(
                        f"{language}: missing language attribute",
                    )
                    stage_result["passed"] = False
                    continue

                if extractor.language.lower() != language:
                    stage_result["initialization_errors"].append(
                        f"{language}: language mismatch",
                    )
                    stage_result["passed"] = False
                    continue

                # Test required methods
                required_methods = ["extract_calls", "validate_source"]
                for method in required_methods:
                    if not hasattr(extractor, method) or not callable(
                        getattr(extractor, method),
                    ):
                        stage_result["initialization_errors"].append(
                            f"{language}: missing {method} method",
                        )
                        stage_result["passed"] = False
                        continue

                stage_result["extractors_initialized"] += 1

            except Exception as e:
                stage_result["initialization_errors"].append(f"{language}: {e!s}")
                stage_result["passed"] = False

        stage_result["performance_metrics"]["initialization_time"] = (
            time.perf_counter() - start_time
        )
        return stage_result

    def _test_extraction_workflow(self) -> dict[str, Any]:
        """Test extraction workflow stage."""
        stage_result = {
            "stage_name": "extraction_workflow",
            "passed": True,
            "successful_extractions": 0,
            "extraction_errors": [],
            "performance_metrics": {},
        }

        start_time = time.perf_counter()

        # Simple test code that should work in most languages
        test_code = "function test() { call1(); return call2(); }"

        for language, extractor in self.test_suite.extractors.items():
            try:
                result = extractor.extract_calls(test_code)

                if isinstance(result, ExtractionResult):
                    stage_result["successful_extractions"] += 1

                    # Basic validation
                    if not hasattr(result, "call_sites") or not isinstance(
                        result.call_sites,
                        list,
                    ):
                        stage_result["extraction_errors"].append(
                            f"{language}: invalid call_sites structure",
                        )
                        stage_result["passed"] = False
                else:
                    stage_result["extraction_errors"].append(
                        f"{language}: invalid result type",
                    )
                    stage_result["passed"] = False

            except Exception as e:
                stage_result["extraction_errors"].append(f"{language}: {e!s}")
                stage_result["passed"] = False

        stage_result["performance_metrics"]["extraction_time"] = (
            time.perf_counter() - start_time
        )
        return stage_result

    def _test_result_aggregation(self) -> dict[str, Any]:
        """Test result aggregation workflow stage."""
        stage_result = {
            "stage_name": "result_aggregation",
            "passed": True,
            "aggregation_tests": [],
            "performance_metrics": {},
        }

        start_time = time.perf_counter()

        try:
            # Test ExtractionUtils.merge_extraction_results
            test_results = []

            for language in list(self.test_suite.extractors.keys())[
                :3
            ]:  # Test with 3 languages
                extractor = self.test_suite.extractors[language]
                result = extractor.extract_calls("test_function();")
                test_results.append(result)

            # Merge results
            merged = ExtractionUtils.merge_extraction_results(test_results)

            if isinstance(merged, ExtractionResult):
                stage_result["aggregation_tests"].append(
                    {"test": "merge_results", "passed": True},
                )

                # Validate merged structure
                expected_calls = sum(len(r.call_sites) for r in test_results)
                actual_calls = len(merged.call_sites)

                if actual_calls != expected_calls:
                    stage_result["aggregation_tests"].append(
                        {
                            "test": "call_count_consistency",
                            "passed": False,
                            "expected": expected_calls,
                            "actual": actual_calls,
                        },
                    )
                    stage_result["passed"] = False
                else:
                    stage_result["aggregation_tests"].append(
                        {"test": "call_count_consistency", "passed": True},
                    )
            else:
                stage_result["aggregation_tests"].append(
                    {"test": "merge_results", "passed": False},
                )
                stage_result["passed"] = False

        except Exception as e:
            stage_result["aggregation_tests"].append(
                {"test": "merge_results", "passed": False, "error": str(e)},
            )
            stage_result["passed"] = False

        stage_result["performance_metrics"]["aggregation_time"] = (
            time.perf_counter() - start_time
        )
        return stage_result

    def _test_cleanup_workflow(self) -> dict[str, Any]:
        """Test cleanup workflow stage."""
        stage_result = {
            "stage_name": "cleanup_workflow",
            "passed": True,
            "cleanup_tests": [],
            "performance_metrics": {},
        }

        start_time = time.perf_counter()

        for language, extractor in self.test_suite.extractors.items():
            try:
                # Test cleanup method if available
                if hasattr(extractor, "cleanup") and callable(extractor.cleanup):
                    extractor.cleanup()
                    stage_result["cleanup_tests"].append(
                        {"language": language, "cleanup_called": True},
                    )
                else:
                    stage_result["cleanup_tests"].append(
                        {"language": language, "cleanup_called": False},
                    )

            except Exception as e:
                stage_result["cleanup_tests"].append(
                    {"language": language, "cleanup_called": False, "error": str(e)},
                )
                stage_result["passed"] = False

        stage_result["performance_metrics"]["cleanup_time"] = (
            time.perf_counter() - start_time
        )
        return stage_result

    def _test_data_integrity(self) -> dict[str, Any]:
        """Test data integrity throughout the workflow."""
        integrity_test = {
            "position_accuracy": {},
            "function_name_accuracy": {},
            "call_type_consistency": {},
            "context_preservation": {},
        }

        # Test with known input/output pairs
        test_input = """
def test_function():
    print("hello")
    result = calculate(10, 20)
    obj.method_call()
    return result
"""

        expected_patterns = [
            {"name": "print", "type": "function"},
            {"name": "calculate", "type": "function"},
            {"name": "method_call", "type": "method"},
        ]

        # Test with Python extractor (most reliable)
        if "python" in self.test_suite.extractors:
            try:
                result = self.test_suite.extractors["python"].extract_calls(test_input)

                # Check position accuracy
                for call_site in result.call_sites:
                    if call_site.line_number > 0 and call_site.column_number >= 0:
                        integrity_test["position_accuracy"]["valid_positions"] = (
                            integrity_test["position_accuracy"].get(
                                "valid_positions",
                                0,
                            )
                            + 1
                        )
                    else:
                        integrity_test["position_accuracy"]["invalid_positions"] = (
                            integrity_test["position_accuracy"].get(
                                "invalid_positions",
                                0,
                            )
                            + 1
                        )

                # Check function names
                found_names = [cs.function_name for cs in result.call_sites]
                for expected in expected_patterns:
                    if expected["name"] in found_names or any(
                        expected["name"] in name for name in found_names
                    ):
                        integrity_test["function_name_accuracy"]["correct_names"] = (
                            integrity_test["function_name_accuracy"].get(
                                "correct_names",
                                0,
                            )
                            + 1
                        )
                    else:
                        integrity_test["function_name_accuracy"]["missed_names"] = (
                            integrity_test["function_name_accuracy"].get(
                                "missed_names",
                                0,
                            )
                            + 1
                        )

            except Exception as e:
                integrity_test["test_error"] = str(e)

        return integrity_test

    def _test_error_recovery(self) -> dict[str, Any]:
        """Test error recovery mechanisms."""
        recovery_test = {
            "graceful_degradation": True,
            "partial_success_handling": {},
            "error_propagation": {},
        }

        # Test with mixed valid/invalid code
        mixed_code = """
def valid_function():
    print("this works")

def invalid syntax here {
    broken code
}

def another_valid():
    call_function()
"""

        for language, extractor in self.test_suite.extractors.items():
            try:
                result = extractor.extract_calls(mixed_code)

                recovery_test["partial_success_handling"][language] = {
                    "returned_result": isinstance(result, ExtractionResult),
                    "has_call_sites": (
                        len(result.call_sites) > 0
                        if isinstance(result, ExtractionResult)
                        else False
                    ),
                    "reported_errors": (
                        len(result.errors) > 0
                        if isinstance(result, ExtractionResult)
                        else False
                    ),
                }

            except Exception as e:
                recovery_test["partial_success_handling"][language] = {
                    "returned_result": False,
                    "exception": str(e),
                }
                recovery_test["graceful_degradation"] = False

        return recovery_test

    def _validate_language_accuracy(
        self,
        language: str,
        extractor: BaseExtractor,
    ) -> dict[str, Any]:
        """Validate accuracy for a specific language extractor."""
        accuracy_result = {
            "overall_score": 0.0,
            "position_accuracy": 0.0,
            "name_accuracy": 0.0,
            "type_accuracy": 0.0,
            "context_completeness": 0.0,
            "test_details": [],
        }

        try:
            # Use known test cases with expected results
            test_cases = [
                {
                    "code": self.test_suite.test_samples[language]["basic_calls"],
                    "expected_min_calls": 3,
                    "expected_function_names": [
                        "print",
                        "console.log",
                        "println!",
                        "printf",
                        "fmt.Println",
                        "System.out.println",
                    ].copy(),
                },
            ]

            total_score = 0.0
            test_count = 0

            for test_case in test_cases:
                try:
                    result = extractor.extract_calls(test_case["code"])
                    test_detail = {
                        "calls_found": len(result.call_sites),
                        "expected_min": test_case["expected_min_calls"],
                        "accuracy_scores": {},
                    }

                    # Position accuracy (validate against source)
                    position_correct = 0
                    for call_site in result.call_sites:
                        validation_errors = ExtractionUtils.validate_call_site(
                            call_site,
                            test_case["code"],
                        )
                        if not validation_errors:
                            position_correct += 1

                    if result.call_sites:
                        test_detail["accuracy_scores"]["position"] = (
                            position_correct / len(result.call_sites)
                        )
                    else:
                        test_detail["accuracy_scores"]["position"] = 0.0

                    # Name accuracy (check for expected names)
                    found_names = [cs.function_name.lower() for cs in result.call_sites]
                    expected_names = test_case["expected_function_names"]
                    name_matches = sum(
                        1
                        for exp in expected_names
                        if any(exp.lower() in found.lower() for found in found_names)
                    )

                    test_detail["accuracy_scores"]["name"] = min(
                        1.0,
                        name_matches / max(1, len(expected_names)),
                    )

                    # Type accuracy (basic check for function vs method)
                    type_correct = sum(
                        1
                        for cs in result.call_sites
                        if cs.call_type in ["function", "method", "constructor"]
                    )
                    if result.call_sites:
                        test_detail["accuracy_scores"]["type"] = type_correct / len(
                            result.call_sites,
                        )
                    else:
                        test_detail["accuracy_scores"]["type"] = 0.0

                    # Context completeness
                    context_complete = sum(
                        1
                        for cs in result.call_sites
                        if cs.context and len(cs.context) > 0
                    )
                    if result.call_sites:
                        test_detail["accuracy_scores"]["context"] = (
                            context_complete / len(result.call_sites)
                        )
                    else:
                        test_detail["accuracy_scores"]["context"] = 0.0

                    # Calculate overall score for this test
                    scores = list(test_detail["accuracy_scores"].values())
                    test_score = statistics.mean(scores) if scores else 0.0
                    test_detail["overall_score"] = test_score

                    total_score += test_score
                    test_count += 1

                    accuracy_result["test_details"].append(test_detail)

                except Exception as e:
                    accuracy_result["test_details"].append(
                        {"error": str(e), "overall_score": 0.0},
                    )

            # Calculate overall accuracy
            if test_count > 0:
                accuracy_result["overall_score"] = total_score / test_count

                # Calculate component scores
                if accuracy_result["test_details"]:
                    position_scores = [
                        t.get("accuracy_scores", {}).get("position", 0)
                        for t in accuracy_result["test_details"]
                    ]
                    name_scores = [
                        t.get("accuracy_scores", {}).get("name", 0)
                        for t in accuracy_result["test_details"]
                    ]
                    type_scores = [
                        t.get("accuracy_scores", {}).get("type", 0)
                        for t in accuracy_result["test_details"]
                    ]
                    context_scores = [
                        t.get("accuracy_scores", {}).get("context", 0)
                        for t in accuracy_result["test_details"]
                    ]

                    accuracy_result["position_accuracy"] = (
                        statistics.mean(position_scores) if position_scores else 0.0
                    )
                    accuracy_result["name_accuracy"] = (
                        statistics.mean(name_scores) if name_scores else 0.0
                    )
                    accuracy_result["type_accuracy"] = (
                        statistics.mean(type_scores) if type_scores else 0.0
                    )
                    accuracy_result["context_completeness"] = (
                        statistics.mean(context_scores) if context_scores else 0.0
                    )

        except Exception as e:
            accuracy_result["validation_error"] = str(e)

        return accuracy_result

    def _test_recovery_mechanisms(self) -> dict[str, Any]:
        """Test recovery mechanisms in error scenarios."""
        recovery_test = {
            "fallback_strategies": {},
            "partial_processing": {},
            "error_isolation": {},
        }

        # Test each extractor's recovery capabilities
        for language, extractor in self.test_suite.extractors.items():
            lang_recovery = {
                "handles_partial_syntax_errors": False,
                "continues_after_errors": False,
                "isolates_error_regions": False,
            }

            # Test partial syntax errors
            try:
                partial_error_code = """
function valid1() { call1(); }
function invalid syntax {
function valid2() { call2(); }
"""
                result = extractor.extract_calls(partial_error_code)
                if isinstance(result, ExtractionResult) and result.call_sites:
                    lang_recovery["handles_partial_syntax_errors"] = True

                    # Check if it found calls despite syntax errors
                    if len(result.call_sites) > 0:
                        lang_recovery["continues_after_errors"] = True

            except Exception:
                pass

            recovery_test["fallback_strategies"][language] = lang_recovery

        return recovery_test

    def _test_concurrent_processing(self) -> dict[str, Any]:
        """Test concurrent processing capabilities."""
        concurrent_test = {
            "thread_safety": {},
            "performance_scaling": {},
            "resource_contention": {},
        }

        try:
            import threading

            # Test thread safety
            test_code = "function test() { call1(); call2(); }"
            results = {}
            errors = {}

            def extract_in_thread(language, extractor, thread_id):
                try:
                    result = extractor.extract_calls(test_code)
                    results[f"{language}_{thread_id}"] = result
                except Exception as e:
                    errors[f"{language}_{thread_id}"] = str(e)

            threads = []
            for language, extractor in list(self.test_suite.extractors.items())[
                :3
            ]:  # Test first 3
                for i in range(3):  # 3 threads per extractor
                    thread = threading.Thread(
                        target=extract_in_thread,
                        args=(language, extractor, i),
                    )
                    threads.append(thread)
                    thread.start()

            for thread in threads:
                thread.join(timeout=10)  # 10 second timeout

            # Analyze results
            for language in list(self.test_suite.extractors.keys())[:3]:
                lang_results = [results.get(f"{language}_{i}") for i in range(3)]
                lang_errors = [errors.get(f"{language}_{i}") for i in range(3)]

                concurrent_test["thread_safety"][language] = {
                    "successful_threads": sum(1 for r in lang_results if r is not None),
                    "failed_threads": sum(1 for e in lang_errors if e is not None),
                    "consistent_results": len(
                        {len(r.call_sites) for r in lang_results if r},
                    )
                    <= 1,
                }

        except ImportError:
            concurrent_test["thread_safety_error"] = "Threading not available"
        except Exception as e:
            concurrent_test["concurrent_test_error"] = str(e)

        return concurrent_test

    def _test_memory_efficiency(self) -> dict[str, Any]:
        """Test memory efficiency of extractors."""
        memory_test = {"baseline_memory": {}, "memory_growth": {}, "memory_cleanup": {}}

        try:
            import gc
            import os

            import psutil

            process = psutil.Process(os.getpid())

            for language, extractor in self.test_suite.extractors.items():
                # Measure baseline memory
                gc.collect()
                baseline_memory = process.memory_info().rss / 1024 / 1024  # MB

                # Process increasingly larger code samples
                small_code = self.test_suite.test_samples[language]["basic_calls"]
                large_code = small_code * 100  # 100x larger

                # Process large code
                start_memory = process.memory_info().rss / 1024 / 1024
                result = extractor.extract_calls(large_code)
                peak_memory = process.memory_info().rss / 1024 / 1024

                # Force cleanup
                del result
                gc.collect()
                cleanup_memory = process.memory_info().rss / 1024 / 1024

                memory_test["baseline_memory"][language] = baseline_memory
                memory_test["memory_growth"][language] = peak_memory - start_memory
                memory_test["memory_cleanup"][language] = peak_memory - cleanup_memory

        except ImportError:
            memory_test["memory_monitoring_error"] = "psutil not available"
        except Exception as e:
            memory_test["memory_test_error"] = str(e)

        return memory_test

    def _test_scalability(self) -> dict[str, Any]:
        """Test scalability of extractors."""
        scalability_test = {
            "processing_time_scaling": {},
            "memory_scaling": {},
            "accuracy_degradation": {},
        }

        try:
            # Test with different file sizes
            size_multipliers = [1, 10, 50]  # 1x, 10x, 50x original size

            for language, extractor in list(self.test_suite.extractors.items())[
                :3
            ]:  # Test first 3
                base_code = self.test_suite.test_samples[language]["basic_calls"]
                scaling_results = []

                for multiplier in size_multipliers:
                    test_code = base_code * multiplier

                    start_time = time.perf_counter()
                    result = extractor.extract_calls(test_code)
                    processing_time = time.perf_counter() - start_time

                    scaling_results.append(
                        {
                            "size_multiplier": multiplier,
                            "code_size_kb": len(test_code.encode("utf-8")) / 1024,
                            "processing_time": processing_time,
                            "calls_found": len(result.call_sites),
                            "time_per_kb": processing_time
                            / (len(test_code.encode("utf-8")) / 1024),
                        },
                    )

                scalability_test["processing_time_scaling"][language] = scaling_results

                # Check if scaling is roughly linear
                times = [r["time_per_kb"] for r in scaling_results]
                if len(times) >= 2:
                    scaling_factor = (
                        max(times) / min(times) if min(times) > 0 else float("inf")
                    )
                    scalability_test["processing_time_scaling"][language].append(
                        {
                            "scaling_factor": scaling_factor,
                            "is_linear": scaling_factor
                            < 3.0,  # Within 3x is considered reasonable
                        },
                    )

        except Exception as e:
            scalability_test["scalability_test_error"] = str(e)

        return scalability_test

    def _test_performance_degradation(self) -> dict[str, Any]:
        """Test for performance degradation over time."""
        degradation_test = {
            "repeated_processing": {},
            "memory_leaks": {},
            "performance_consistency": {},
        }

        try:
            # Test repeated processing
            test_iterations = 20
            test_code = "function test() { call1(); call2(); call3(); }"

            for language, extractor in list(self.test_suite.extractors.items())[
                :2
            ]:  # Test first 2
                processing_times = []
                memory_usage = []

                try:
                    import os

                    import psutil

                    process = psutil.Process(os.getpid())
                    memory_available = True
                except ImportError:
                    memory_available = False

                for i in range(test_iterations):
                    if memory_available:
                        pre_memory = process.memory_info().rss / 1024 / 1024

                    start_time = time.perf_counter()
                    result = extractor.extract_calls(test_code)
                    processing_time = time.perf_counter() - start_time

                    processing_times.append(processing_time)

                    if memory_available:
                        post_memory = process.memory_info().rss / 1024 / 1024
                        memory_usage.append(post_memory)

                # Analyze degradation
                if processing_times:
                    first_half = processing_times[: len(processing_times) // 2]
                    second_half = processing_times[len(processing_times) // 2 :]

                    first_avg = statistics.mean(first_half)
                    second_avg = statistics.mean(second_half)

                    degradation_test["repeated_processing"][language] = {
                        "first_half_avg": first_avg,
                        "second_half_avg": second_avg,
                        "degradation_ratio": (
                            second_avg / first_avg if first_avg > 0 else 1.0
                        ),
                        "total_iterations": test_iterations,
                    }

                if memory_usage and memory_available:
                    memory_trend = memory_usage[-1] - memory_usage[0]
                    degradation_test["memory_leaks"][language] = {
                        "initial_memory_mb": memory_usage[0],
                        "final_memory_mb": memory_usage[-1],
                        "memory_growth_mb": memory_trend,
                        "potential_leak": memory_trend > 10,  # More than 10MB growth
                    }

        except Exception as e:
            degradation_test["degradation_test_error"] = str(e)

        return degradation_test

    def _test_resource_utilization(self) -> dict[str, Any]:
        """Test resource utilization patterns."""
        resource_test = {
            "cpu_utilization": {},
            "memory_patterns": {},
            "io_efficiency": {},
        }

        try:
            # This would typically require more sophisticated profiling
            # For now, we'll do basic measurements
            test_code = """
function complexFunction() {
    for (let i = 0; i < 1000; i++) {
        processItem(i);
        validateItem(items[i]);
        transformItem(results[i]);
    }
    return finalizeResults();
}
"""

            for language, extractor in list(self.test_suite.extractors.items())[:2]:
                start_time = time.perf_counter()
                result = extractor.extract_calls(test_code)
                end_time = time.perf_counter()

                resource_test["cpu_utilization"][language] = {
                    "processing_time": end_time - start_time,
                    "calls_per_second": (
                        len(result.call_sites) / (end_time - start_time)
                        if end_time > start_time
                        else 0
                    ),
                    "efficiency_score": len(result.call_sites)
                    / max(0.001, end_time - start_time),
                }

        except Exception as e:
            resource_test["resource_test_error"] = str(e)

        return resource_test


def run_complete_extractor_test_suite() -> dict[str, Any]:
    """Run complete extractor test suite."""
    logger = logging.getLogger(__name__)
    logger.info("Starting complete extractor test suite")

    # Initialize test components
    test_suite = ExtractorTestSuite()
    integration_tester = IntegrationTester()

    # Overall results structure
    complete_results = {
        "test_suite_version": "1.0.0",
        "execution_timestamp": datetime.now().isoformat(),
        "overall_status": "RUNNING",
        "component_results": {},
        "summary": {},
        "recommendations": [],
        "total_execution_time": 0.0,
    }

    start_time = time.perf_counter()

    try:
        logger.info("Running comprehensive test suite")

        # Run comprehensive test suite
        suite_results = test_suite.run_all_tests()
        complete_results["component_results"]["test_suite"] = suite_results

        # Run integration testing
        logger.info("Running integration workflow tests")
        workflow_results = integration_tester.test_complete_workflow()
        complete_results["component_results"]["workflow_tests"] = workflow_results

        # Run accuracy validation
        logger.info("Running accuracy validation")
        accuracy_results = integration_tester.validate_accuracy()
        complete_results["component_results"]["accuracy_validation"] = accuracy_results

        # Run error handling tests
        logger.info("Running error handling tests")
        error_handling_results = integration_tester.test_error_handling()
        complete_results["component_results"]["error_handling"] = error_handling_results

        # Run performance integration tests
        logger.info("Running performance integration tests")
        performance_results = integration_tester.test_performance_integration()
        complete_results["component_results"][
            "performance_integration"
        ] = performance_results

        # Generate overall summary
        complete_results["summary"] = _generate_overall_summary(
            complete_results["component_results"],
        )

        # Generate recommendations
        complete_results["recommendations"] = _generate_overall_recommendations(
            complete_results["component_results"],
        )

        # Determine overall status
        if all(
            component.get("overall_passed", True)
            for component in complete_results["component_results"].values()
            if isinstance(component, dict)
        ):
            complete_results["overall_status"] = "PASSED"
        else:
            complete_results["overall_status"] = "FAILED"

    except Exception as e:
        complete_results["overall_status"] = "ERROR"
        complete_results["critical_error"] = str(e)
        complete_results["error_traceback"] = traceback.format_exc()
        logger.error(f"Complete test suite failed with error: {e}", exc_info=True)

    complete_results["total_execution_time"] = time.perf_counter() - start_time

    logger.info(
        f"Complete test suite finished with status: {complete_results['overall_status']}",
    )
    logger.info(
        f"Total execution time: {complete_results['total_execution_time']:.2f}s",
    )

    return complete_results


def _generate_overall_summary(component_results: dict[str, Any]) -> dict[str, Any]:
    """Generate overall summary from component results."""
    summary = {
        "total_tests_run": 0,
        "total_tests_passed": 0,
        "overall_success_rate": 0.0,
        "component_status": {},
        "critical_issues": [],
        "performance_summary": {},
        "accuracy_summary": {},
    }

    try:
        # Aggregate test counts
        for component_name, results in component_results.items():
            if isinstance(results, dict):
                component_passed = results.get("overall_passed", False) or results.get(
                    "end_to_end_success",
                    False,
                )
                summary["component_status"][component_name] = (
                    "PASSED" if component_passed else "FAILED"
                )

                # Count tests if available
                if "total_tests" in results:
                    summary["total_tests_run"] += results["total_tests"]
                    summary["total_tests_passed"] += results.get("passed_tests", 0)

        # Calculate overall success rate
        if summary["total_tests_run"] > 0:
            summary["overall_success_rate"] = (
                summary["total_tests_passed"] / summary["total_tests_run"]
            )

        # Identify critical issues
        failed_components = [
            name
            for name, status in summary["component_status"].items()
            if status == "FAILED"
        ]
        if failed_components:
            summary["critical_issues"].extend(
                [f"{component} failed" for component in failed_components],
            )

        # Performance summary
        if (
            "test_suite" in component_results
            and "performance_summary" in component_results["test_suite"]
        ):
            summary["performance_summary"] = component_results["test_suite"][
                "performance_summary"
            ]

        # Accuracy summary
        if "accuracy_validation" in component_results:
            accuracy_data = component_results["accuracy_validation"]
            summary["accuracy_summary"] = {
                "overall_accuracy": accuracy_data.get("overall_accuracy", 0.0),
                "languages_tested": len(accuracy_data.get("language_accuracy", {})),
            }

    except Exception as e:
        summary["summary_generation_error"] = str(e)

    return summary


def _generate_overall_recommendations(component_results: dict[str, Any]) -> list[str]:
    """Generate overall recommendations from component results."""
    recommendations = []

    try:
        # Check test suite results
        if "test_suite" in component_results:
            suite_results = component_results["test_suite"]
            if not suite_results.get("overall_passed", True):
                recommendations.append(
                    "Review and fix failing language extractors before production deployment",
                )

            if (
                "summary" in suite_results
                and suite_results["summary"].get("overall_success_rate", 1.0) < 0.8
            ):
                recommendations.append(
                    "Overall test success rate is below 80% - comprehensive review needed",
                )

        # Check accuracy results
        if "accuracy_validation" in component_results:
            accuracy_results = component_results["accuracy_validation"]
            if accuracy_results.get("overall_accuracy", 1.0) < 0.7:
                recommendations.append(
                    "Overall accuracy is below 70% - improve extraction algorithms",
                )

            # Check individual language accuracy
            lang_accuracy = accuracy_results.get("language_accuracy", {})
            low_accuracy_langs = [
                lang
                for lang, data in lang_accuracy.items()
                if isinstance(data, dict) and data.get("overall_score", 1.0) < 0.6
            ]

            if low_accuracy_langs:
                recommendations.append(
                    f"Low accuracy languages need attention: {', '.join(low_accuracy_langs)}",
                )

        # Check error handling
        if "error_handling" in component_results:
            error_results = component_results["error_handling"]
            if error_results.get("robustness_score", 1.0) < 0.8:
                recommendations.append(
                    "Improve error handling and robustness across extractors",
                )

            critical_failures = error_results.get("critical_failures", [])
            if critical_failures:
                recommendations.append(
                    f"Address critical error handling failures: {len(critical_failures)} found",
                )

        # Check performance
        if "performance_integration" in component_results:
            perf_results = component_results["performance_integration"]

            # Check for memory leaks
            memory_efficiency = perf_results.get("memory_efficiency", {})
            if "memory_cleanup" in memory_efficiency:
                poor_cleanup = [
                    lang
                    for lang, cleanup in memory_efficiency["memory_cleanup"].items()
                    if isinstance(cleanup, (int, float)) and cleanup > 50
                ]  # >50MB not cleaned up
                if poor_cleanup:
                    recommendations.append(
                        f"Memory cleanup issues detected in: {', '.join(poor_cleanup)}",
                    )

        # General recommendations
        if not recommendations:
            recommendations.append(
                "All tests passed - extractors are ready for production deployment",
            )
        else:
            recommendations.append(
                "Complete all recommended fixes before production deployment",
            )

        # Always recommend monitoring
        recommendations.append(
            "Implement monitoring and alerting for extractor performance in production",
        )

    except Exception as e:
        recommendations.append(f"Error generating recommendations: {e!s}")

    return recommendations
