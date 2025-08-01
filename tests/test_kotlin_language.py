"""Test Kotlin language support."""
import pytest

from chunker import chunk_text
from chunker.languages import language_config_registry


class TestKotlinLanguage:
    """Test Kotlin language chunking."""

    @staticmethod
    def test_kotlin_basic_chunking():
        """Test basic Kotlin chunking."""
        code = """
package com.example.app

import kotlinx.coroutines.*

data class User(val id: Int, val name: String, val email: String?)

class UserService(private val repository: UserRepository) {
    suspend fun getUser(id: Int): User? {
        return withContext(Dispatchers.IO) {
            repository.findById(id)
        }
    }

    suspend fun createUser(name: String, email: String?): User {
        val user = User(
            id = generateId(),
            name = name,
            email = email
        )
        return repository.save(user)
    }

    private fun generateId(): Int {
        return (1..1000000).random()
    }
}

fun main() {
    runBlocking {
        val service = UserService(InMemoryUserRepository())
        val user = service.createUser("John Doe", "john@example.com")
        println("Created user: $user")
    }
}
"""
        chunks = chunk_text(code, language="kotlin")
        assert len(chunks) >= 4
        chunk_contents = [chunk.content for chunk in chunks]
        assert any("data class User" in c for c in chunk_contents)
        assert any("class UserService" in c for c in chunk_contents)
        assert any("fun main" in c for c in chunk_contents)

    @staticmethod
    def test_kotlin_interfaces_sealed():
        """Test Kotlin interfaces and sealed classes."""
        code = """
interface Repository<T> {
    suspend fun findById(id: Int): T?
    suspend fun save(entity: T): T
    suspend fun delete(id: Int)
}

sealed class Result<out T> {
    data class Success<T>(val data: T) : Result<T>()
    data class Error(val exception: Exception) : Result<Nothing>()
    object Loading : Result<Nothing>()

    inline fun <R> map(transform: (T) -> R): Result<R> = when (this) {
        is Success -> Success(transform(data))
        is Error -> Error(exception)
        is Loading -> Loading
    }
}

abstract class BaseViewModel : ViewModel() {
    protected val _state = MutableStateFlow<ViewState>(ViewState.Initial)
    val state: StateFlow<ViewState> = _state.asStateFlow()

    abstract fun onEvent(event: ViewEvent)
}
"""
        chunks = chunk_text(code, language="kotlin")
        assert len(chunks) >= 3

    @staticmethod
    def test_kotlin_extension_functions():
        """Test Kotlin extension functions and properties."""
        code = """
fun String.isEmail(): Boolean {
    return this.matches(Regex("[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}"))
}

val String.wordCount: Int
    get() = this.trim().split("\\\\s+".toRegex()).size

inline fun <T> List<T>.forEachIndexedReversed(action: (index: Int, T) -> Unit) {
    for (index in lastIndex downTo 0) {
        action(index, this[index])
    }
}

object StringExtensions {
    fun String.capitalize(): String {
        return this.replaceFirstChar {
            if (it.isLowerCase()) it.titlecase() else it.toString()
        }
    }
}

class ValidationExtensions {
    companion object {
        fun String.isPhoneNumber(): Boolean {
            return this.matches(Regex("\\\\d{10}"))
        }
    }
}
"""
        chunks = chunk_text(code, language="kotlin")
        assert len(chunks) >= 5

    @staticmethod
    def test_kotlin_coroutines():
        """Test Kotlin coroutines and flow."""
        code = """
import kotlinx.coroutines.flow.*

class DataRepository {
    private val refreshTrigger = MutableSharedFlow<Unit>()

    val data: Flow<List<Item>> = refreshTrigger
        .onStart { emit(Unit) }
        .flatMapLatest {
            flow {
                emit(fetchFromNetwork())
            }.catch { e ->
                emit(fetchFromCache())
            }
        }
        .shareIn(
            scope = CoroutineScope(Dispatchers.IO),
            started = SharingStarted.WhileSubscribed(5000),
            replay = 1
        )

    suspend fun refresh() {
        refreshTrigger.emit(Unit)
    }

    private suspend fun fetchFromNetwork(): List<Item> = withContext(Dispatchers.IO) {
        delay(1000)
        api.getItems()
    }

    private suspend fun fetchFromCache(): List<Item> {
        return database.itemDao().getAll()
    }
}
"""
        chunks = chunk_text(code, language="kotlin")
        assert len(chunks) >= 1

    @staticmethod
    def test_kotlin_dsl_builders():
        """Test Kotlin DSL and builder patterns."""
        code = """
class Html {
    private val children = mutableListOf<Element>()

    fun head(init: Head.() -> Unit) {
        val head = Head()
        head.init()
        children.add(head)
    }

    fun body(init: Body.() -> Unit) {
        val body = Body()
        body.init()
        children.add(body)
    }
}

@DslMarker
annotation class HtmlDsl

@HtmlDsl
class Head : Element() {
    fun title(text: String) {
        children.add(Title(text))
    }
}

fun html(init: Html.() -> Unit): Html {
    val html = Html()
    html.init()
    return html
}

inline fun <reified T : Any> buildConfig(builder: ConfigBuilder<T>.() -> Unit): T {
    return ConfigBuilder(T::class).apply(builder).build()
}
"""
        chunks = chunk_text(code, language="kotlin")
        assert len(chunks) >= 4

    @staticmethod
    def test_kotlin_companion_object():
        """Test Kotlin companion objects."""
        code = """
class Logger private constructor(private val tag: String) {
    companion object {
        @JvmStatic
        private val instances = mutableMapOf<String, Logger>()

        @JvmStatic
        fun getInstance(tag: String): Logger {
            return instances.getOrPut(tag) { Logger(tag) }
        }

        const val DEFAULT_TAG = "App"
    }

    fun log(message: String) {
        println("[$tag] $message")
    }

    inline fun debug(lazyMessage: () -> String) {
        if (BuildConfig.DEBUG) {
            log(lazyMessage())
        }
    }
}

enum class LogLevel {
    DEBUG, INFO, WARN, ERROR;

    companion object {
        fun fromString(value: String): LogLevel {
            return values().find { it.name == value.uppercase() } ?: INFO
        }
    }
}
"""
        chunks = chunk_text(code, language="kotlin")
        assert len(chunks) >= 2

    @staticmethod
    @pytest.mark.parametrize("file_extension", [".kt", ".kts", ".ktm"])
    def test_kotlin_file_extensions(file_extension):
        """Test Kotlin file extension detection."""
        config = language_config_registry.get_for_file(f"test{file_extension}")
        assert config is not None
        assert config.name == "kotlin"
