"""STUB Phase 3 — computer-use Ubuntu (X11). Chưa active, để học sau.

Khi vào Phase 3, cài: sudo apt install xdotool scrot && pip install mss pyautogui
Rồi implement:
- screenshot(): mss -> png base64 cho model vision
- click(x,y), type_text(text), press(key): via xdotool / pyautogui
An toàn: chỉ chạy trong VM, tắt sudo.
"""
import base64
import mss
import mss.tools

def screenshot() -> dict:
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[0])
        png_bytes = mss.tools.to_png(shot.rgb, shot.size)
        
    return {
        "kind": "image",
        "mime_type": "image/png",
        "base64": base64.b64encode(png_bytes).decode("ascii"),
        "width": shot.width,
        "height": shot.height,
    }


def click(x: int, y: int) -> str:
    return f"STUB: click({x},{y}) — cần xdotool trong VM."


def type_text(text: str) -> str:
    return f"STUB: type_text({text[:100]}) — cần xdotool trong VM."


SCHEMAS = {
    "screenshot": ({"type": "object", "properties": {}}, screenshot),
    "click": ({"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]}, click),
    "type_text": ({"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}, type_text),
}
