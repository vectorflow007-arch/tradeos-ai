"""Tests for llm/ modules: base_llm, claude, openai, groq clients."""

import pytest


class TestBaseLLM:
    def test_abstract(self):
        from llm.base_llm import BaseLLM
        with pytest.raises(TypeError):
            BaseLLM()

    def test_interface_methods(self):
        from llm.base_llm import BaseLLM
        import inspect
        methods = [m for m in dir(BaseLLM) if not m.startswith("_")]
        assert "complete" in methods
        assert "stream" in methods


class TestClaudeClient:
    def test_import(self):
        from llm.claude_client import ClaudeClient
        assert ClaudeClient is not None

    def test_properties(self):
        from llm.claude_client import ClaudeClient
        # Should have provider/model info
        assert hasattr(ClaudeClient, "complete")


class TestOpenAIClient:
    def test_import(self):
        from llm.openai_client import OpenAIClient
        assert OpenAIClient is not None


class TestGroqClient:
    def test_import(self):
        from llm.groq_client import GroqClient
        assert GroqClient is not None
