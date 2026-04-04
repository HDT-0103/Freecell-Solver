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

## 📖 **Giới Thiệu**

**FreeCell Solver** là ứng dụng giải trò chơi bài **FreeCell** tự động sử dụng các thuật toán tìm kiếm Trí Tuệ Nhân Tạo. Dự án được phát triển nhằm minh họa và so sánh hiệu suất thực tế của các thuật toán tìm kiếm kinh điển trong môi trường bài toán có không gian trạng thái lớn.

### 🎯 **Mục tiêu dự án**

- **Giao Diện Trực Quan:** Chơi FreeCell với GUI Pygame thân thiện, bắt mắt
- **Giải Tự Động bằng AI:** Áp dụng 4 thuật toán tìm kiếm để tự động giải ván bài
- **So Sánh Hiệu Suất:** Benchmark và trực quan hoá kết quả giữa các thuật toán
- **Thống Kê Chi Tiết:** Theo dõi số bước, thời gian, bộ nhớ, số trạng thái đã duyệt

---

## ✨ **Tính Năng Chính**

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

## 📊 **Tiêu chí đánh giá**

Các thuật toán được đo lường và so sánh theo 4 tiêu chí:

```
Thời gian thực thi        —  Tốc độ tìm lời giải
Bộ nhớ sử dụng (MB)       —  Tài nguyên tiêu thụ
Số trạng thái đã duyệt    —  Mức độ khám phá không gian
Độ dài lời giải (số bước) —  Chất lượng lời giải tìm được
```
Xem video demo các thuật toán hoạt động thực tế: https://www.youtube.com/watch?v=Otm58rCn6DY
---

## 🛠️ **Công Nghệ Sử Dụng**

| Thư Viện | Mục Đích |
|----------|----------|
| **Python 3.8+** | Ngôn ngữ lập trình chính |
| **Pygame** | Giao diện đồ họa game |
| **psutil** | Theo dõi tài nguyên hệ thống (RAM, CPU) |
| **matplotlib** | Vẽ biểu đồ so sánh benchmark |
| **moviepy** | Video intro, outro trong game |
| **pytest** | Framework kiểm thử tự động |

---

## 📦 **Cài đặt**

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

### 1️⃣ Chế Độ GUI — Giao Diện Đồ Họa

```bash
python main.py
```

**Các thao tác trong GUI:**

Menu chính có 3 lựa chọn:

- **Góc trái màn hình** — Xem hướng dẫn luật chơi (Instructions)
- **Manual** — Chọn mức độ khó → chọn ván chơi → dùng chuột để di chuyển và chọn quân bài
- **AI Solver** — Chọn thuật toán → đợi giải xong → nhấn **nút Play** để bắt đầu → xem quá trình giải từng bước theo animation

**Chơi Thủ Công (Manual Mode):**

<div align="center">
<img width="700px" src="https://github.com/HDT-0103/Freecell-Solver/raw/main/Source/assets/readme%20gif/manual.gif" alt="Manual Play Demo">
</div>

**Giải Tự Động Bằng AI (AI Solver Mode):**

<div align="center">
<img width="700px" src="https://github.com/HDT-0103/Freecell-Solver/raw/main/Source/assets/readme%20gif/AI%20solver.gif" alt="AI Solver Demo">
</div>

### 2️⃣ Chế Độ Benchmark — So Sánh Thuật Toán

```bash
python main.py --mode benchmark
```

Chế độ này sẽ tự động:
- Chạy tất cả 4 thuật toán trên cùng bộ ván bài
- Thu thập đầy đủ số liệu về thời gian, bộ nhớ, số bước

---

## 🏗️ **Cấu trúc Dự Án**

```
Freecell-Solver/
├── 📄 main.py # Điểm vào của ứng dụng
├── 📄 requirements.txt # Danh sách phụ thuộc
├── 📄 conftest.py # Cấu hình pytest
│
├── 📁 Nguồn/
│ ├── 📁 core/ # Logic cốt lõi của trò chơi
│ │ ├── state.py # Định nghĩa trạng thái game
│ │ ├── rules.py # Luật chơi FreeCell
│ │ ├── game_service.py # Quản lý logic trò chơi
│ │ └── loader.py # Tải cấu hình trò chơi
│   │
│ ├── 📁 solvers/ # Các thuật toán AI
│ │ ├── bfs.py # Tìm kiếm theo chiều rộng đầu tiên
│ │ ├── dfs.py # Tìm kiếm đầu tiên về độ sâu
│ │ ├── ucs.py # Tìm kiếm chi phí thống nhất
│ │ └── a_star.py # Tìm kiếm A-Star
│   │
│ ├── 📁 gui/ # Giao diện người dùng
│ │ ├── app.py # Ứng dụng chính
│ │ ├── interface.py # Giao diện game
│ │ ├── menu.py # Chính Menu
│ │ ├── hud.py # Hiển thị thông tin HUD
│ │ ├── animation.py # Hiệu ứng animation
│ │ └── howto.py # Hướng dẫn sử dụng
│   │
│ ├── 📁 utils/ # Tiện ích
│ │ └── benchmark_runner.py # Chạy & thu thập benchmark
│   │
│ ├── 📁 assets/ # Tài nguyên (hình ảnh, phông chữ...)
│ └── 📄 config.py # Cấu hình ứng dụng
│
└── 📁 kiểm tra/ # Kiểm tra đơn vị
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

## **Giấy Phép**

Dự án này được phát triển cho mục đích **học tập và nghiên cứu** trong khuôn khổ môn học CSC14003 tại Trường Đại học Khoa học Tự nhiên – ĐHQG TP.HCM.

---

<div align="center">

## ⭐ **Nếu dự án hữu ích, hãy cho chúng tôi một ngôi sao!**

---

![Footer](https://readme-typing-svg.demolab.com?font=Fira+Code&weight=500&duration=4000&pause=1000&color=F7A800&center=true&vCenter=true&width=700&lines=Thank+you+for+visiting+our+project!+♠️;Let's+solve+FreeCell+with+AI+together.;BFS+%7C+DFS+%7C+UCS+%7C+A*+—+Which+wins%3F)

</div>