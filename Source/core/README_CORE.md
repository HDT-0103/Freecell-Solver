# Core Guide

## Mục tiêu

`Source/core/` là tầng xương sống cho toàn bộ game FreeCell solver.

Thiết kế hiện tại chia rõ trách nhiệm:
- `state.py`: mô hình dữ liệu và khởi tạo bàn
- `rules.py`: luật chơi, kiểm tra nước đi và sinh state mới
- `game_service.py`: facade đơn giản cho GUI/controller

Mục tiêu của cách tách này:
- GUI chỉ cần đọc `State` để render
- Controller chỉ cần giữ `current_state` và gọi `rules`
- Solver chỉ cần dùng `rules.get_next_states(state)` và `rules.is_goal(state)`
- Utilities không phải tự viết lại logic bài / move

## 1. `state.py`

Import:

```python
from Source.core.state import Card, State
```

`state.py` chịu trách nhiệm cho:
- `Card`
- `State`
- `State.build_standard_deck()`
- `State.microsoft_shuffle(seed)`

### `Card`

- `rank`: `1..13`
- `suit`: `H`, `D`, `C`, `S`
- `color`: property suy ra từ suit
- là immutable object, có thể dùng an toàn trong set/dict

Ví dụ:

```python
card = Card(1, 'H')   # Ace of Hearts
print(card.color)     # red
```

### `State`

`State` chứa đúng 3 phần dữ liệu game:
- `cascades`: 8 cột bài
- `free_cells`: 4 ô tạm
- `foundations`: `{'H': int, 'D': int, 'C': int, 'S': int}`

Ngoài ra còn có metadata cho solver:
- `parent`
- `move`
- `g`
- `h`

### Helper có sẵn trong `State`

- `clone()`: copy state hiện tại
- `iter_cards()`: duyệt toàn bộ card đang nằm trong cascades/free cells
- `as_key()`: biểu diễn immutable để deduplicate state
- `get_hash()`: hash của state

### Khởi tạo bàn từ seed

```python
state = State.microsoft_shuffle(1)
```

Đảm bảo:
- đủ 52 lá
- chia cột theo `7, 7, 7, 7, 6, 6, 6, 6`
- cùng seed cho cùng một bàn

## 2. `rules.py`

Import:

```python
from Source.core import rules
from Source.core.rules import Move
```

`rules.py` là nơi duy nhất nên chứa gameplay logic.

### Kiểu dữ liệu `Move`

`Move` mô tả một nước đi chuẩn:
- `src_type`
- `src_index`
- `dst_type`
- `dst_index`
- `count`

Ví dụ:

```python
Move('cascade', 0, 'foundation', 'H')
Move('cascade', 3, 'cascade', 5, count=2)
```

### API chính trong `rules.py`

- `is_goal(state)`
- `get_max_move_size(state, moving_to_empty_stack=False)`
- `can_move_to_foundation(card, foundations)`
- `can_place_on_cascade(card, cascade)`
- `is_valid_sequence(cards)`
- `get_movable_sequence_lengths(cascade)`
- `is_legal_move(state, move)`
- `enumerate_legal_moves(state)`
- `apply_move(state, move)`
- `get_next_states(state)`

### Mẫu dùng cho controller / solver

```python
state = State.microsoft_shuffle(1)
moves = rules.enumerate_legal_moves(state)

for move in moves:
    next_state = rules.apply_move(state, move)
    if rules.is_goal(next_state):
        print("Solved")
```

## 3. Hướng dẫn cho từng nhóm

### GUI

- Chỉ đọc `State` để render
- Không tự giữ một bộ luật riêng
- Khi user click/drag, gửi action cho controller
- Controller hoặc rule layer sẽ gọi `rules.is_legal_move(...)` / `rules.apply_move(...)`

Nếu muốn GUI gần như chỉ xử lý hiển thị, dùng trực tiếp `FreeCellGame`:

```python
from Source.core import FreeCellGame

game = FreeCellGame(seed=1)
view_model = game.get_view_model()

result = game.try_move('cascade', 0, 'foundation', 'H')
if result.ok:
    view_model = game.get_view_model()
```

`get_view_model()` trả về dict sẵn cho frontend:
- `cascades`
- `free_cells`
- `foundations`
- `is_goal`
- `legal_moves`

`try_move(...)` trả về `ActionResult`:
- `ok`
- `state`
- `message`
- `move`
- `game_won`

### Logic di chuyển

- Viết trong `rules.py`
- Không đưa gameplay logic vào `State`
- Mọi move hợp lệ nên đi qua `Move` + `apply_move`
- Không mutate trực tiếp state cũ

### Controller

- Giữ `current_state`
- Chuyển input của người dùng thành `Move`
- Gọi `rules.is_legal_move(current_state, move)`
- Nếu hợp lệ thì `current_state = rules.apply_move(current_state, move)`
- Sau đó cập nhật GUI

Hoặc đơn giản hơn, controller chỉ wrap `FreeCellGame`:
- `game.get_view_model()`
- `game.try_move(...)`
- `game.auto_move_to_foundation()`

### Solver

- Dùng `rules.get_next_states(state)` để mở rộng node
- Dùng `rules.enumerate_legal_moves(state)` nếu muốn tách move và state generation
- Dùng `rules.is_goal(state)` để kiểm tra đích
- Dùng `state.as_key()` hoặc `state.get_hash()` để lưu visited

### Utilities / Debug

- Dùng `state.iter_cards()` để đếm bài hoặc kiểm tra trùng lặp
- Dùng `repr(state)` để log nhanh
- Dùng `Move` để lưu lịch sử nước đi rõ ràng hơn tuple rời rạc

## 4. Quy ước nên giữ lâu dài

- `State` là data container, không chứa gameplay rules
- `rules` là nơi duy nhất quyết định move nào hợp lệ
- `apply_move` luôn trả về state mới
- Các module khác không mutate trực tiếp `cascades`, `free_cells`, `foundations`
- Khi thêm field mới vào `State`, phải kiểm tra lại `clone()`, `as_key()`, test và solver integration

## 5. Test

Chạy toàn bộ test core:

```bash
python3 -m pytest tests/test_state.py tests/test_rules.py tests/test_game_service.py
```

Hoặc chạy toàn bộ repo:

```bash
python3 -m pytest tests
```
