"""Focused image-observation checks without touching the real desktop."""
import base64
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.loop import run
from core.registry import ToolRegistry
from tools import computer_tool
from tools.file_tool import read_file


class FakeShot:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.size = (width, height)
        self.rgb = bytes(width * height * 3)


class FakeCapture:
    monitors = [{"left": -100, "top": 20, "width": 100, "height": 80}]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def grab(self, region):
        self.last_region = dict(region)
        return FakeShot(region["width"], region["height"])


class TwoStepLLM:
    def __init__(self):
        self.calls = 0
        self.observed_messages = None

    def chat(self, messages, tools_schema=None):
        self.calls += 1
        if self.calls == 1:
            return {
                "content": "",
                "tool_calls": [{
                    "name": "screenshot_region",
                    "arguments": {"x": 70, "y": 3, "width": 30, "height": 20},
                    "id": "crop1",
                }],
            }
        self.observed_messages = messages
        return {"content": "Đã thấy ảnh crop.", "tool_calls": []}


class ScriptedLLM:
    def __init__(self, actions):
        self.actions = actions
        self.request_images = []
        self.request_notes = []

    def chat(self, messages, tools_schema=None):
        image_messages = [
            message for message in messages
            if isinstance(message.get("content"), list)
            and any(part.get("type") == "image_url" for part in message["content"])
        ]
        self.request_images.append(len(image_messages))
        self.request_notes.append([
            part["text"]
            for message in messages
            if isinstance(message.get("content"), list)
            for part in message["content"]
            if part.get("type") == "text"
        ] + [
            message["content"] for message in messages
            if isinstance(message.get("content"), str)
            and "Ảnh cũ đã được lược bỏ" in message["content"]
        ])
        action = self.actions.pop(0)
        if action is None:
            return {"content": "Xong", "tool_calls": []}
        name, arguments = action
        return {
            "content": "",
            "tool_calls": [{
                "name": name,
                "arguments": arguments,
                "id": f"call{len(self.request_images)}",
            }],
        }


def _fake_image(origin_x=0):
    return {
        "kind": "image", "mime_type": "image/png", "base64": "YWJj",
        "width": 10, "height": 10, "origin_x": origin_x, "origin_y": 0,
        "desktop_width": 100, "desktop_height": 80,
    }


def _scripted_registry(click_result="Clicked"):
    registry = ToolRegistry()
    registry.register("screenshot", "full", {"type": "object", "properties": {}}, _fake_image)
    registry.register(
        "screenshot_region", "crop", computer_tool.SCHEMAS["screenshot_region"][0],
        lambda x, y, width, height: _fake_image(x),
    )
    registry.register(
        "click", "click", computer_tool.SCHEMAS["click"][0],
        lambda x, y: click_result,
    )
    return registry


def test_crop_reaches_model_with_desktop_origin():
    capture = FakeCapture()
    with patch.dict(
        os.environ,
        {"XDG_SESSION_TYPE": "x11", "WAYLAND_DISPLAY": "", "DISPLAY": ":fake"},
    ), patch.object(computer_tool.mss, "mss", return_value=capture):
        registry = ToolRegistry()
        registry.register(
            "screenshot_region", "crop", computer_tool.SCHEMAS["screenshot_region"][0],
            computer_tool.screenshot_region,
        )
        llm = TwoStepLLM()
        result = run("Xem góc phải", llm, registry, max_steps=2, verbose=False)

    assert result["final"] == "Đã thấy ảnh crop."
    assert capture.last_region == {"left": -30, "top": 23, "width": 30, "height": 20}
    assert result["log"][0]["obs"]["origin_x"] == 70
    assert "base64" not in result["log"][0]["obs"]
    tool_message = llm.observed_messages[-2]
    image_message = llm.observed_messages[-1]
    assert json.loads(tool_message["content"])["image"]["origin_x"] == 70
    assert "(70, 3)" in image_message["content"][0]["text"]
    image_url = image_message["content"][1]["image_url"]["url"]
    assert base64.b64decode(image_url.split(",", 1)[1]).startswith(b"\x89PNG\r\n\x1a\n")


def test_old_images_are_compacted_and_capture_loop_stops():
    crop = lambda x: ("screenshot_region", {"x": x, "y": 0, "width": 10, "height": 10})
    llm = ScriptedLLM([
        ("screenshot", {}), crop(10), crop(20), crop(30), crop(40),
    ])
    result = run("Tìm nút", llm, _scripted_registry(), max_steps=12, verbose=False)

    assert llm.request_images == [0, 1, 2, 2, 2]
    assert len(result["log"]) == 5
    assert result["log"][-1]["obs"] == "blocked: screenshot limit"
    assert "chưa thể xác nhận" in result["final"]
    assert any("(30, 0)" in note for note in llm.request_notes[-1])
    assert any("lược bỏ" in note for note in llm.request_notes[-1])


def test_successful_gui_action_resets_capture_budget():
    llm = ScriptedLLM([
        ("screenshot", {}), ("screenshot", {}), ("screenshot", {}),
        ("screenshot", {}), ("click", {"x": 1, "y": 2}),
        ("screenshot", {}), None,
    ])
    result = run("Đổi tab", llm, _scripted_registry(), max_steps=8, verbose=False)

    assert result["final"] == "Xong"
    assert llm.request_images == [0, 1, 2, 2, 2, 0, 1]


def test_failed_gui_action_does_not_reset_capture_budget():
    llm = ScriptedLLM([
        ("screenshot", {}), ("screenshot", {}), ("screenshot", {}),
        ("screenshot", {}), ("click", {"x": 1, "y": 2}),
        ("screenshot", {}),
    ])
    result = run(
        "Đổi tab", llm, _scripted_registry(click_result="ERROR: click failed"),
        max_steps=8, verbose=False,
    )

    assert result["log"][-1]["obs"] == "blocked: screenshot limit"
    assert llm.request_images[-1] == 2


def test_view_image_and_binary_read():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "crop.png"
        Image.new("RGB", (5, 4), "red").save(path)
        result = computer_tool.view_image(str(path))
        assert isinstance(result, dict) and result["width"] == 5
        assert result["mime_type"] == "image/png"
        assert "binary file" in read_file(str(path))


if __name__ == "__main__":
    test_crop_reaches_model_with_desktop_origin()
    test_old_images_are_compacted_and_capture_loop_stops()
    test_successful_gui_action_resets_capture_budget()
    test_failed_gui_action_does_not_reset_capture_budget()
    test_view_image_and_binary_read()
    print("COMPUTER USE IMAGE CHECKS PASS")
