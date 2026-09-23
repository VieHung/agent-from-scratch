"""ReAct loop cốt lõi. Đây là file quan trọng nhất Phase 0."""

SYSTEM_PROMPT = """Bạn là coding agent chạy trên Ubuntu.
Luôn suy luận ngắn gọn rồi gọi tool khi cần.
Quy tắc:
- Ưu tiên đọc file trước khi sửa.
- Mọi lệnh shell đi qua tool bash.
- Khi xong việc, trả lời trực tiếp, không gọi thêm tool.
- Không bao giờ chạy lệnh nguy hiểm: rm -rf /, mkfs, dd, shutdown.
"""


def run(task, llm, registry, max_steps=12, verbose=True):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]
    log = []
    for step in range(1, max_steps + 1):
        resp = llm.chat(messages, tools_schema=registry.schema())
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
            if verbose:
                print(f"action: {name}({str(args)[:300]})")
            obs = registry.execute(name, args)
            if verbose:
                print(f"observation: {obs[:800]}")
            log.append({"step": step, "tool": name, "args": args, "obs": obs})
            messages.append({"role": "assistant", "content": content or "", "tool_calls": [
                {"id": tc.get("id", f"s{step}"), "type": "function",
                 "function": {"name": name, "arguments": str(args)}}
            ]})
            messages.append({"role": "tool", "tool_call_id": tc.get("id", f"s{step}"), "content": obs})
    return {"final": "Dừng vì quá max_steps.", "steps": max_steps, "log": log}
