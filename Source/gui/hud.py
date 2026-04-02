from __future__ import annotations

import pygame

from core import rules
from core.state import State
from typing import Any
from solvers.ucs import UCSSearchResult


def draw_solver_stats(
    screen: pygame.Surface,
    hint_font: pygame.font.Font,
    body_font: pygame.font.Font,
    solver_result,
    solver_name: str = "Solver",
) -> None:
    if solver_result is None:
        return

    # 1. ĐỌC DỮ LIỆU AN TOÀN CHO TẤT CẢ THUẬT TOÁN (Không đụng logic core)
    if hasattr(solver_result, 'metrics'):
        m = solver_result.metrics
        time_str = f"{getattr(m, 'elapsed_seconds', 0.0):.3f} s"
        nodes = getattr(m, 'expanded_nodes', 0)
        steps = getattr(m, 'solution_steps', 0)
        memory = f"{getattr(m, 'peak_memory_mb', 0.0):.2f} MB"
    else:
        time_str = getattr(solver_result, 'elapsed_seconds', "N/A")
        if isinstance(time_str, float): time_str = f"{time_str:.3f} s"
        nodes = getattr(solver_result, 'expanded_nodes', 0)
        steps = len(getattr(solver_result, 'moves', []))
        memory = "N/A"

    lines = [
        "AI Performance Summary",
        f"Time: {time_str}",
        f"Nodes: {nodes}",
        f"Steps: {steps}"
    ]
    if memory != "N/A":
        lines.append(f"Memory: {memory}")

    # 2. CĂN GIỮA VÀ MỞ RỘNG KHUNG CHO THOÁNG
    panel_w, panel_h = 420, 220
    cx = screen.get_rect().centerx
    cy = screen.get_rect().centery + 300 # Đẩy xuống dưới dòng "YOU CLEARED THE BOARD"

    panel = pygame.Rect(cx - panel_w // 2, cy - panel_h // 2, panel_w, panel_h)

    # 3. VẼ NỀN ĐEN MỜ VÀ VIỀN VÀNG SANG TRỌNG
    bg_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    pygame.draw.rect(bg_surf, (14, 10, 5, 200), bg_surf.get_rect(), border_radius=14)
    pygame.draw.rect(bg_surf, (255, 215, 0, 255), bg_surf.get_rect(), width=2, border_radius=14)
    screen.blit(bg_surf, panel.topleft)

    # 4. IN CHỮ CĂN GIỮA BẢNG
    for idx, line in enumerate(lines):
        font = hint_font if idx == 0 else body_font
        color = (255, 215, 0) if idx == 0 else (244, 236, 206)
        text = font.render(line, True, color)
        screen.blit(text, (cx - text.get_width() // 2, panel.y + 20 + idx * 40))


def draw_win_or_lose_overlay(
    screen: pygame.Surface,
    title_font: pygame.font.Font,
    hint_font: pygame.font.Font,
    state: State,
    is_stuck: bool,
) -> None:
    if rules.is_goal(state):
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 95))
        screen.blit(overlay, (0, 0))
        win = title_font.render("YOU WIN!", True, (255, 245, 160))
        cx = screen.get_rect().centerx
        cy = screen.get_rect().centery
        screen.blit(win, (cx - win.get_width() // 2, cy - win.get_height() // 2))
        return

    if is_stuck:
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 95))
        screen.blit(overlay, (0, 0))
        lose = title_font.render("NO MOVES LEFT", True, (255, 210, 150))
        tip = hint_font.render("You are stuck. Press R to restart this deal.", True, (255, 240, 200))
        cx = screen.get_rect().centerx
        cy = screen.get_rect().centery
        screen.blit(lose, (cx - lose.get_width() // 2, cy - lose.get_height() // 2 - 20))
        screen.blit(tip, (cx - tip.get_width() // 2, cy + 30))



def draw_playback_controls(screen, app, center_y, ai_solver_mode, is_solved):
    """
    Vẽ bộ điều khiển Playback tròn với kích thước mới và nút Stop ở góc.
    - << (prev), >> (next): To hơn cũ (radius=40)
    - | | (play_pause): To nhất (radius=50)
    - [Stop]: Góc trái cuối (radius=30)
    """
    if not ai_solver_mode or not is_solved:
        return []

    rects = []
    mp = pygame.mouse.get_pos()
    
    # --- PHẦN 1: CỤM 3 NÚT CHÍNH Ở GIỮA (PREV, PLAY/PAUSE, NEXT) ---
    # Định nghĩa kích thước và icon cho cụm giữa
    mid_buttons = [
        ("prev", "icon_prev.png", 40),       # To hơn cũ
        ("play_pause", "icon_play.png", 50), # To nhất
        ("next", "icon_next.png", 40)        # To hơn cũ
    ]
    
    # Tính toán vị trí bắt đầu để cụm giữa nằm chính xác ở trung tâm màn hình
    gap = 35 # Khoảng cách giữa các nút cụm giữa
    total_width = sum(b[2]*2 for b in mid_buttons) + gap * (len(mid_buttons) - 1)
    current_x = screen.get_width() // 2 - total_width // 2
    
    for btn_type, icon_name, radius in mid_buttons:
        cx = current_x + radius
        cy = center_y # Vị trí Y như cũ (h - 60)
        rect = pygame.Rect(cx - radius, cy - radius, radius * 2, radius * 2)
        rects.append((btn_type, rect))
        
        is_hover = rect.collidepoint(mp)
        
        # 1. Vẽ hiệu ứng Glow (Smartphone Style)
        glow_alpha = 70 if is_hover else 40 # Glow đậm hơn cho nút to
        glow_surf = pygame.Surface((radius*2 + 10, radius*2 + 10), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (255, 255, 255, glow_alpha), (radius+5, radius+5), radius + 5)
        screen.blit(glow_surf, (cx - radius - 5, cy - radius - 5))
        
        # 2. Vẽ viền Gold tròn sang trọng
        pygame.draw.circle(screen, (212, 175, 55), (cx, cy), radius, width=3) # Viền dày hơn
        
        # 3. Vẽ Icon trong suốt (Co giãn theo kích thước radius)
        # Icon của nút to nhất (Play) sẽ là 40x40, nút bên cạnh là 32x32
        icon_size = 40 if btn_type == "play_pause" else 32
        icon = app._load_img(icon_name, scale=(icon_size, icon_size))
        if icon:
            screen.blit(icon, (cx - icon_size//2, cy - icon_size//2))
            
        current_x += radius * 2 + gap # Cập nhật X cho nút tiếp theo

    # --- PHẦN 2: NÚT STOP Ở GÓC TRÁI CUỐI MÀN HÌNH ---
    # Nút Stop giữ kích thước cũ (radius=30) nhưng đổi icon
    stop_radius = 30
    stop_cx = stop_radius + 40 # Cách lề trái 40 pixel
    stop_cy = screen.get_height() - stop_radius - 20 # Cách lề dưới 20 pixel
    stop_rect = pygame.Rect(stop_cx - stop_radius, stop_cy - stop_radius, stop_radius * 2, stop_radius * 2)
    rects.append(("stop_to_algo", stop_rect)) # Đổi tên btn_type để app nhận diện logic mới
    
    stop_is_hover = stop_rect.collidepoint(mp)
    stop_color = (255, 215, 0) if stop_is_hover else (178, 34, 34) # Hover: Gold, Normal: Đỏ đô
    
    # Vẽ nút Stop hình tròn với Icon Home hoặc Stop tùy ý Quan
    pygame.draw.circle(screen, (30, 0, 0, 50), (stop_cx, stop_cy), stop_radius + 4) # Glow đỏ nhẹ
    pygame.draw.circle(screen, stop_color, (stop_cx, stop_cy), stop_radius, width=3)
    
    # Nạp Icon Stop/Home vào giữa
    stop_icon = app._load_img("icon_stop.png", scale=(32, 32)) # Bạn có thể đổi thành icon_home.png nếu muốn
    if stop_icon:
        screen.blit(stop_icon, (stop_cx - 16, stop_cy - 16))
            
    return rects


def draw_fancy_timer(screen: pygame.Surface, font: pygame.font.Font, time_str: str, right_x: int, bottom_y: int):
    """Vẽ đồng hồ với HUD kính mờ, viền vàng kim và icon đồng hồ cơ vẽ tay."""
    padding_x = 20
    padding_y = 10
    icon_size = 22
    gap = 12

    text_surf = font.render(time_str, True, (255, 250, 205)) # Chữ màu kem sang trọng
    
    # Tính toán kích thước tự động co giãn theo text
    width = padding_x * 2 + icon_size + gap + text_surf.get_width()
    height = padding_y * 2 + max(icon_size, text_surf.get_height())
    
    # Căn từ góc phải dưới (bottom right) hất lên
    rect = pygame.Rect(right_x - width, bottom_y - height, width, height)
    
    # 1. Vẽ nền mờ (Glass overlay)
    bg_surf = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.rect(bg_surf, (14, 10, 5, 210), bg_surf.get_rect(), border_radius=12) # Nền Cafe cháy mờ
    
    # 2. Vẽ viền Vàng Gold
    pygame.draw.rect(bg_surf, (212, 175, 55, 255), bg_surf.get_rect(), width=2, border_radius=12)
    
    screen.blit(bg_surf, rect.topleft)
    
    # 3. Vẽ Icon đồng hồ cơ bằng code hình học
    icon_cx = rect.x + padding_x + icon_size // 2
    icon_cy = rect.y + height // 2
    
    # Vỏ đồng hồ
    pygame.draw.circle(screen, (212, 175, 55), (icon_cx, icon_cy), icon_size // 2, width=2)
    # Kim phút (dài, thẳng lên)
    pygame.draw.line(screen, (255, 250, 205), (icon_cx, icon_cy), (icon_cx, icon_cy - 7), width=2)
    # Kim giờ (ngắn, chỉ góc 4 giờ)
    pygame.draw.line(screen, (255, 250, 205), (icon_cx, icon_cy), (icon_cx + 5, icon_cy + 4), width=2)
    # Chốt tâm
    pygame.draw.circle(screen, (255, 250, 205), (icon_cx, icon_cy), 2)
    
    # 4. Vẽ Text số
    text_y = rect.y + height // 2 - text_surf.get_height() // 2
    screen.blit(text_surf, (rect.x + padding_x + icon_size + gap, text_y))