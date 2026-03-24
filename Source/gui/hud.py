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
        tip = hint_font.render("You are stuck. Press R to start a new shuffle.", True, (255, 240, 200))
        cx = screen.get_rect().centerx
        cy = screen.get_rect().centery
        screen.blit(lose, (cx - lose.get_width() // 2, cy - lose.get_height() // 2 - 20))
        screen.blit(tip, (cx - tip.get_width() // 2, cy + 30))
