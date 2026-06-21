"""Reusable immediate-ish UI widgets: buttons, text fields, list, helpers."""
from __future__ import annotations

from typing import Callable, List, Optional, Tuple

import pygame

from .. import engine


def draw_text(surface, font, text, color, pos, center=False, right=False):
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = pos
    elif right:
        rect.topright = pos
    else:
        rect.topleft = pos
    surface.blit(img, rect)
    return rect


class Button:
    def __init__(self, rect, label: str, on_click: Callable[[], None],
                 color=engine.PANEL_LIGHT, hover=engine.ACCENT_DIM,
                 text_color=engine.TEXT, font_size=24, enabled=True):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.on_click = on_click
        self.color = color
        self.hover = hover
        self.text_color = text_color
        self.font_size = font_size
        self.enabled = enabled
        self._hovered = False

    def handle_event(self, event) -> bool:
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.on_click()
                return True
        return False

    def draw(self, surface, fonts):
        if not self.enabled:
            bg = engine.PANEL
            tc = engine.TEXT_DIM
        else:
            bg = self.hover if self._hovered else self.color
            tc = self.text_color
        pygame.draw.rect(surface, bg, self.rect, border_radius=10)
        pygame.draw.rect(surface, engine.PANEL, self.rect, width=1, border_radius=10)
        draw_text(surface, fonts.get(self.font_size), self.label, tc,
                  self.rect.center, center=True)


class TextInput:
    def __init__(self, rect, placeholder="", text="", password=False,
                 max_len=40, numeric=False):
        self.rect = pygame.Rect(rect)
        self.placeholder = placeholder
        self.text = text
        self.password = password
        self.max_len = max_len
        self.numeric = numeric
        self.focused = False

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.focused = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.focused:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
                self.focused = False
            elif event.unicode and len(self.text) < self.max_len:
                ch = event.unicode
                if ch.isprintable():
                    if self.numeric and not (ch.isdigit() or ch == "."):
                        return
                    self.text += ch

    def draw(self, surface, fonts):
        border = engine.ACCENT if self.focused else engine.PANEL_LIGHT
        pygame.draw.rect(surface, engine.PANEL, self.rect, border_radius=8)
        pygame.draw.rect(surface, border, self.rect, width=2, border_radius=8)
        font = fonts.get(22)
        shown = ("*" * len(self.text)) if self.password else self.text
        if not shown and not self.focused:
            draw_text(surface, font, self.placeholder, engine.TEXT_DIM,
                      (self.rect.x + 10, self.rect.centery - 11))
        else:
            cursor = "|" if self.focused else ""
            draw_text(surface, font, shown + cursor, engine.TEXT,
                      (self.rect.x + 10, self.rect.centery - 11))


class ListView:
    """Scrollable list of rows; caller draws each row via a render callback."""

    def __init__(self, rect, row_height=46):
        self.rect = pygame.Rect(rect)
        self.row_height = row_height
        self.scroll = 0
        self.items: List = []
        self.selected: Optional[int] = None
        self.on_select: Optional[Callable[[int], None]] = None

    def set_items(self, items: List) -> None:
        self.items = items
        self.scroll = max(0, min(self.scroll, self._max_scroll()))

    def _max_scroll(self) -> int:
        total = len(self.items) * self.row_height
        return max(0, total - self.rect.height)

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            if self.rect.collidepoint(mx, my):
                self.scroll = max(0, min(self.scroll - event.y * 40, self._max_scroll()))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                idx = (event.pos[1] - self.rect.y + self.scroll) // self.row_height
                if 0 <= idx < len(self.items):
                    self.selected = int(idx)
                    if self.on_select:
                        self.on_select(self.selected)

    def draw(self, surface, fonts, render_row: Callable):
        prev_clip = surface.get_clip()
        surface.set_clip(self.rect)
        for i, item in enumerate(self.items):
            y = self.rect.y + i * self.row_height - self.scroll
            if y + self.row_height < self.rect.y or y > self.rect.bottom:
                continue
            row_rect = pygame.Rect(self.rect.x, y, self.rect.width, self.row_height - 4)
            selected = (i == self.selected)
            bg = engine.ACCENT_DIM if selected else engine.PANEL
            pygame.draw.rect(surface, bg, row_rect, border_radius=8)
            render_row(surface, fonts, item, row_rect, i, selected)
        surface.set_clip(prev_clip)


def panel(surface, rect, color=engine.PANEL):
    pygame.draw.rect(surface, color, rect, border_radius=12)


def header(surface, fonts, title: str, subtitle: str = "") -> None:
    draw_text(surface, fonts.get(40, bold=True), title, engine.TEXT, (40, 28))
    if subtitle:
        draw_text(surface, fonts.get(20), subtitle, engine.TEXT_DIM, (42, 76))
