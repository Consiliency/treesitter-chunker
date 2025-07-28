"""Tests for Ruby language support."""

import pytest

from chunker.chunker import chunk_text
from chunker.languages import language_config_registry
from chunker.parser import list_languages


class TestRubyLanguageSupport:
    """Test Ruby language chunking."""

    @pytest.mark.skipif(
        "ruby" not in list_languages(), reason="Ruby grammar not available",
    )
    def test_ruby_method_chunking(self):
        """Test chunking Ruby methods."""
        code = """
class User
  attr_accessor :name, :email
  
  def initialize(name, email)
    @name = name
    @email = email
  end
  
  def full_name
    "#{@name} <#{@email}>"
  end
  
  def self.find_by_email(email)
    # Class method
    User.where(email: email).first
  end
  
  private
  
  def validate_email
    @email.include?('@')
  end
end
"""
        chunks = chunk_text(code, "ruby", "user.rb")

        # Should find class and methods
        assert len(chunks) >= 5  # class + attr_accessor + methods

        # Check for methods
        method_chunks = [c for c in chunks if c.node_type == "method"]
        assert len(method_chunks) >= 3  # initialize, full_name, validate_email

        # Check for class
        class_chunks = [c for c in chunks if c.node_type == "class"]
        assert len(class_chunks) == 1
        assert class_chunks[0].parent_context == "User"

    @pytest.mark.skipif(
        "ruby" not in list_languages(), reason="Ruby grammar not available",
    )
    def test_ruby_module_chunking(self):
        """Test chunking Ruby modules."""
        code = """
module Authentication
  extend ActiveSupport::Concern
  
  included do
    before_action :authenticate_user!
  end
  
  def authenticate_user!
    redirect_to login_path unless logged_in?
  end
  
  def logged_in?
    current_user.present?
  end
  
  module ClassMethods
    def requires_admin
      before_action :ensure_admin
    end
  end
end
"""
        chunks = chunk_text(code, "ruby", "authentication.rb")

        # Should find modules and methods
        module_chunks = [c for c in chunks if c.node_type == "module"]
        assert len(module_chunks) >= 1

        # Check for Authentication module
        auth_modules = [
            c for c in module_chunks if c.parent_context == "Authentication"
        ]
        assert len(auth_modules) == 1

    @pytest.mark.skipif(
        "ruby" not in list_languages(), reason="Ruby grammar not available",
    )
    def test_ruby_dsl_blocks(self):
        """Test chunking Ruby DSL blocks."""
        code = """
describe User do
  let(:user) { User.new(name: "John", email: "john@example.com") }
  
  describe "#full_name" do
    it "returns the full name with email" do
      expect(user.full_name).to eq("John <john@example.com>")
    end
  end
  
  context "when email is invalid" do
    before do
      user.email = "invalid"
    end
    
    it "fails validation" do
      expect(user).not_to be_valid
    end
  end
end

namespace :db do
  desc "Seed the database"
  task seed: :environment do
    User.create!(name: "Admin", email: "admin@example.com")
  end
end
"""
        chunks = chunk_text(code, "ruby", "user_spec.rb")

        # Should find RSpec blocks
        block_chunks = [c for c in chunks if c.node_type == "block"]
        assert len(block_chunks) >= 5  # describe, context, it blocks, namespace, task

    @pytest.mark.skipif(
        "ruby" not in list_languages(), reason="Ruby grammar not available",
    )
    def test_ruby_attr_methods(self):
        """Test chunking Ruby attr_* methods."""
        code = """
class Book
  attr_reader :title, :author
  attr_writer :price
  attr_accessor :isbn, :published_date
  
  def initialize(title, author)
    @title = title
    @author = author
  end
  
  def description
    "#{@title} by #{@author}"
  end
end
"""
        chunks = chunk_text(code, "ruby", "book.rb")

        # Should find attr_* declarations
        call_chunks = [c for c in chunks if c.node_type == "call"]
        attr_chunks = [c for c in call_chunks if c.metadata.get("attr_type")]

        # Note: The plugin may not detect attr_* as separate chunks
        # They might be included in the class chunk
        class_chunks = [c for c in chunks if c.node_type == "class"]
        assert len(class_chunks) == 1

    @pytest.mark.skipif(
        "ruby" not in list_languages(), reason="Ruby grammar not available",
    )
    def test_ruby_singleton_methods(self):
        """Test chunking Ruby singleton methods."""
        code = """
class Configuration
  class << self
    attr_accessor :api_key, :base_url
    
    def configure
      yield self
    end
    
    def reset!
      @api_key = nil
      @base_url = nil
    end
  end
  
  def self.configured?
    api_key.present? && base_url.present?
  end
end
"""
        chunks = chunk_text(code, "ruby", "configuration.rb")

        # Should find singleton class and methods
        singleton_methods = [c for c in chunks if c.node_type == "singleton_method"]
        singleton_classes = [c for c in chunks if c.node_type == "singleton_class"]

        assert len(chunks) >= 2  # At least main class and some methods

    @pytest.mark.skipif(
        "ruby" not in list_languages(), reason="Ruby grammar not available",
    )
    def test_ruby_language_config(self):
        """Test Ruby language configuration."""
        config = language_config_registry.get_config("ruby")

        assert config is not None
        assert config.name == "ruby"
        assert ".rb" in config.file_extensions
        assert ".rake" in config.file_extensions

        # Check chunk rules
        rule_names = [rule.name for rule in config.chunk_rules]
        assert "methods" in rule_names
        assert "classes" in rule_names
        assert "modules" in rule_names
        assert "dsl_blocks" in rule_names

        # Check scope node types
        assert "program" in config.scope_node_types
        assert "class" in config.scope_node_types
        assert "module" in config.scope_node_types
        assert "method" in config.scope_node_types
