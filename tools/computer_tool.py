"""STUB Phase 3 — computer-use Ubuntu (X11). Chưa active, để học sau.

Khi vào Phase 3, cài: sudo apt install xdotool scrot && pip install mss pyautogui
Rồi implement:
- screenshot(): mss -> png base64 cho model vision
- click(x,y), type_text(text), press(key): via xdotool / pyautogui
An toàn: chỉ chạy trong VM, tắt sudo.
"""


def screenshot() -> str:
    return "STUB: chưa implement. Phase 3 cần mss + model vision."


def click(x: int, y: int) -> str:
    return f"STUB: click({x},{y}) — cần xdotool trong VM."


def type_text(text: str) -> str:
    return f"STUB: type_text({text[:100]}) — cần xdotool trong VM."


SCHEMAS = {
    "screenshot": ({"type": "object", "properties": {}}, screenshot),
    "click": ({"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]}, click),
    "type_text": ({"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}, type_text),
}
