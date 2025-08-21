using System;
using System.Collections.Generic;

namespace TestNamespace
{
    public class Calculator
    {
        private readonly ILogger _logger;
        
        public Calculator(ILogger logger)
        {
            _logger = logger;
        }
        
        public int Add(int a, int b)
        {
            _logger.Log($"Adding {a} + {b}");
            return a + b;
        }
        
        public int Multiply(int a, int b)
        {
            _logger.Log($"Multiplying {a} * {b}");
            return a * b;
        }
    }
    
    public interface ILogger
    {
        void Log(string message);
    }
    
    public class ConsoleLogger : ILogger
    {
        public void Log(string message)
        {
            Console.WriteLine($"[{DateTime.Now:HH:mm:ss}] {message}");
        }
    }
}
