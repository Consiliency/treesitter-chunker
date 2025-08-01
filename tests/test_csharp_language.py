"""Test C# language support."""
import pytest

from chunker import chunk_text
from chunker.languages import language_config_registry


class TestCSharpLanguage:
    """Test C# language chunking."""

    @staticmethod
    def test_csharp_basic_chunking():
        """Test basic C# chunking."""
        code = """
using System;
using System.Collections.Generic;
using System.Linq;

namespace MyApp.Models
{
    public class User
    {
        public int Id { get; set; }
        public string Name { get; set; }
        public string Email { get; set; }

        public User(string name, string email)
        {
            Name = name;
            Email = email;
        }

        public void UpdateEmail(string newEmail)
        {
            if (string.IsNullOrWhiteSpace(newEmail))
                throw new ArgumentException("Email cannot be empty");

            Email = newEmail;
        }

        public override string ToString()
        {
            return $"User: {Name} ({Email})";
        }
    }

    public static class UserExtensions
    {
        public static bool IsValid(this User user)
        {
            return !string.IsNullOrEmpty(user.Name) &&
                   !string.IsNullOrEmpty(user.Email);
        }
    }
}
"""
        chunks = chunk_text(code, language="csharp")
        assert len(chunks) >= 2
        chunk_contents = [chunk.content for chunk in chunks]
        assert any("class User" in c for c in chunk_contents)
        assert any("static class UserExtensions" in c for c in chunk_contents)

    @staticmethod
    def test_csharp_interfaces_generics():
        """Test C# interfaces and generics."""
        code = """
public interface IRepository<T> where T : class
{
    Task<T> GetByIdAsync(int id);
    Task<IEnumerable<T>> GetAllAsync();
    Task<T> AddAsync(T entity);
    Task UpdateAsync(T entity);
    Task DeleteAsync(int id);
}

public abstract class BaseRepository<T> : IRepository<T> where T : class, IEntity
{
    protected readonly DbContext _context;
    protected readonly DbSet<T> _dbSet;

    protected BaseRepository(DbContext context)
    {
        _context = context;
        _dbSet = context.Set<T>();
    }

    public virtual async Task<T> GetByIdAsync(int id)
    {
        return await _dbSet.FindAsync(id);
    }

    public abstract Task<IEnumerable<T>> GetAllAsync();
}

public class UserRepository : BaseRepository<User>
{
    public UserRepository(DbContext context) : base(context) { }

    public override async Task<IEnumerable<User>> GetAllAsync()
    {
        return await _dbSet
            .Where(u => u.IsActive)
            .OrderBy(u => u.Name)
            .ToListAsync();
    }
}
"""
        chunks = chunk_text(code, language="csharp")
        assert len(chunks) >= 3

    @staticmethod
    def test_csharp_async_await():
        """Test C# async/await patterns."""
        code = """
public class ApiService
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<ApiService> _logger;

    public ApiService(HttpClient httpClient, ILogger<ApiService> logger)
    {
        _httpClient = httpClient;
        _logger = logger;
    }

    public async Task<T> GetAsync<T>(string endpoint)
    {
        try
        {
            var response = await _httpClient.GetAsync(endpoint);
            response.EnsureSuccessStatusCode();

            var json = await response.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<T>(json);
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "Error calling API endpoint: {Endpoint}", endpoint);
            throw;
        }
    }

    public async Task<IEnumerable<User>> GetUsersAsync()
    {
        var users = await GetAsync<List<User>>("/api/users");

        var tasks = users.Select(async user =>
        {
            user.Profile = await GetAsync<UserProfile>($"/api/users/{user.Id}/profile");
            return user;
        });

        return await Task.WhenAll(tasks);
    }
}
"""
        chunks = chunk_text(code, language="csharp")
        assert len(chunks) >= 1

    @staticmethod
    def test_csharp_linq_expressions():
        """Test C# LINQ and expression patterns."""
        code = """
public class DataProcessor
{
    public IEnumerable<ProductSummary> GetProductSummaries(List<Product> products)
    {
        return products
            .Where(p => p.IsActive && p.Price > 0)
            .GroupBy(p => p.Category)
            .Select(g => new ProductSummary
            {
                Category = g.Key,
                TotalProducts = g.Count(),
                AveragePrice = g.Average(p => p.Price),
                TopProducts = g.OrderByDescending(p => p.Sales)
                               .Take(5)
                               .Select(p => p.Name)
                               .ToList()
            })
            .OrderBy(s => s.Category);
    }

    public Expression<Func<User, bool>> GetUserFilter(UserSearchCriteria criteria)
    {
        return user =>
            (string.IsNullOrEmpty(criteria.Name) || user.Name.Contains(criteria.Name)) &&
            (criteria.MinAge == null || user.Age >= criteria.MinAge) &&
            (criteria.MaxAge == null || user.Age <= criteria.MaxAge) &&
            (!criteria.ActiveOnly || user.IsActive);
    }
}
"""
        chunks = chunk_text(code, language="csharp")
        assert len(chunks) >= 1

    @staticmethod
    def test_csharp_modern_features():
        """Test modern C# features (C# 9+)."""
        code = """
public record Person(string FirstName, string LastName)
{
    public string FullName => $"{FirstName} {LastName}";
}

public record struct Point(double X, double Y);

public class PatternMatchingExamples
{
    public string GetTypeInfo(object obj) => obj switch
    {
        null => "null",
        int n when n > 0 => $"Positive integer: {n}",
        string { Length: > 0 } s => $"Non-empty string: {s}",
        Person { FirstName: "John" } => "Person named John",
        List<int> { Count: 0 } => "Empty integer list",
        List<int> list => $"Integer list with {list.Count} items",
        _ => "Unknown type"
    };

    public void ProcessData(string? data)
    {
        if (data is not null and { Length: > 10 })
        {
            Console.WriteLine($"Processing: {data[..10]}...");
        }
    }
}

public class Calculator
{
    public static int Add(int a, int b) => a + b;

    public static double Calculate(string operation, double x, double y) =>
        operation switch
        {
            "+" => x + y,
            "-" => x - y,
            "*" => x * y,
            "/" when y != 0 => x / y,
            "/" => throw new DivideByZeroException(),
            _ => throw new ArgumentException($"Unknown operation: {operation}")
        };
}
"""
        chunks = chunk_text(code, language="csharp")
        assert len(chunks) >= 4

    @staticmethod
    def test_csharp_attributes_properties():
        """Test C# attributes and properties."""
        code = """
[AttributeUsage(AttributeTargets.Property)]
public class RequiredAttribute : ValidationAttribute
{
    public override bool IsValid(object value)
    {
        return value != null && !string.IsNullOrWhiteSpace(value.ToString());
    }
}

public class Product
{
    private decimal _price;

    [Required]
    public string Name { get; set; }

    [Range(0, 10000)]
    public decimal Price
    {
        get => _price;
        set
        {
            if (value < 0)
                throw new ArgumentException("Price cannot be negative");
            _price = value;
        }
    }

    [JsonIgnore]
    public DateTime LastModified { get; set; } = DateTime.Now;

    public string Category { get; init; }

    public required string Sku { get; init; }
}

[ApiController]
[Route("api/[controller]")]
public class ProductsController : ControllerBase
{
    [HttpGet("{id:int}")]
    [ProducesResponseType(typeof(Product), 200)]
    [ProducesResponseType(404)]
    public async Task<IActionResult> GetProduct(int id)
    {
        var product = await _repository.GetByIdAsync(id);
        return product == null ? NotFound() : Ok(product);
    }
}
"""
        chunks = chunk_text(code, language="csharp")
        assert len(chunks) >= 3

    @staticmethod
    @pytest.mark.parametrize("file_extension", [".cs", ".csx"])
    def test_csharp_file_extensions(file_extension):
        """Test C# file extension detection."""
        config = language_config_registry.get_for_file(f"test{file_extension}")
        assert config is not None
        assert config.name == "csharp"
