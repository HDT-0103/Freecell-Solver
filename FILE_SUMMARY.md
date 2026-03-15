# FreeCell Solver - File Summary

Tài liệu này tóm tắt ngắn gọn nhiệm vụ của từng file chính trong project.

## Root

- `main.py`: Entrypoint tối giản, khởi tạo `FreeCellApp` và gọi `run()`.
- `README.md`: Mô tả dự án, cách cài đặt/chạy.
- `requirements.txt`: Danh sách thư viện Python cần cài.
- `WORKLOG_SUMMARY.md`: Ghi chú tiến độ/lịch sử công việc.
- `nội dung đồ án.txt`: Tài liệu mô tả đồ án.

## Source/config.py

- `Source/config.py`: Quản lý cấu hình đường dẫn tài nguyên (`CARD_IMAGE_DIR`, `SOLUTION_DIR`) theo dạng linh hoạt theo thư mục project.

## Source/core

- `Source/core/__init__.py`: Đánh dấu package core.
- `Source/core/rules.py`: Luật FreeCell thuần logic (đỏ/đen, xếp cascade, foundation, supermove).
- `Source/core/state.py`: Mô hình trạng thái game (`GameState`, `CardData`, thao tác pick/drop, kiểm tra thắng/thua, clone/hash).
- `Source/core/loader.py`: Logic nạp dữ liệu từ JSON (`load_game_from_json`) và parse token lá bài (`parse_card_token`).

## Source/gui

- `Source/gui/__init__.py`: Đánh dấu package gui.
- `Source/gui/interface.py`: Lớp hiển thị board/card, layout, kéo-thả, đồng bộ vị trí lá bài.
- `Source/gui/animation.py`: Điều khiển animation replay đường đi solver.
- `Source/gui/menu.py`: Vẽ và xử lý sự kiện cho Menu/HowTo, gồm dropdown AI Solver.
- `Source/gui/hud.py`: Vẽ HUD game (metrics solver, overlay thắng/thua, thông điệp).
- `Source/gui/app.py`: Controller trung tâm `FreeCellApp` (game loop, scene switching, threading solver, phối hợp state-renderer-animator).

## Source/solvers

- `Source/solvers/__init__.py`: Đánh dấu package solvers.
- `Source/solvers/ucs.py`: Thuật toán UCS/A*-style đang dùng cho AI Solver (sinh nước đi, heuristic/progress, dựng lại path).
- `Source/solvers/bfs.py`: Placeholder cho BFS (chưa triển khai logic).
- `Source/solvers/dfs.py`: Placeholder cho DFS (chưa triển khai logic).
- `Source/solvers/a_star.py`: Placeholder cho A* riêng (chưa triển khai logic độc lập).

## Source/utils

- `Source/utils/metrics.py`: Đo thời gian/bộ nhớ và thống kê tìm kiếm (`SearchMetrics`, `measure_search`).

## Source/assets

- `Source/assets/images/cards/`: Bộ ảnh lá bài dùng cho giao diện.
- `Source/assets/solution/game_01.json`: Dữ liệu một ván mẫu để load vào game.

## Ghi chú

- Các thư mục `__pycache__/` chỉ chứa bytecode cache của Python, không chứa logic nghiệp vụ.
