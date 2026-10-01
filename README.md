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
│   └── computer_tool.py# Phase 3: MSS screenshot + xdotool input (X11)
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
- [ ] Phase 3: computer-use X11 trong VM (code đã nối; chờ smoke runtime trong VM). Wayland cần backend portal riêng.
- [ ] Phase 4: multi-agent (planner/coder/reviewer)
- [ ] Phase 5: memory RAG codebase
- [ ] Phase 6: eval set

> An toàn: đừng cho agent sudo trên máy chính. Test computer-use trong VM.

## Phase 3: computer-use trong Ubuntu VM (X11)

Backend hiện tại dùng MSS đọc desktop X11 qua `DISPLAY`, còn `xdotool` gửi click/phím vào cửa sổ đang focus. Chạy chính agent bên trong desktop của VM; không chuyển tiếp `DISPLAY`, `XAUTHORITY` hoặc `/var/run/docker.sock` từ máy host vào container.

Trong Ubuntu VM, cài `xdotool` và Python dependencies:

```bash
sudo apt update
sudo apt install -y python3-venv xdotool
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Mở terminal bên trong desktop VM và kiểm tra session trước khi bật tool:

```bash
printf 'session=%s display=%s wayland=%s\n' "$XDG_SESSION_TYPE" "$DISPLAY" "$WAYLAND_DISPLAY"
xdotool -v
python3 -c 'import mss; print(mss.mss().monitors)'
```

Session cần là `x11` và `DISPLAY` phải có giá trị. Nếu màn hình đăng nhập Ubuntu mặc định vào Wayland, chọn phiên **Ubuntu on Xorg** ở menu phiên đăng nhập. Khởi chạy agent trực tiếp trong VM:

```bash
python3 main.py --no-sandbox --computer-use --task "Chụp màn hình và mô tả cửa sổ đang mở"
```

`--no-sandbox` ở đây giữ Bash trong cùng VM với desktop. Tùy chọn này ghi đè `sandbox.enabled` trong `config.yaml`; computer-use không được đưa vào Docker sandbox vì container đó không tự có quyền desktop.

MSS trên Linux dùng X11 và `$DISPLAY`; nó không phải bộ chụp Wayland. Wayland cần phiên người dùng cấp quyền qua XDG Desktop Portal ScreenCast/RemoteDesktop và PipeWire; khi session Wayland được phát hiện, các tool hiện trả lỗi rõ ràng thay vì điều khiển nhầm XWayland hoặc host. Chỉ đánh dấu Phase 3 hoàn tất sau khi chạy screenshot, click, type và press bên trong VM.
