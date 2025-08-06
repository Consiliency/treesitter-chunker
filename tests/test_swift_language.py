"""Test Swift language support."""

import pytest

from chunker import chunk_text
from chunker.languages import language_config_registry


class TestSwiftLanguage:
    """Test Swift language chunking."""

    @staticmethod
    def test_swift_basic_chunking():
        """Test basic Swift chunking."""
        code = """
import Foundation

struct User {
    let id: UUID
    var name: String
    var email: String?

    init(name: String, email: String? = nil) {
        self.id = UUID()
        self.name = name
        self.email = email
    }

    mutating func updateEmail(_ newEmail: String) {
        email = newEmail
    }
}

class UserManager {
    private var users: [User] = []

    func addUser(_ user: User) {
        users.append(user)
    }

    func findUser(byId id: UUID) -> User? {
        return users.first { $0.id == id }
    }

    func getAllUsers() -> [User] {
        return users
    }
}

func validateEmail(_ email: String) -> Bool {
    let emailRegex = #"^[A-Z0-9a-z._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$"#
    return email.range(of: emailRegex, options: .regularExpression) != nil
}
"""
        chunks = chunk_text(code, language="swift")
        assert len(chunks) >= 3
        chunk_contents = [chunk.content for chunk in chunks]
        assert any("struct User" in c for c in chunk_contents)
        assert any("class UserManager" in c for c in chunk_contents)
        assert any("func validateEmail" in c for c in chunk_contents)

    @staticmethod
    def test_swift_protocols_extensions():
        """Test Swift protocols and extensions."""
        code = """
protocol Vehicle {
    var numberOfWheels: Int { get }
    func startEngine()
    func stopEngine()
}

protocol Electric {
    var batteryLevel: Double { get set }
    mutating func charge(to level: Double)
}

struct Car: Vehicle, Electric {
    let numberOfWheels = 4
    var batteryLevel: Double = 0.0

    func startEngine() {
        print("Engine started")
    }

    func stopEngine() {
        print("Engine stopped")
    }

    mutating func charge(to level: Double) {
        batteryLevel = min(level, 100.0)
    }
}

extension Vehicle {
    func describe() -> String {
        return "A vehicle with \\(numberOfWheels) wheels"
    }
}

extension Array where Element: Numeric {
    func sum() -> Element {
        return reduce(0, +)
    }

    func average() -> Double? {
        guard !isEmpty else { return nil }
        let total = reduce(0) { Double($0) + Double($1 as! NSNumber) }
        return total / Double(count)
    }
}
"""
        chunks = chunk_text(code, language="swift")
        assert len(chunks) >= 5

    @staticmethod
    def test_swift_enums_associated_values():
        """Test Swift enums with associated values."""
        code = """
enum Result<Success, Failure: Error> {
    case success(Success)
    case failure(Failure)

    func map<NewSuccess>(_ transform: (Success) -> NewSuccess) -> Result<NewSuccess, Failure> {
        switch self {
        case .success(let value):
            return .success(transform(value))
        case .failure(let error):
            return .failure(error)
        }
    }
}

enum NetworkError: Error {
    case noConnection
    case timeout(seconds: Int)
    case serverError(code: Int, message: String)
    case invalidResponse

    var localizedDescription: String {
        switch self {
        case .noConnection:
            return "No internet connection"
        case .timeout(let seconds):
            return "Request timed out after \\(seconds) seconds"
        case .serverError(let code, let message):
            return "Server error \\(code): \\(message)"
        case .invalidResponse:
            return "Invalid response from server"
        }
    }
}

enum ViewState<T> {
    case idle
    case loading
    case loaded(T)
    case error(Error)
}
"""
        chunks = chunk_text(code, language="swift")
        assert len(chunks) >= 3

    @staticmethod
    def test_swift_async_await():
        """Test Swift async/await and actors."""
        code = """
actor UserCache {
    private var cache: [UUID: User] = [:]

    func get(_ id: UUID) -> User? {
        return cache[id]
    }

    func set(_ user: User) {
        cache[user.id] = user
    }

    func clear() {
        cache.removeAll()
    }
}

class APIService {
    private let session = URLSession.shared
    private let decoder = JSONDecoder()

    func fetchUser(id: UUID) async throws -> User {
        let url = URL(string: "https://api.example.com/users/\\(id)")!
        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }

        return try decoder.decode(User.self, from: data)
    }

    func fetchUsers() async throws -> [User] {
        async let user1 = fetchUser(id: UUID())
        async let user2 = fetchUser(id: UUID())
        async let user3 = fetchUser(id: UUID())

        return try await [user1, user2, user3]
    }
}

@MainActor
class ViewModel: ObservableObject {
    @Published var users: [User] = []
    @Published var isLoading = false

    private let apiService = APIService()

    func loadUsers() async {
        isLoading = true
        defer { isLoading = false }

        do {
            users = try await apiService.fetchUsers()
        } catch {
            print("Failed to load users: \\(error)")
        }
    }
}
"""
        chunks = chunk_text(code, language="swift")
        assert len(chunks) >= 3

    @staticmethod
    def test_swift_property_wrappers():
        """Test Swift property wrappers."""
        code = """
@propertyWrapper
struct UserDefault<T> {
    let key: String
    let defaultValue: T

    var wrappedValue: T {
        get { UserDefaults.standard.object(forKey: key) as? T ?? defaultValue }
        set { UserDefaults.standard.set(newValue, forKey: key) }
    }
}

@propertyWrapper
struct Clamped<T: Comparable> {
    private var value: T
    let range: ClosedRange<T>

    init(wrappedValue: T, _ range: ClosedRange<T>) {
        self.range = range
        self.value = min(max(wrappedValue, range.lowerBound), range.upperBound)
    }

    var wrappedValue: T {
        get { value }
        set { value = min(max(newValue, range.lowerBound), range.upperBound) }
    }
}

struct Settings {
    @UserDefault(key: "username", defaultValue: "")
    var username: String

    @UserDefault(key: "volume", defaultValue: 50)
    @Clamped(0...100)
    var volume: Int

    @UserDefault(key: "isDarkMode", defaultValue: false)
    var isDarkMode: Bool
}
"""
        chunks = chunk_text(code, language="swift")
        assert len(chunks) >= 3

    @staticmethod
    def test_swift_generics_constraints():
        """Test Swift generics with constraints."""
        code = """
protocol Identifiable {
    associatedtype ID: Hashable
    var id: ID { get }
}

class Cache<T: Identifiable> {
    private var storage: [T.ID: T] = [:]

    func store(_ item: T) {
        storage[item.id] = item
    }

    func retrieve(id: T.ID) -> T? {
        return storage[id]
    }

    func remove(id: T.ID) {
        storage.removeValue(forKey: id)
    }
}

func findDuplicates<T: Hashable>(_ array: [T]) -> [T] {
    var seen = Set<T>()
    var duplicates = Set<T>()

    for item in array {
        if seen.contains(item) {
            duplicates.insert(item)
        } else {
            seen.insert(item)
        }
    }

    return Array(duplicates)
}

struct Container<T> where T: Equatable {
    private var items: [T] = []

    mutating func append(_ item: T) {
        items.append(item)
    }

    func contains(_ item: T) -> Bool {
        return items.contains(item)
    }
}
"""
        chunks = chunk_text(code, language="swift")
        assert len(chunks) >= 4

    @staticmethod
    @pytest.mark.parametrize("file_extension", [".swift"])
    def test_swift_file_extensions(file_extension):
        """Test Swift file extension detection."""
        config = language_config_registry.get_for_file(f"test{file_extension}")
        assert config is not None
        assert config.name == "swift"
