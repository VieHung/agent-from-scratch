"""Base agent cho Phase 4 multi-agent."""


class BaseAgent:
    name = "base"
    system = "Bạn là sub-agent Ubuntu."

    def __init__(self, llm, registry):
        self.llm = llm
        self.registry = registry
