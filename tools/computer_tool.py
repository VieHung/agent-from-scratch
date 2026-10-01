"""Computer-use tools for a local Linux X11 desktop session.

MSS captures the X11 display selected by ``$DISPLAY``. Input is sent through
the ``xdotool`` executable. Wayland sessions are rejected deliberately: MSS
does not capture a compositor's Wayland desktop, and xdotool cannot inject
input into native Wayland clients.
"""
import base64
import os
import re
import shutil
import subprocess

import mss
import mss.tools


class ComputerUseError(RuntimeError):
    """An expected environment or input error for a computer-use action."""


def _require_x11() -> None:
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session_type == "wayland" or os.environ.get("WAYLAND_DISPLAY"):
        raise ComputerUseError(
            "Wayland session detected. This backend uses MSS + xdotool on X11; "
            "run the agent inside an Xorg VM, or use a separate XDG portal backend."
        )
    if session_type and session_type != "x11":
        raise ComputerUseError(
            f"Unsupported desktop session '{session_type}'; this backend requires X11."
        )
    if not os.environ.get("DISPLAY"):
        raise ComputerUseError(
            "DISPLAY is not set. Start the agent from a terminal inside the VM's X11 desktop."
        )


def _screen_region() -> dict:
    _require_x11()
    try:
        with mss.mss() as capture:
            if not capture.monitors:
                raise ComputerUseError("MSS did not find an X11 monitor.")
            # Index 0 is the full virtual desktop, including all X11 monitors.
            return dict(capture.monitors[0])
    except ComputerUseError:
        raise
    except Exception as exc:
        raise ComputerUseError(
            f"MSS could not connect to DISPLAY={os.environ['DISPLAY']!r}: {exc}"
        ) from None


def _run_xdotool(*args: str) -> None:
    _require_x11()
    executable = shutil.which("xdotool")
    if not executable:
        raise ComputerUseError(
            "xdotool is missing. Install it inside the Ubuntu VM with: sudo apt install xdotool"
        )
    try:
        result = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise ComputerUseError("xdotool timed out while sending desktop input.") from None
    except OSError as exc:
        raise ComputerUseError(f"Could not start xdotool: {exc}") from None
    if result.returncode:
        detail = (result.stderr or result.stdout or "no details").strip()
        raise ComputerUseError(f"xdotool failed (exit {result.returncode}): {detail[:400]}")


def _action_error(action):
    try:
        return action()
    except ComputerUseError as exc:
        return f"ERROR: {exc}"


def screenshot() -> dict | str:
    """Capture the full X11 desktop as a PNG for the vision model."""
    def capture_screen():
        region = _screen_region()
        try:
            with mss.mss() as capture:
                shot = capture.grab(region)
                png_bytes = mss.tools.to_png(shot.rgb, shot.size)
        except Exception as exc:
            raise ComputerUseError(f"MSS screenshot failed: {exc}") from None
        return {
            "kind": "image",
            "mime_type": "image/png",
            "base64": base64.b64encode(png_bytes).decode("ascii"),
            "width": shot.width,
            "height": shot.height,
        }

    return _action_error(capture_screen)


def click(x: int, y: int, button: int = 1) -> str:
    """Click an image-relative pixel; button 1=left, 2=middle, 3=right."""
    def perform_click():
        if (
            isinstance(x, bool) or not isinstance(x, int)
            or isinstance(y, bool) or not isinstance(y, int)
        ):
            raise ComputerUseError("x and y must be integer pixel coordinates.")
        if isinstance(button, bool) or not isinstance(button, int) or button not in (1, 2, 3):
            raise ComputerUseError("button must be 1 (left), 2 (middle), or 3 (right).")
        region = _screen_region()
        width, height = int(region["width"]), int(region["height"])
        if x < 0 or y < 0 or x >= width or y >= height:
            raise ComputerUseError(
                f"Click is outside the captured desktop ({width}x{height}); coordinates are image-relative."
            )
        screen_x = int(region["left"]) + x
        screen_y = int(region["top"]) + y
        _run_xdotool(
            "mousemove", "--sync", str(screen_x), str(screen_y),
            "click", "--clearmodifiers", str(button),
        )
        return f"Clicked button {button} at image coordinate ({x}, {y})."

    return _action_error(perform_click)


def type_text(text: str) -> str:
    """Type literal text into the currently focused X11 window."""
    def perform_type():
        if not isinstance(text, str):
            raise ComputerUseError("text must be a string.")
        if not text:
            return "No text to type."
        if len(text) > 1000:
            raise ComputerUseError("text is limited to 1000 characters per call.")
        _run_xdotool("type", "--clearmodifiers", "--delay", "0", "--", text)
        return f"Typed {len(text)} characters into the focused window."

    return _action_error(perform_type)


def press(key: str) -> str:
    """Press one X keysym or a modifier chord such as ``ctrl+l``."""
    def perform_press():
        if not isinstance(key, str) or not re.fullmatch(
            r"[A-Za-z0-9_][A-Za-z0-9_:+-]{0,63}", key
        ):
            raise ComputerUseError(
                "key must be an X keysym or chord using letters, digits, '+', '_', ':' or '-'."
            )
        _run_xdotool("key", "--clearmodifiers", key)
        return f"Pressed {key}."

    return _action_error(perform_press)


SCHEMAS = {
    "screenshot": (
        {"type": "object", "properties": {}},
        screenshot,
    ),
    "click": (
        {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X pixel in the screenshot image"},
                "y": {"type": "integer", "description": "Y pixel in the screenshot image"},
                "button": {
                    "type": "integer",
                    "enum": [1, 2, 3],
                    "default": 1,
                    "description": "1=left, 2=middle, 3=right",
                },
            },
            "required": ["x", "y"],
        },
        click,
    ),
    "type_text": (
        {
            "type": "object",
            "properties": {
                "text": {"type": "string", "maxLength": 1000},
            },
            "required": ["text"],
        },
        type_text,
    ),
    "press": (
        {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "X keysym or chord, e.g. Return or ctrl+l",
                },
            },
            "required": ["key"],
        },
        press,
    ),
}
