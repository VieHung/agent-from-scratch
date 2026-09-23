"""Tool registry: đăng ký, export OpenAI schema, execute."""
import traceback


class ToolRegistry:
    def __init__(self):
        self._tools = {}  # name -> {"desc":..., "params":..., "fn":...}

    def register(self, name, description, parameters, fn):
        self._tools[name] = {"description": description, "parameters": parameters, "fn": fn}

    def schema(self):
        out = []
        for name, t in self._tools.items():
            out.append({
                "type": "function",
                "function": {"name": name, "description": t["description"], "parameters": t["parameters"]},
            })
        return out

    def execute(self, name, arguments):
        if name not in self._tools:
            return f"ERROR: unknown tool '{name}'. Available: {list(self._tools)}"
        try:
            return str(self._tools[name]["fn"](** (arguments or {})))
        except Exception as e:
            return f"ERROR executing {name}: {e}\n{traceback.format_exc(limit=3)}"

    def names(self):
        return list(self._tools.keys())
