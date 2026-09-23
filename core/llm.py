"""LLM wrapper OpenAI-compatible + Mock mode để học offline."""
import json
import os


class LLMClient:
    def __init__(self, model=None, base_url=None, api_key=None, temperature=0.2, mock=False):
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.temperature = temperature
        self.mock = mock or not self.api_key or self.api_key.startswith("sk-...")
        self._client = None
        self._mock_step = 0
        if not self.mock:
            from openai import OpenAI
            self._client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    def chat(self, messages, tools_schema=None):
        """Return {"content": str, "tool_calls": [{"name":..., "arguments": dict}]}."""
        if self.mock:
            return self._mock_chat(messages)
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools_schema or [],
            tool_choice="auto" if tools_schema else "none",
            temperature=self.temperature,
        )
        msg = resp.choices[0].message
        out = {"content": msg.content or "", "tool_calls": []}
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            out["tool_calls"].append({"name": tc.function.name, "arguments": args, "id": tc.id})
        return out

    def _mock_chat(self, messages):
        """Mock deterministic để demo ReAct mà không tốn key."""
        last = messages[-1].get("content", "") if messages else ""
        self._mock_step += 1
        # Kịch bản demo: step1 gọi bash pwd/ls, step2 trả lời.
        if self._mock_step == 1:
            return {
                "content": "Tôi sẽ kiểm tra thư mục hiện tại.",
                "tool_calls": [{"name": "bash", "arguments": {"command": "pwd && ls"}, "id": "mock1"}],
            }
        if "hello.py" in last.lower() or self._mock_step == 2 and "hello" in str(messages).lower():
            return {
                "content": "Tôi sẽ tạo file hello.py.",
                "tool_calls": [{"name": "write_file", "arguments": {"path": "hello.py", "content": "print('hello agent')\n"}}, {"name": "bash", "arguments": {"command": "python3 hello.py"}}],
                "id": "mock2",
            }
        return {"content": f"Hoàn thành sau {self._mock_step} bước. Observation cuối: {last[:300]}", "tool_calls": []}
