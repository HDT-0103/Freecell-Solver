<div align="center">

# ♠️ **FREECELL SOLVER**
### *AI-Powered FreeCell Game Solver — Giải FreeCell Bằng Trí Tuệ Nhân Tạo*

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Pygame](https://img.shields.io/badge/Pygame-2.0+-00B140?logo=pygame&logoColor=white)](https://pygame.org)
[![AI](https://img.shields.io/badge/AI-Search%20Algorithms-FF6B35?logo=artificial-intelligence)](https://en.wikipedia.org/wiki/Search_algorithm)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status](https://img.shields.io/badge/Status-Complete-success)](https://github.com)

---

### **ĐẠI HỌC QUỐC GIA TP.HCM**
### **ĐẠI HỌC KHOA HỌC TỰ NHIÊN**
### **KHOA CÔNG NGHỆ THÔNG TIN**

**Môn học:** CSC14003 – Cơ Sở Trí Tuệ Nhân Tạo  
**Năm học:** 2024 – 2025

---

### **NHÓM SINH VIÊN THỰC HIỆN**

| MSSV | Họ và Tên | Vai Trò |
|------|-----------|---------|
| 24127254 | Hồ Đình Trí | Leader |
| 24127226 | Phạm Trần Anh Quân | Member |
| 24127252 | Nguyễn Khánh Toàn | Member |
| 24127337 | Nguyễn Tiến Cường | Member |

---

![FreeCell Solver Banner](https://readme-typing-svg.demolab.com?font=Fira+Code&weight=700&size=22&duration=3000&pause=800&color=F7A800&center=true&vCenter=true&width=700&lines=♠️+FreeCell+Solver+with+AI;BFS+%7C+DFS+%7C+UCS+%7C+A*+Search;Giải+tự+động+bằng+Trí+Tuệ+Nhân+Tạo!;So+sánh+hiệu+suất+thuật+toán+thực+chiến!)

<br>

<img width="700px" src="https://github.com/HDT-0103/Freecell-Solver/raw/main/Source/assets/readme%20gif/menu.gif" alt="Menu Demo">

</div>

---

## **Giới Thiệu**

**FreeCell Solver** là ứng dụng giải trò chơi bài **FreeCell** tự động sử dụng các thuật toán tìm kiếm Trí Tuệ Nhân Tạo. Dự án được phát triển nhằm minh họa và so sánh hiệu suất thực tế của các thuật toán tìm kiếm kinh điển trong môi trường bài toán có không gian trạng thái lớn.

### **Mục Tiêu Dự Án**

- **Giao Diện Trực Quan:** Chơi FreeCell với GUI Pygame thân thiện, bắt mắt
- **Giải Tự Động bằng AI:** Áp dụng 4 thuật toán tìm kiếm để tự động giải ván bài
- **So Sánh Hiệu Suất:** Benchmark và trực quan hoá kết quả giữa các thuật toán
- **Thống Kê Chi Tiết:** Theo dõi số bước, thời gian, bộ nhớ, số trạng thái đã duyệt

---

## **Tính Năng Chính**

### **Giao Diện Đồ Họa (GUI)**
- Giao diện Pygame trực quan, dễ sử dụng
- Click chuột để di chuyển bài theo luật FreeCell
- Chọn thuật toán AI từ menu và xem quá trình giải từng bước
- Animation mượt mà khi thực hiện nước đi

<div align="center">
<img width="700px" src="https://github.com/HDT-0103/Freecell-Solver/raw/main/Source/assets/readme%20gif/instruction.gif" alt="Instruction Demo">
</div>

### **Giải Tự Động Bằng AI**
- Tích hợp 4 thuật toán tìm kiếm: **BFS, DFS, UCS, A\***
- Tự động xác định trạng thái hợp lệ và sinh nước đi
- Hiển thị lời giải từng bước theo thời gian thực

### **Chế Độ Benchmark**
- Chạy tất cả thuật toán trên cùng bộ dữ liệu
- Thu thập và so sánh: thời gian, bộ nhớ, số trạng thái, độ dài lời giải
- Xuất biểu đồ so sánh bằng **Matplotlib**

### **Unit Tests**
- Bộ test đầy đủ cho từng module: BFS, DFS, A\*, Rules, State
- Dễ dàng mở rộng và kiểm thử thêm

---

## **Các Thuật Toán Tìm Kiếm**

| Thuật Toán | Ký Hiệu | Tối Ưu? | Bộ Nhớ | Đặc Điểm |
|------------|---------|---------|--------|----------|
| Breadth-First Search | **BFS** | ✅ Có | Cao | Tìm lời giải ngắn nhất (số bước ít nhất) |
| Depth-First Search | **DFS** | ❌ Không | Thấp | Nhanh, nhưng không đảm bảo tối ưu |
| Uniform Cost Search | **UCS** | ✅ Có | Trung bình | Tối ưu theo chi phí, tương tự BFS khi đồng giá |
| A\* Search | **A\*** | ✅ Có | Trung bình | **Nhanh nhất** — dùng heuristic dẫn đường |

### Chi Tiết Từng Thuật Toán

#### BFS — Breadth-First Search
> Duyệt theo chiều rộng, đảm bảo tìm lời giải **ngắn nhất** (ít bước nhất). Phù hợp khi cần độ chính xác tuyệt đối, nhưng tốn nhiều bộ nhớ với không gian trạng thái lớn.

#### DFS — Depth-First Search
> Duyệt theo chiều sâu, tiết kiệm bộ nhớ hơn BFS. Không đảm bảo lời giải tối ưu nhưng có thể tìm ra lời giải nhanh trong nhiều tình huống.

#### UCS — Uniform Cost Search
> Mở rộng nút theo chi phí tích lũy thấp nhất. Tương đương BFS khi tất cả bước đi có cùng chi phí, nhưng linh hoạt hơn khi chi phí không đồng nhất.

#### A\* — A-Star Search
> Kết hợp chi phí thực và **hàm heuristic** để ưu tiên các trạng thái tiềm năng nhất. Thường nhanh nhất và hiệu quả nhất trong thực tế.

---

## **Tiêu Chí Đánh Giá**

Các thuật toán được đo lường và so sánh theo 4 tiêu chí:

```
Thời gian thực thi        —  Tốc độ tìm lời giải
Bộ nhớ sử dụng (MB)       —  Tài nguyên tiêu thụ
Số trạng thái đã duyệt    —  Mức độ khám phá không gian
Độ dài lời giải (số bước) —  Chất lượng lời giải tìm được
```

---

## **Công Nghệ Sử Dụng**

| Thư Viện | Mục Đích |
|----------|----------|
| **Python 3.8+** | Ngôn ngữ lập trình chính |
| **Pygame** | Giao diện đồ họa game |
| **psutil** | Theo dõi tài nguyên hệ thống (RAM, CPU) |
| **matplotlib** | Vẽ biểu đồ so sánh benchmark |
| **moviepy** | Xuất video quá trình giải (tùy chọn) |
| **pytest** | Framework kiểm thử tự động |

---

## **Cài Đặt**

### Yêu Cầu Hệ Thống

- **Python 3.8** trở lên
- **pip** (Python package manager)
- Hệ điều hành: Windows / macOS / Linux

### Các Bước Cài Đặt

**BƯỚC 1: Clone Repository**

```bash
git clone <repository-url>
cd Freecell-Solver
```

**BƯỚC 2: Cài đặt Dependencies**

```bash
pip install -r requirements.txt
```

**BƯỚC 3: Chạy ứng dụng**

```bash
python main.py
```

---

## **Hướng Dẫn Sử Dụng**

### 1. Chế Độ GUI — Giao Diện Đồ Họa

```bash
python main.py
# hoặc
python main.py --mode gui
```

**Các thao tác trong GUI:**
- Click chuột để chọn và di chuyển bài
- Chọn thuật toán AI từ menu thả xuống
- Nhấn **Solve** để bắt đầu giải tự động
- Xem quá trình giải từng bước theo animation

**Chơi Thủ Công (Manual Mode):**

<div align="center">
<img width="700px" src="https://github.com/HDT-0103/Freecell-Solver/raw/main/Source/assets/readme%20gif/manual.gif" alt="Manual Play Demo">
</div>

**Giải Tự Động Bằng AI (AI Solver Mode):**

<div align="center">
<img width="700px" src="https://github.com/HDT-0103/Freecell-Solver/raw/main/Source/assets/readme%20gif/AI%20solver.gif" alt="AI Solver Demo">
</div>

### 2. Chế Độ Benchmark — So Sánh Thuật Toán

```bash
python main.py --mode benchmark
```

Chế độ này sẽ tự động:
- Chạy tất cả 4 thuật toán trên cùng bộ ván bài
- Thu thập đầy đủ số liệu về thời gian, bộ nhớ, số bước
- Xuất biểu đồ so sánh trực quan

---

## **Cấu Trúc Dự Án**

```
Freecell-Solver/
├── main.py                    # Entry point của ứng dụng
├── requirements.txt           # Danh sách dependencies
├── conftest.py                # Cấu hình pytest
│
├── Source/
│   ├── core/                  # Logic cốt lõi của trò chơi
│   │   ├── state.py           # Định nghĩa trạng thái game
│   │   ├── rules.py           # Luật chơi FreeCell
│   │   ├── game_service.py    # Quản lý game logic
│   │   └── loader.py          # Load cấu hình game
│   │
│   ├── solvers/               # Các thuật toán AI
│   │   ├── bfs.py             # Breadth-First Search
│   │   ├── dfs.py             # Depth-First Search
│   │   ├── ucs.py             # Uniform Cost Search
│   │   └── a_star.py          # A-Star Search
│   │
│   ├── gui/                   # Giao diện người dùng
│   │   ├── app.py             # Ứng dụng chính
│   │   ├── interface.py       # Giao diện game
│   │   ├── menu.py            # Menu chính
│   │   ├── hud.py             # Hiển thị thông tin HUD
│   │   ├── animation.py       # Hiệu ứng animation
│   │   └── howto.py           # Hướng dẫn sử dụng
│   │
│   ├── utils/                 # Tiện ích
│   │   └── benchmark_runner.py  # Chạy & thu thập benchmark
│   │
│   ├── assets/                # Tài nguyên (hình ảnh, font...)
│   └── config.py              # Cấu hình ứng dụng
│
└── tests/                     # Unit Tests
    ├── test_bfs.py
    ├── test_dfs.py
    ├── test_a_star.py
    ├── test_rules.py
    └── test_state.py
```

---

## **Chạy Tests**

Chạy toàn bộ test suite:

```bash
pytest
```

Chạy test cho một module cụ thể:

```bash
pytest tests/test_bfs.py
pytest tests/test_a_star.py
pytest tests/test_rules.py
```

---

## **Tài Liệu Tham Khảo**

- **Luật chơi FreeCell:** [Wikipedia – FreeCell](https://en.wikipedia.org/wiki/FreeCell)
- **Thuật toán tìm kiếm AI:** *Artificial Intelligence: A Modern Approach* — Russell & Norvig
- **Pygame Documentation:** [pygame.org/docs](https://pygame.org/docs)

---

## **Giấy Phép**

Dự án này được phát triển cho mục đích **học tập và nghiên cứu** trong khuôn khổ môn học CSC14003 tại Trường Đại học Khoa học Tự nhiên – ĐHQG TP.HCM.

---

<div align="center">

## ⭐ **Nếu dự án hữu ích, hãy cho chúng tôi một ngôi sao!**

[Star](https://github.com) | [Report Bug](https://github.com) | [Request Feature](https://github.com)

---

![Footer](https://readme-typing-svg.demolab.com?font=Fira+Code&weight=500&duration=4000&pause=1000&color=F7A800&center=true&vCenter=true&width=700&lines=Thank+you+for+visiting+our+project!+♠️;Let's+solve+FreeCell+with+AI+together.;BFS+%7C+DFS+%7C+UCS+%7C+A*+—+Which+wins%3F)

</div>