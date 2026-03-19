# GUI Refactor Guide

## Mục tiêu

GUI hiện tại đang dùng model cũ:

- `GameState`
- `CardData`
- `DragInfo`
- `pick_cards()`
- `apply_drop()`
- `cancel_drag()`

Core mới đã chuyển sang:

- `State`
- `Card`
- `rules.py`
- `FreeCellGame`

Vì vậy GUI cần refactor để dùng đúng core mới, tránh giữ 2 hệ dữ liệu song song.

## Kết luận ngắn

Hướng nên làm:

- GUI chỉ render dữ liệu từ `FreeCellGame.get_view_model()`
- Khi user drag/drop hoặc click, GUI gọi `FreeCellGame.try_move(...)`
- Không tự viết luật ở phía GUI
- Không mutate trực tiếp `cascades`, `free_cells`, `foundations`

## 1. API mới cần dùng

Import chính:

```python
from Source.core import FreeCellGame, rules
from Source.core.state import State, Card
from Source.core.rules import Move
```

Nếu GUI muốn đơn giản nhất thì chỉ cần:

```python
from Source.core import FreeCellGame
```

## 2. Mapping từ model cũ sang model mới

### Cũ

- `CardData`
- `GameState`
- foundation là danh sách các pile
- GUI tự xử lý `pick/drop`

### Mới

- `Card`
- `State`
- foundation là:

```python
{'H': int, 'D': int, 'C': int, 'S': int}
```

- move hợp lệ do `rules.py` hoặc `FreeCellGame` quyết định

## 3. Cách GUI nên lấy dữ liệu để render

Thay vì đọc trực tiếp object cũ, dùng:

```python
game = FreeCellGame(seed=1)
view_model = game.get_view_model()
```

`view_model` trả về:

```python
{
    "cascades": [...],
    "free_cells": [...],
    "foundations": {"H": 0, "D": 0, "C": 0, "S": 0},
    "is_goal": False,
    "legal_moves": [...],
}
```

### Card payload cho GUI

Mỗi lá bài có dạng:

```python
{
    "rank": 1,
    "suit": "H",
    "color": "red",
    "label": "AH"
}
```

GUI chỉ cần dùng:

- `rank`
- `suit`
- `color`
- `label`

## 4. Cách xử lý drag/drop

### Cách cũ

GUI đang làm kiểu:

- pick card
- giữ drag state nội bộ
- tự xác định target
- gọi `apply_drop()`

### Cách mới

GUI vẫn có thể giữ drag state để phục vụ animation và UX, nhưng khi thả bài:

- xác định `src_type`, `src_index`
- xác định `dst_type`, `dst_index`
- nếu là kéo chuỗi thì có thêm `count`
- gọi:

```python
result = game.try_move(src_type, src_index, dst_type, dst_index, count)
```

Nếu:

- `result.ok == True`: cập nhật lại `view_model = game.get_view_model()`
- `result.ok == False`: trả lá bài về vị trí cũ

## 5. Mapping vị trí nguồn/đích

Quy ước nên dùng thống nhất:

- cascade: `("cascade", col_index)`
- free cell: `("free_cell", cell_index)`
- foundation: `("foundation", suit)`

Ví dụ:

```python
result = game.try_move("cascade", 0, "free_cell", 2)
result = game.try_move("free_cell", 1, "cascade", 4)
result = game.try_move("cascade", 3, "foundation", "H")
result = game.try_move("cascade", 2, "cascade", 5, count=3)
```

## 6. Các file GUI cần refactor trước

### `Source/gui/interface.py`

Hiện đang phụ thuộc:

- `CardData`
- `DragInfo`
- `GameState`

Cần đổi sang:

- render từ `view_model`
- hoặc tối thiểu render từ `State`

Khuyến nghị:

- `BoardRenderer` nhận `FreeCellGame` hoặc `view_model`
- không giữ logic game bên trong renderer

### `Source/gui/app.py`

Hiện đang phụ thuộc:

- `GameState()`
- `reset()`
- `clone()`
- `is_won()`
- `has_any_legal_move()`
- `pick_cards()`
- `apply_drop()`
- `cancel_drag()`

Cần đổi sang:

- `self.game = FreeCellGame(seed=...)`
- `self.view_model = self.game.get_view_model()`
- `self.game.try_move(...)`
- `self.game.auto_move_to_foundation()` nếu cần
- `rules.is_goal(self.game.get_state())` nếu cần check trực tiếp

### `Source/gui/animation.py`

Hiện đang animate theo `GameState`

Cần đổi sang:

- animate theo `State`
- hoặc animate theo `view_model`

Khuyến nghị:

- solver trả `List[State]`
- animator chỉ cần so sánh vị trí card giữa 2 `State`

### `Source/core/loader.py`

Hiện loader đang tạo `CardData` kiểu cũ

Cần đổi sang:

- parse thành `Card`
- tạo `State`
- hoặc `FreeCellGame.set_state(...)`

Ngoài ra cần đổi suit:

- từ `clubs/diamonds/hearts/spades`
- sang `C/D/H/S`

## 7. Cách refactor an toàn theo từng bước

### Bước 1

Refactor `app.py` để tạo:

```python
self.game = FreeCellGame(seed=1)
self.view_model = self.game.get_view_model()
```

### Bước 2

Refactor `BoardRenderer` để render từ `view_model` thay vì `GameState`

### Bước 3

Khi drag/drop xong, gọi:

```python
result = self.game.try_move(...)
if result.ok:
    self.view_model = self.game.get_view_model()
```

### Bước 4

Đổi toàn bộ check win/stuck:

- win: `self.view_model["is_goal"]`
- legal moves: `self.view_model["legal_moves"]`

### Bước 5

Refactor loader để trả về `State`

### Bước 6

Refactor animator để dùng `State`

## 8. Những gì GUI không nên làm nữa

- Không tự kiểm tra luật xếp bài riêng
- Không tự quyết định foundation hợp lệ riêng
- Không mutate trực tiếp state
- Không giữ một `GameState` custom khác với core

## 9. Mẫu flow mới

```python
game = FreeCellGame(seed=1)
view_model = game.get_view_model()

# render view_model

result = game.try_move("cascade", 0, "free_cell", 0)
if result.ok:
    view_model = game.get_view_model()
else:
    # snap card back
    pass
```

## 10. Khuyến nghị kiến trúc

Nên chia GUI thành 3 lớp:

- `FreeCellGame`:
  - giữ logic game

- `App/controller`:
  - nhận input từ user
  - gọi `game.try_move(...)`
  - cập nhật view model

- `BoardRenderer`:
  - chỉ vẽ
  - không chứa luật

## 11. Ưu tiên thực hiện

Thứ tự nên làm:

1. Refactor `app.py`
2. Refactor `interface.py`
3. Refactor `loader.py`
4. Refactor `animation.py`
5. Dọn các class cũ như `GameState`, `CardData`, `DragInfo`

## 12. Kết luận

GUI hiện tại chưa tương thích với core mới.

Muốn hệ thống ổn định về sau, GUI nên chuyển sang dùng `FreeCellGame` làm điểm vào chính.

Như vậy:

- frontend chỉ tập trung render
- controller chỉ tập trung nhận input
- toàn bộ luật chơi nằm ở core
