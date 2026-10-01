"""ReAct loop cốt lõi. Đây là file quan trọng nhất Phase 0."""
import json
import time


MAX_SCREEN_OBSERVATIONS_WITHOUT_ACTION = 4
SCREEN_CAPTURE_TOOLS = {"screenshot", "screenshot_region"}
GUI_ACTION_TOOLS = {"click", "press", "type_text"}

SYSTEM_PROMPT = """Bạn là coding agent chạy trên Ubuntu.
Luôn suy luận ngắn gọn rồi gọi tool khi cần.
Quy tắc:
- Ưu tiên đọc file trước khi sửa.
- Mọi lệnh shell đi qua tool bash.
- Khi xong việc, trả lời trực tiếp, không gọi thêm tool.
- Không bao giờ chạy lệnh nguy hiểm: rm -rf /, mkfs, dd, shutdown.
"""

COMPUTER_USE_PROMPT = """Khi điều khiển desktop:
- screenshot và screenshot_region trả ảnh trực tiếp cho bạn, không tạo file trên đĩa.
- Nếu chi tiết trên ảnh nhỏ, gọi screenshot_region với tọa độ trên ảnh toàn màn hình.
- Dùng tool ảnh để chụp/crop màn hình; không tìm file screenshot trong /tmp hoặc crop bằng bash.
- click dùng tọa độ của toàn màn hình; ảnh crop sẽ kèm tọa độ gốc để quy đổi.
- Nếu có ảnh PNG/JPEG trong file, dùng view_image; read_file chỉ dành cho văn bản.
- Sau thao tác GUI, chụp lại màn hình để xác nhận kết quả trước khi mô tả.
- Chỉ chụp tối đa 4 lần trước một thao tác GUI. Nếu vẫn không xác định được mục tiêu,
  nói rõ điểm chưa chắc chắn; không đoán tọa độ click và không chụp lặp vùng tương tự.
"""


def _omit_image(message):
    """Release an old base64 payload while retaining its coordinate note."""
    content = message["content"]
    if isinstance(content, list):
        notes = " ".join(
            part["text"] for part in content if part.get("type") == "text"
        )
        message["content"] = f"{notes} Ảnh cũ đã được lược bỏ khỏi ngữ cảnh."


def _compact_images(messages, image_history):
    """Keep the newest full screenshot and newest other image, at most two."""
    latest_index = image_history[-1][0]
    full_index = next(
        (index for index, name in reversed(image_history) if name == "screenshot"),
        None,
    )
    keep = {latest_index}
    if full_index is not None and full_index != latest_index:
        keep.add(full_index)
    elif len(image_history) > 1:
        keep.add(image_history[-2][0])
    retained = []
    for index, name in image_history:
        if index in keep:
            retained.append((index, name))
        else:
            _omit_image(messages[index])
    return retained


def run(task, llm, registry, max_steps=12, verbose=True):
    system_prompt = SYSTEM_PROMPT
    if "screenshot_region" in registry.names():
        system_prompt += "\n" + COMPUTER_USE_PROMPT
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]
    log = []
    image_history = []
    screen_observations_without_action = 0
    for step in range(1, max_steps + 1):
        started = time.monotonic()
        if verbose and image_history:
            encoded_chars = sum(
                len(part["image_url"]["url"])
                for index, _ in image_history
                for part in messages[index]["content"]
                if part.get("type") == "image_url"
            )
            print(
                f"llm request: {len(image_history)} ảnh, "
                f"base64 ~{encoded_chars / 1024 / 1024:.2f} MiB"
            )
        try:
            resp = llm.chat(messages, tools_schema=registry.schema())
        finally:
            if verbose and image_history:
                print(f"llm wait: {time.monotonic() - started:.1f}s")
        content, tool_calls = resp.get("content", ""), resp.get("tool_calls", [])
        if verbose:
            print(f"\n--- step {step} ---")
            if content:
                print(f"thought: {content[:500]}")
        if not tool_calls:
            log.append({"step": step, "thought": content, "done": True})
            return {"final": content, "steps": step, "log": log}
        for tc in tool_calls:
            name, args = tc["name"], tc.get("arguments", {})
            if (
                name in SCREEN_CAPTURE_TOOLS
                and screen_observations_without_action >= MAX_SCREEN_OBSERVATIONS_WITHOUT_ACTION
            ):
                final = (
                    "Tôi đã chụp nhiều lần nhưng vẫn chưa xác định chắc chắn bước tiếp theo. "
                    "Đã dừng để tránh chụp lặp; chưa thể xác nhận yêu cầu hoàn tất. "
                    "Cần mô tả rõ hơn mục tiêu hoặc một cách nhận diện UI khác."
                )
                log.append({"step": step, "tool": name, "args": args, "obs": "blocked: screenshot limit"})
                return {"final": final, "steps": step, "log": log}
            if verbose:
                print(f"action: {name}({str(args)[:300]})")
            obs = registry.execute(name, args)
            is_image = isinstance(obs, dict) and obs.get("kind") == "image"
            if is_image and name in SCREEN_CAPTURE_TOOLS:
                screen_observations_without_action += 1
            elif (
                name in GUI_ACTION_TOOLS
                and isinstance(obs, str)
                and not obs.startswith("ERROR")
                and obs != "No text to type."
            ):
                screen_observations_without_action = 0
                for index, _ in image_history:
                    _omit_image(messages[index])
                image_history.clear()
            if verbose:
                if is_image:
                    print(
                        f"observation: <image "
                        f"{obs['width']}x{obs['height']} "
                        f"{obs['mime_type']}>"
                    )
                else:
                    print(f"observation: {obs[:800]}")
            if is_image:
                # Keep image logs small; the base64 payload is still sent to the model below.
                log_obs = {
                    key: obs[key]
                    for key in (
                        "kind", "mime_type", "width", "height", "origin_x", "origin_y",
                        "desktop_width", "desktop_height",
                    )
                    if key in obs
                }
            else:
                log_obs = obs
            log.append({"step": step, "tool": name, "args": args, "obs": log_obs})
            messages.append({"role": "assistant", "content": content or "", "tool_calls": [
                {"id": tc.get("id", f"s{step}"), "type": "function",
                 "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}
            ]})
            call_id = tc.get("id", f"s{step}")
            if is_image:
                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps({"ok": True, "image": log_obs}),
                })
                if all(
                    key in obs
                    for key in ("origin_x", "origin_y", "desktop_width", "desktop_height")
                ):
                    image_note = (
                        f"Ảnh này bắt đầu ở tọa độ desktop ({obs['origin_x']}, "
                        f"{obs['origin_y']}), kích thước {obs['width']}x{obs['height']}. "
                        f"Desktop đầy đủ là {obs['desktop_width']}x{obs['desktop_height']}. "
                        "click dùng tọa độ desktop: cộng tọa độ gốc này với vị trí trong ảnh crop."
                    )
                else:
                    image_note = (
                        "Ảnh từ file không có ánh xạ tọa độ desktop; "
                        "đừng dùng tọa độ trong ảnh để click nếu chưa biết vị trí ảnh trên màn hình."
                    )
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": image_note,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    f"data:{obs['mime_type']};base64,"
                                    f"{obs['base64']}"
                                )
                            }
                        }
                    ]
                })
                image_history.append((len(messages) - 1, name))
                image_history = _compact_images(messages, image_history)
            else:
                messages.append({"role": "tool", "tool_call_id": tc.get("id", f"s{step}"), "content": obs})
    return {"final": "Dừng vì quá max_steps.", "steps": max_steps, "log": log}
