# Báo cáo Refactor: Kiến Trúc Thuần Core Theo GUI_REFACTOR_GUIDE

Tài liệu này tóm tắt kiến trúc sau refactor và mối liên kết giữa các file trong project.

## 1. Mục tiêu kiến trúc

- Dùng `FreeCellGame` + `State/Card/rules.py` làm nguồn logic duy nhất.
- GUI chỉ nhận input, render và gọi API core.
- Không giữ hai hệ model song song trong luồng gameplay chính.

## 2. Flow liên kết file

```text
main.py
  -> Source/gui/app.py (FreeCellApp: controller)
       -> Source/core/game_service.py (FreeCellGame)
       -> Source/core/rules.py (luật di chuyển)
       -> Source/core/loader.py (JSON -> State)
       -> Source/gui/interface.py (BoardRenderer)
       -> Source/gui/animation.py (SolverAnimator)
       -> Source/gui/hud.py (HUD/overlay)
       -> Source/solvers/ucs.py (UCS + hint trên State)
```

## 3. Vai trò từng nhóm file

### 3.1 Controller

- `Source/gui/app.py`
  - Điều phối scene và vòng lặp game.
  - Khởi tạo game qua `FreeCellGame`.
  - Gọi solver/hint và đẩy state vào renderer/animation.

### 3.2 Core gameplay

- `Source/core/game_service.py`
  - Cung cấp API `try_move`, `get_state`, `set_state`, `get_view_model`.

- `Source/core/rules.py`
  - Định nghĩa tính hợp lệ và thực thi move trên `State`.

- `Source/core/state.py`
  - Định nghĩa model `State` và `Card` dùng cho gameplay.

- `Source/core/loader.py`
  - Parse JSON và dựng `State` thuần core để nạp vào `FreeCellGame`.

### 3.3 GUI render/input

- `Source/gui/interface.py`
  - Renderer theo `State`.
  - Kéo/thả chỉ tạo source/target, hợp lệ do `FreeCellGame.try_move` quyết định.

- `Source/gui/animation.py`
  - Animate theo `List[State]`.
  - So sánh vị trí card giữa các snapshot `State`.

- `Source/gui/hud.py`
  - Vẽ thông tin solver và overlay win/lose từ dữ liệu controller (`is_won`, `is_stuck`).

### 3.4 Solver

- `Source/solvers/ucs.py`
  - Tìm đường đi/hint trên `State`.
  - Trả `state_path` dạng `List[State]` để animation phát lại trực tiếp.

## 4. Kết quả refactor

- Luồng gameplay chính đã chuyển sang mô hình core-first.
- App, Renderer, Animation, HUD, Loader và UCS liên kết qua `State/Card` + `FreeCellGame`.
- Không còn cầu nối adapter trong pipeline chính.

## 5. Tóm tắt kiến trúc sau cùng

- **Core** (`state/rules/game_service`) là nguồn chân lý duy nhất cho luật và trạng thái.
- **Controller** (`app.py`) chỉ điều phối và đồng bộ luồng.
- **View** (`interface.py`, `animation.py`, `hud.py`) chỉ render + tương tác.
- **Solver** (`ucs.py`) làm việc trực tiếp trên `State` và trả path dùng được ngay cho animation.