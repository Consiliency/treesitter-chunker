"""Comprehensive tests for Haskell language support."""

from chunker import chunk_file
from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.languages.haskell import HaskellPlugin


class TestHaskellBasicChunking:
    """Test basic Haskell chunking functionality."""

    @staticmethod
    def test_simple_function(tmp_path):
        """Test basic function definition."""
        src = tmp_path / "main.hs"
        src.write_text(
            """-- Simple function
factorial :: Integer -> Integer
factorial 0 = 1
factorial n = n * factorial (n - 1)

-- Another function
fibonacci :: Int -> Int
fibonacci n
  | n <= 1    = n
  | otherwise = fibonacci (n - 1) + fibonacci (n - 2)
""",
        )
        chunks = chunk_file(src, "haskell")
        assert len(chunks) >= 2
        function_chunks = [c for c in chunks if "function" in c.node_type]
        assert len(function_chunks) >= 2
        assert any("factorial" in c.content for c in function_chunks)
        assert any("fibonacci" in c.content for c in function_chunks)

    @staticmethod
    def test_data_types(tmp_path):
        """Test data type definitions."""
        src = tmp_path / "types.hs"
        src.write_text(
            """-- Data types
data Color = Red | Green | Blue deriving (Show, Eq)

data Tree a = Empty
            | Node a (Tree a) (Tree a)
            deriving (Show, Eq)

-- Type alias
type Name = String
type Age = Int

-- Newtype
newtype Email = Email String deriving (Show)
""",
        )
        chunks = chunk_file(src, "haskell")
        chunk_types = {chunk.node_type for chunk in chunks}
        assert "data_type" in chunk_types or "data" in chunk_types
        assert "type_alias" in chunk_types or "type_synonym" in chunk_types
        assert "newtype" in chunk_types

    @staticmethod
    def test_type_classes(tmp_path):
        """Test type class and instance declarations."""
        src = tmp_path / "classes.hs"
        src.write_text(
            """-- Type class
class Printable a where
    toString :: a -> String
    print :: a -> IO ()
    print x = putStrLn (toString x)

-- Instance
instance Printable Bool where
    toString True = "true"
    toString False = "false"

instance Printable Int where
    toString = show
""",
        )
        chunks = chunk_file(src, "haskell")
        chunk_types = {chunk.node_type for chunk in chunks}
        assert "class_declaration" in chunk_types
        assert "instance_declaration" in chunk_types
        assert any("Printable" in c.content for c in chunks)
        assert any("instance Printable Bool" in c.content for c in chunks)

    @staticmethod
    def test_module_structure(tmp_path):
        """Test module with exports."""
        src = tmp_path / "MyModule.hs"
        src.write_text(
            """module MyModule
    ( factorial
    , fibonacci
    , Tree(..)
    ) where

import Data.List
import qualified Data.Map as Map

factorial :: Integer -> Integer
factorial 0 = 1
factorial n = n * factorial (n - 1)

fibonacci :: Int -> Int
fibonacci = fib 0 1
  where
    fib a b 0 = a
    fib a b n = fib b (a + b) (n - 1)
""",
        )
        chunks = chunk_file(src, "haskell")
        assert any("module_declaration" in c.node_type for c in chunks)
        module_chunk = next(c for c in chunks if "module_declaration" in c.node_type)
        assert "MyModule" in module_chunk.content
        assert any("factorial" in c.content for c in chunks)
        assert any("fibonacci" in c.content for c in chunks)


class TestHaskellContractCompliance:
    """Test ExtendedLanguagePluginContract implementation."""

    @classmethod
    def test_implements_contract(cls):
        """Test that HaskellPlugin implements the contract."""
        plugin = HaskellPlugin()
        assert isinstance(plugin, ExtendedLanguagePluginContract)

    @staticmethod
    def test_get_semantic_chunks():
        """Test get_semantic_chunks method."""
        plugin = HaskellPlugin()

        class MockNode:

            def __init__(self, node_type, start=0, end=1):
                self.type = node_type
                self.start_byte = start
                self.end_byte = end
                self.start_point = 0, 0
                self.end_point = 0, end
                self.children = []

        root = MockNode("module")
        func_node = MockNode("function", 0, 50)
        root.children.append(func_node)
        source = b"factorial n = n * factorial (n - 1)"
        chunks = plugin.get_semantic_chunks(root, source)
        assert len(chunks) >= 1
        assert any(chunk["type"] == "function" for chunk in chunks)

    @classmethod
    def test_get_chunk_node_types(cls):
        """Test get_chunk_node_types method."""
        plugin = HaskellPlugin()
        node_types = plugin.get_chunk_node_types()
        assert isinstance(node_types, set)
        assert "function" in node_types
        assert "data_type" in node_types
        assert "class_declaration" in node_types

    @staticmethod
    def test_should_chunk_node():
        """Test should_chunk_node method."""
        plugin = HaskellPlugin()

        class MockNode:

            def __init__(self, node_type):
                self.type = node_type
                self.children = []

        assert plugin.should_chunk_node(MockNode("function"))
        assert plugin.should_chunk_node(MockNode("data_type"))
        assert plugin.should_chunk_node(MockNode("class_declaration"))
        assert not plugin.should_chunk_node(MockNode("identifier"))
        assert not plugin.should_chunk_node(MockNode("comment"))

    @staticmethod
    def test_get_node_context():
        """Test get_node_context method."""
        plugin = HaskellPlugin()

        class MockNode:

            def __init__(self, node_type):
                self.type = node_type
                self.children = []

        node = MockNode("function")
        context = plugin.get_node_context(node, b"factorial n = n!")
        assert context is not None
        assert "function" in context


class TestHaskellEdgeCases:
    """Test edge cases in Haskell parsing."""

    @staticmethod
    def test_empty_file(tmp_path):
        """Test empty Haskell file."""
        src = tmp_path / "empty.hs"
        src.write_text("")
        chunks = chunk_file(src, "haskell")
        assert len(chunks) == 0

    @staticmethod
    def test_comments_only(tmp_path):
        """Test file with only comments."""
        src = tmp_path / "comments.hs"
        src.write_text(
            """-- This is a comment
{- This is a
   multi-line comment -}
-- Another comment
""",
        )
        chunks = chunk_file(src, "haskell")
        assert len(chunks) == 0

    @staticmethod
    def test_guards_and_pattern_matching(tmp_path):
        """Test functions with guards and pattern matching."""
        src = tmp_path / "patterns.hs"
        src.write_text(
            """-- Pattern matching
isEmpty :: [a] -> Bool
isEmpty [] = True
isEmpty _  = False

-- Guards
grade :: Int -> String
grade score
  | score >= 90 = "A"
  | score >= 80 = "B"
  | score >= 70 = "C"
  | score >= 60 = "D"
  | otherwise   = "F"

-- Case expression
describe :: Maybe Int -> String
describe x = case x of
    Nothing -> "No value"
    Just n  -> "Value: " ++ show n
""",
        )
        chunks = chunk_file(src, "haskell")
        function_chunks = [c for c in chunks if "function" in c.node_type]
        assert len(function_chunks) >= 3
        assert any("isEmpty" in c.content for c in function_chunks)
        assert any("grade" in c.content for c in function_chunks)
        assert any("describe" in c.content for c in function_chunks)

    @staticmethod
    def test_where_clauses(tmp_path):
        """Test functions with where clauses."""
        src = tmp_path / "where.hs"
        src.write_text(
            """-- Function with where clause
quadratic :: Double -> Double -> Double -> (Double, Double)
quadratic a b c = (x1, x2)
  where
    x1 = (-b + discriminant) / (2 * a)
    x2 = (-b - discriminant) / (2 * a)
    discriminant = sqrt (b^2 - 4*a*c)

-- Nested where
complexCalc :: Int -> Int
complexCalc n = result
  where
    result = helper n
    helper 0 = 0
    helper x = x + helper (x - 1)
      where
        adjusted = x * 2
""",
        )
        chunks = chunk_file(src, "haskell")
        assert any("quadratic" in c.content and "where" in c.content for c in chunks)
        assert any("complexCalc" in c.content for c in chunks)

    @staticmethod
    def test_lambda_expressions(tmp_path):
        """Test lambda expressions and higher-order functions."""
        src = tmp_path / "lambdas.hs"
        src.write_text(
            """-- Higher-order functions
map' :: (a -> b) -> [a] -> [b]
map' f xs = foldr (\\x acc -> f x : acc) [] xs

-- Lambda in let binding
sumSquares :: [Int] -> Int
sumSquares xs = sum (map (\\x -> x * x) xs)

-- Point-free style
double :: Num a => a -> a
double = (*2)
""",
        )
        chunks = chunk_file(src, "haskell")
        assert any("map'" in c.content for c in chunks)
        assert any("sumSquares" in c.content for c in chunks)
        assert any("double" in c.content for c in chunks)
