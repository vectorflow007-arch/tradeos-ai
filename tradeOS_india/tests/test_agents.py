"""Tests for agents/ modules: base_agent, strategy, risk, execution, research, orchestrator."""

import pytest


class TestBaseAgent:
    def test_import_enums(self):
        from agents.base_agent import (
            TaskType, TaskPriority, AgentStatus,
        )
        assert TaskType is not None
        assert TaskPriority is not None
        assert AgentStatus is not None

    def test_import_dataclasses(self):
        from agents.base_agent import AgentTask, AgentResult
        task = AgentTask(
            task_id="test-001",
            task_type="strategy_signal",
            priority=1,
            payload={"symbol": "NSE:NIFTY50-INDEX"},
        )
        assert task.task_id == "test-001"
        assert task.priority == 1

    def test_base_agent_abstract(self):
        from agents.base_agent import BaseAgent
        with pytest.raises(TypeError):
            BaseAgent()


class TestStrategyAgent:
    def test_import(self):
        from agents.strategy_agent import StrategyAgent
        assert StrategyAgent is not None


class TestRiskAgent:
    def test_import(self):
        from agents.risk_agent import RiskAgent
        assert RiskAgent is not None


class TestExecutionAgent:
    def test_import(self):
        from agents.execution_agent import ExecutionAgent
        assert ExecutionAgent is not None


class TestResearchAgent:
    def test_import(self):
        from agents.research_agent import ResearchAgent
        assert ResearchAgent is not None


class TestOrchestrator:
    def test_import(self):
        from agents.orchestrator import AgentOrchestrator
        assert AgentOrchestrator is not None
