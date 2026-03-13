# FILE NAY DA DUOC CHUYEN SANG:
#   Logic bai    -> Source/core/state.py  (class CardData)
#   Hien thi bai -> Source/gui/interface.py (class CardWidget, CardImageLoader)
#
# File nay khong duoc import nua. Co the xoa an toan.
#
# (Giu lai de tranh loi neu co import cu, nhung se khong co hieu luc.)

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

import pygame


SUITS = ("spades", "hearts", "clubs", "diamonds")
RANKS = tuple(range(1, 14))


def default_image_name(rank: int, suit: str) -> str:
    """Tao ten file anh mac dinh theo dinh dang rank_of_suit.png."""
    rank_map = {
        1: "ace",
        11: "jack",
        12: "queen",
        13: "king",
    }
    rank_text = rank_map.get(rank, str(rank))
    return f"{rank_text}_of_{suit}.png"


@dataclass(frozen=True)
class CardIdentity:
    rank: int
    suit: str


class CardImageLoader:
    """Quan ly cache va nap anh la bai de tranh load lai nhieu lan."""

    def __init__(
        self,
        base_dir: str,
        naming_fn: Optional[Callable[[int, str], str]] = None,
        card_size: Optional[Tuple[int, int]] = None,
    ) -> None:
        self.base_dir = base_dir
        self.naming_fn = naming_fn or default_image_name
        self.card_size = card_size
        self._cache: Dict[Tuple[int, str, Optional[Tuple[int, int]]], pygame.Surface] = {}

    def build_card_path(self, rank: int, suit: str) -> str:
        """Ham rieng de ban co the tuy bien duong dan/ten file de sau nay."""
        file_name = self.naming_fn(rank, suit)
        return os.path.join(self.base_dir, file_name)

    def get_image(self, rank: int, suit: str) -> pygame.Surface:
        key = (rank, suit, self.card_size)
        if key in self._cache:
            return self._cache[key]

        image_path = self.build_card_path(rank, suit)
        if os.path.exists(image_path):
            image = pygame.image.load(image_path).convert_alpha()
            if self.card_size:
                image = pygame.transform.smoothscale(image, self.card_size)
        else:
            image = self._build_fallback_surface(rank, suit)

        self._cache[key] = image
        return image

    def _build_fallback_surface(self, rank: int, suit: str) -> pygame.Surface:
        size = self.card_size or (100, 145)
        surface = pygame.Surface(size, pygame.SRCALPHA)
        rect = surface.get_rect()

        pygame.draw.rect(surface, (255, 255, 255), rect, border_radius=8)
        pygame.draw.rect(surface, (30, 30, 30), rect, width=2, border_radius=8)

        font = pygame.font.SysFont("arial", 22, bold=True)
        color = (200, 0, 0) if suit in ("hearts", "diamonds") else (15, 15, 15)
        label = f"{self._rank_text(rank)} {suit[0].upper()}"
        text = font.render(label, True, color)
        surface.blit(text, (8, 8))
        return surface

    @staticmethod
    def _rank_text(rank: int) -> str:
        rank_map = {1: "A", 11: "J", 12: "Q", 13: "K"}
        return rank_map.get(rank, str(rank))


class Card(pygame.sprite.Sprite):
    """Doi tuong 1 la bai trong game."""

    def __init__(self, rank: int, suit: str, image_loader: CardImageLoader) -> None:
        super().__init__()
        self.identity = CardIdentity(rank=rank, suit=suit)
        self.image = image_loader.get_image(rank, suit)
        self.rect = self.image.get_rect()

    @property
    def rank(self) -> int:
        return self.identity.rank

    @property
    def suit(self) -> str:
        return self.identity.suit

    @property
    def is_red(self) -> bool:
        return self.suit in ("hearts", "diamonds")

    def can_stack_on(self, other: "Card") -> bool:
        """Dung cho cascade: khac mau va be hon 1 don vi."""
        return self.is_red != other.is_red and self.rank + 1 == other.rank

    def move_to(self, x: int, y: int) -> None:
        self.rect.topleft = (x, y)
