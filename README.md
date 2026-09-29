# Agent From Scratch — Coding + Computer-Use trên Ubuntu

Mục tiêu: học bản chất agent bằng Python thuần, không framework.
Aim: multi-agent có khả năng coding và điều khiển máy Linux/Ubuntu.

## Cấu trúc

```
agent-from-scratch/
├── core/               # Phase 0: ReAct loop + LLM wrapper + registry
│   ├── llm.py          # OpenAI-compatible client + Mock mode để học offline
│   ├── registry.py     # Đăng ký tool, execute, export schema
│   └── loop.py         # ReAct loop: thought -> tool -> observation
├── tools/              # Phase 1-3: năng lực của agent
│   ├── bash_tool.py    # Chạy shell an toàn (timeout, blacklist)
│   ├── file_tool.py    # read/write/edit/glob/grep
│   └── computer_tool.py# STUB Phase 3: screenshot/click/key (Ubuntu X11)
├── agents/             # Phase 4: multi-agent
│   ├── base.py         # BaseAgent
│   ├── coder.py        # Coder system prompt
│   ├── planner.py      # Planner: chia task
│   └── reviewer.py     # Reviewer: soi lỗi
├── memory/             # Phase 5: placeholder history/vector
├── sandbox/            # Phase 2: Docker Ubuntu để chạy agent an toàn
├── evals/              # Phase 6: task regression
├── tests/              # smoke test/ không cần API key
├── main.py             # entrypoint CLI
└── config.yaml
```

## Chạy nhanh (không cần API key)

```bash
python3 main.py --task "tạo file hello.py in ra hello agent" --mock
python3 -m tests.test_smoke
```

## Chạy thật (cần key)

```bash
cp .env.example .env  # điền LLM_API_KEY, LLM_MODEL, LLM_BASE_URL
pip install -r requirements.txt
python3 main.py --task "liệt kê file trong thư mục này"
```

Chạy tool `bash` trong Docker sandbox (cần Docker daemon hoạt động):

```bash
python3 main.py --task "liệt kê file trong thư mục này" --sandbox
```

Lệnh shell chạy trong container không có mạng; workspace được mount để agent đọc/ghi file.
Có thể bật mặc định bằng `sandbox.enabled: true` trong `config.yaml`.

## Roadmap

- [x] Phase 0: ReAct loop
- [x] Phase 1: coding tools (bash/file)
- [x] Phase 2: sandbox Docker (xem sandbox/)
- [ ] Phase 3: computer-use (hoàn thiện tools/computer_tool.py)
- [ ] Phase 4: multi-agent (planner/coder/reviewer)
- [ ] Phase 5: memory RAG codebase
- [ ] Phase 6: eval set

> An toàn: đừng cho agent sudo trên máy chính. Test computer-use trong VM.
