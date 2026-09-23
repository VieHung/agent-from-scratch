from .base import BaseAgent


class CoderAgent(BaseAgent):
    name = "coder"
    system = """Bạn là Coder. Đọc file trước khi sửa, sửa tối thiểu,
chạy test sau mỗi thay đổi, báo file:line khi xong."""
