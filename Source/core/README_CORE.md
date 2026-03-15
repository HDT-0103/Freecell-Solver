# State Handoff Note

File nguồn: [Source/core/state.py]

## `State` dùng để làm gì

`State` là dữ liệu chuẩn của một bàn FreeCell tại một thời điểm. Các module GUI, logic di chuyển, controller, solver và utilities nên dùng chung cấu trúc này.

## Cấu trúc chính

- `cascades`: 8 cột bài, mỗi cột là `list[Card]`
- `free_cells`: 4 ô tạm, mỗi ô là `Card` hoặc `None`
- `foundations`: `{'H': int, 'D': int, 'C': int, 'S': int}`
  - số này là rank cao nhất đã đưa lên foundation của chất đó

## `Card`

- `rank`: `1..13`
- `suit`: `H`, `D`, `C`, `S`
- `color`: tự suy ra là `red` hoặc `black`
- hai lá bài cùng `rank` và `suit` sẽ được xem là bằng nhau

## Cách tạo bàn mới

```python
from Source.core.state import State

state = State.microsoft_shuffle(seed)
```

Hàm này:

- tạo đúng 52 lá
- chia cột theo `7, 7, 7, 7, 6, 6, 6, 6`
- cùng `seed` sẽ ra cùng một bàn

## Dành cho GUI

- Dùng `state` để render trực tiếp.
- `state.cascades[i]` là cột thứ `i`
- `state.free_cells[i]` là ô free cell thứ `i`
- `state.foundations['H']` cho biết foundation cơ đã lên tới đâu
- Không nên sửa trực tiếp dữ liệu trong `state`; GUI chỉ nên gửi action và nhận state mới

## Dành cho logic di chuyển

- Logic move nên đọc từ `cascades`, `free_cells`, `foundations`
- Khi sinh trạng thái mới, nên tạo `State` mới thay vì mutate state cũ
- Có sẵn:
  - `get_next_states()`
  - `get_max_move_size()`
  - `is_goal()`

## Dành cho controller

- Controller có thể giữ `current_state`
- Khi người chơi thao tác:
  1. đọc state hiện tại
  2. kiểm tra nước đi hợp lệ
  3. tạo state mới
  4. cập nhật lại GUI bằng state mới

## Dành cho utilities / solver

- Có thể dùng `state.get_hash()` để lưu visited/closed set
- Hai state giống dữ liệu sẽ được coi là bằng nhau
- `parent`, `move`, `g`, `h` đã có sẵn để phục vụ search

## Lưu ý chung

- Sau khi tạo `State`, dữ liệu đầu vào đã được copy
- Không nên phụ thuộc vào identity của object `Card` hay `State`
- Nếu sau này thêm field mới vào `State`, cần cập nhật lại `__eq__` và `get_hash()`
