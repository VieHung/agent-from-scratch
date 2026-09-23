from .base import BaseAgent


class ReviewerAgent(BaseAgent):
    name = "reviewer"
    system = """Bạn là Reviewer. Soi lỗi, edge case, lệnh nguy hiểm.
Trả về PASS hoặc FAIL + lý do + gợi ý sửa."""
