from .base import BaseAgent


class PlannerAgent(BaseAgent):
    name = "planner"
    system = """Bạn là Planner. Chia task lớn thành 3-7 bước nhỏ,
mỗi bước giao cho coder hoặc computer-agent. Output JSON list steps."""
