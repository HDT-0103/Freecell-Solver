from __future__ import annotations

import pygame

from core import rules
from core.state import State
from solvers.ucs import UCSSearchResult


def draw_solver_stats(
    screen: pygame.Surface,
    hint_font: pygame.font.Font,
    body_font: pygame.font.Font,
    solver_result: UCSSearchResult | None,
) -> None:
    if solver_result is None:
        return

    metrics = solver_result.metrics
    lines = [
        "UCS Metrics",
        f"Time: {metrics.elapsed_seconds:.3f} s",
        f"Nodes: {metrics.expanded_nodes}",
        f"Memory: {metrics.peak_memory_mb:.2f} MB",
        f"Steps: {metrics.solution_steps}",
    ]

    panel_w, panel_h = 380, 230
    panel = pygame.Rect(screen.get_width() - panel_w - 18, 18, panel_w, panel_h)
    pygame.draw.rect(screen, (14, 46, 26), panel, border_radius=14)
    pygame.draw.rect(screen, (252, 238, 176), panel, width=2, border_radius=14)

    for idx, line in enumerate(lines):
        font = hint_font if idx == 0 else body_font
        color = (255, 246, 188) if idx == 0 else (244, 236, 206)
        text = font.render(line, True, color)
        screen.blit(text, (panel.x + 18, panel.y + 14 + idx * 40))


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
