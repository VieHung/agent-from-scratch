"""Computer-use tools for a local Linux X11 desktop session.

MSS captures the X11 display selected by ``$DISPLAY``. Input is sent through
the ``xdotool`` executable. Wayland sessions are rejected deliberately: MSS
does not capture a compositor's Wayland desktop, and xdotool cannot inject
input into native Wayland clients.
"""
import base64
from io import BytesIO
import os
from pathlib import Path
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


def _capture_image(bounds: tuple[int, int, int, int] | None = None) -> dict:
    """Capture a full desktop or a rectangle in full screenshot coordinates."""
    _require_x11()
    try:
        with mss.mss() as capture:
            if not capture.monitors:
                raise ComputerUseError("MSS did not find an X11 monitor.")
            desktop = dict(capture.monitors[0])
            desktop_width = int(desktop["width"])
            desktop_height = int(desktop["height"])
            if bounds is None:
                x, y, width, height = 0, 0, desktop_width, desktop_height
            else:
                x, y, width, height = bounds
                if any(isinstance(value, bool) or not isinstance(value, int) for value in bounds):
                    raise ComputerUseError("x, y, width and height must be integers.")
                if (
                    x < 0 or y < 0 or width <= 0 or height <= 0
                    or x + width > desktop_width or y + height > desktop_height
                ):
                    raise ComputerUseError(
                        f"Region must fit inside the {desktop_width}x{desktop_height} desktop "
                        "and have positive width and height."
                    )
            region = {
                "left": int(desktop["left"]) + x,
                "top": int(desktop["top"]) + y,
                "width": width,
                "height": height,
            }
            shot = capture.grab(region)
            png_bytes = mss.tools.to_png(shot.rgb, shot.size)
    except ComputerUseError:
        raise
    except Exception as exc:
        raise ComputerUseError(f"MSS screenshot failed: {exc}") from None
    return {
        "kind": "image",
        "mime_type": "image/png",
        "base64": base64.b64encode(png_bytes).decode("ascii"),
        "width": shot.width,
        "height": shot.height,
        "origin_x": x,
        "origin_y": y,
        "desktop_width": desktop_width,
        "desktop_height": desktop_height,
    }


def screenshot() -> dict | str:
    """Capture the full X11 desktop as an image for the vision model."""
    return _action_error(lambda: _capture_image())


def screenshot_region(x: int, y: int, width: int, height: int) -> dict | str:
    """Capture a desktop rectangle and return its image and desktop origin."""
    return _action_error(lambda: _capture_image((x, y, width, height)))


def view_image(path: str, origin_x: int | None = None, origin_y: int | None = None) -> dict | str:
    """Send a local PNG/JPEG to vision; optional origin maps a desktop crop."""
    def open_image():
        from PIL import Image

        if not isinstance(path, str) or not path:
            raise ComputerUseError("path must be a local PNG or JPEG file path.")
        if (origin_x is None) != (origin_y is None):
            raise ComputerUseError("Provide both origin_x and origin_y for a desktop crop.")
        if origin_x is not None and any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (origin_x, origin_y)
        ):
            raise ComputerUseError("origin_x and origin_y must be nonnegative integers.")
        try:
            with Path(path).open("rb") as image_file:
                image_bytes = image_file.read(20 * 1024 * 1024 + 1)
        except OSError as exc:
            raise ComputerUseError(f"Cannot read image: {exc}") from None
        if len(image_bytes) > 20 * 1024 * 1024:
            raise ComputerUseError("Image file is larger than 20 MiB.")
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                image_format = image.format
                width, height = image.size
                if image_format not in {"PNG", "JPEG"}:
                    raise ComputerUseError("view_image supports PNG and JPEG files only.")
                if width <= 0 or height <= 0 or width * height > 40_000_000:
                    raise ComputerUseError("Image dimensions are invalid or too large.")
                image.load()
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise ComputerUseError(f"Invalid image file: {exc}") from None

        result = {
            "kind": "image",
            "mime_type": "image/png" if image_format == "PNG" else "image/jpeg",
            "base64": base64.b64encode(image_bytes).decode("ascii"),
            "width": width,
            "height": height,
        }
        if origin_x is not None:
            desktop = _screen_region()
            desktop_width, desktop_height = int(desktop["width"]), int(desktop["height"])
            if origin_x + width > desktop_width or origin_y + height > desktop_height:
                raise ComputerUseError("Image and origin do not fit inside the current desktop.")
            result.update({
                "origin_x": origin_x,
                "origin_y": origin_y,
                "desktop_width": desktop_width,
                "desktop_height": desktop_height,
            })
        return result

    return _action_error(open_image)


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
    "screenshot_region": (
        {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "Left pixel in the full desktop screenshot"},
                "y": {"type": "integer", "description": "Top pixel in the full desktop screenshot"},
                "width": {"type": "integer", "description": "Crop width in pixels"},
                "height": {"type": "integer", "description": "Crop height in pixels"},
            },
            "required": ["x", "y", "width", "height"],
        },
        screenshot_region,
    ),
    "view_image": (
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Local PNG or JPEG path"},
                "origin_x": {
                    "type": "integer",
                    "description": "Optional full desktop X of this image's top-left pixel",
                },
                "origin_y": {
                    "type": "integer",
                    "description": "Optional full desktop Y of this image's top-left pixel",
                },
            },
            "required": ["path"],
        },
        view_image,
    ),
    "click": (
        {
            "type": "object",
            "properties": {
                "x": {
                    "type": "integer",
                    "description": "X pixel in full desktop screenshot; add crop origin_x to crop-local X",
                },
                "y": {
                    "type": "integer",
                    "description": "Y pixel in full desktop screenshot; add crop origin_y to crop-local Y",
                },
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
