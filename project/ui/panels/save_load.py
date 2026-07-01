from __future__ import annotations

import time
from typing import TYPE_CHECKING, Callable

import pygame
from enums import NotificationTypeEnum
from save_load.models import SaveSlotInfo
from settings import HEIGHT, MAX_SAVE_SLOTS, WIDTH

from .. import theme
from ..widget import Widget
from ..widgets import Button, Label

if TYPE_CHECKING:
    from game import Game
    from scene import Scene
    from state import State as _StateT

    from .hud import HUD

_PAD = 20
_GAP = 10
_BUTTON_SIZE = 28


def _format_timestamp(ts: float) -> str:
    t = time.localtime(ts)
    return f"{t.tm_year}-{t.tm_mon:02d}-{t.tm_mday:02d} {t.tm_hour:02d}:{t.tm_min:02d}"


def _format_playtime(secs: float) -> str:
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    return f"{h}h {m:02d}m"


class _SlotButton:
    def __init__(self, idx: int, info: SaveSlotInfo | None, rect: pygame.Rect) -> None:
        self.idx = idx
        self.info = info
        self.rect = rect
        self.occupied = info is not None and info.is_occupied

    @property
    def label(self) -> str:
        if not self.occupied or self.info is None or self.info.metadata is None:
            return f"Slot {self.idx + 1} — Empty"
        m = self.info.metadata
        name = m.slot_name or f"Slot {self.idx + 1}"
        return f"{name}  |  {_format_timestamp(m.timestamp)}  |  {_format_playtime(m.playtime)}"


class SaveLoadPanel(Widget):
    _TITLE = ""

    def __init__(self, scene: Scene, hud: HUD | None = None) -> None:
        super().__init__()
        self.scene = scene
        self.game = scene.game
        self.hud = hud

        self._slots: list[_SlotButton] = []
        self._selected_idx: int = 0
        self._confirm_action: str | None = None
        self._confirm_slot_idx: int = -1
        self._confirm_buttons: list[Button] = []
        self._confirm_selected: int = 0

        self._build_background()
        self._refresh_slots()

    def _build_background(self) -> None:
        bw, bh = 600, 420
        self.bg = theme.nine_patch("nine_patch_04.png", bw, bh)
        self.rect = self.bg.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        self._title_surf = theme.menu_font(32).render(self._TITLE, False, theme.NAME)
        self._close_btn = Label("[X]", size=24)

    def _refresh_slots(self) -> None:
        infos = self.game.save_manager.list_slots()
        self._slots.clear()
        y = self.rect.top + 60
        for i in range(MAX_SAVE_SLOTS):
            slot_rect = pygame.Rect(self.rect.left + _PAD, y, self.rect.width - 2 * _PAD, 30)
            info = infos[i] if i < len(infos) else None
            self._slots.append(_SlotButton(i, info, slot_rect))
            y += 34

    def _confirm_yes(self) -> None:
        if self._confirm_action == "save":
            self._do_save(self._confirm_slot_idx)
        elif self._confirm_action == "load":
            do_load = getattr(self, "_do_load", None)
            if do_load is not None:
                do_load(self._confirm_slot_idx)
        self._confirm_action = None
        self._confirm_slot_idx = -1
        self._refresh_slots()

    def _confirm_no(self) -> None:
        self._confirm_action = None
        self._confirm_slot_idx = -1

    def _do_save(self, slot_idx: int) -> None:
        success = self.game.save_manager.save(slot_idx)
        if success:
            self.scene.add_notification("Game saved", NotificationTypeEnum.success)
        self._confirm_action = None
        self._refresh_slots()

    def open(self) -> None:
        self._confirm_action = None
        self._confirm_slot_idx = -1
        self._confirm_selected = 0
        self._selected_idx = 0
        self._refresh_slots()

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self._confirm_action:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    self._confirm_selected = 1 - self._confirm_selected
                    return True
                if event.key == pygame.K_RETURN:
                    self._confirm_buttons[self._confirm_selected].activate()
                    return True
                if event.key == pygame.K_ESCAPE:
                    self._confirm_no()
                    return True
            for btn in self._confirm_buttons:
                if btn.handle_event(event):
                    return True
            return False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP and self._slots:
                self._selected_idx = (self._selected_idx - 1) % len(self._slots)
                return True
            if event.key == pygame.K_DOWN and self._slots:
                self._selected_idx = (self._selected_idx + 1) % len(self._slots)
                return True
            if event.key == pygame.K_RETURN and self._slots:
                self._on_slot_click(self._slots[self._selected_idx])
                return True
            if event.key == pygame.K_ESCAPE:
                self.scene.ui.close(type(self))
                return True
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, slot in enumerate(self._slots):
                if slot.rect.collidepoint(event.pos):
                    self._selected_idx = i
                    self._on_slot_click(slot)
                    return True
        return False

    def _on_slot_click(self, slot: _SlotButton) -> None:
        if not slot.occupied:
            self._do_save(slot.idx)
            self._refresh_slots()
        else:
            self._show_confirm("overwrite", slot)

    def _show_confirm(self, action: str, slot: _SlotButton) -> None:
        msg = f"Overwrite save in slot {slot.idx + 1}?" if action == "overwrite" else f"Load slot {slot.idx + 1}?"
        self._confirm_action = "save" if action == "overwrite" else "load"
        self._confirm_slot_idx = slot.idx
        self._confirm_selected = 0
        cx = self.rect.centerx
        cy = self.rect.centery + 40
        self._confirm_buttons = [
            Button("Yes", self._confirm_yes, size=_BUTTON_SIZE),
            Button("No", self._confirm_no, size=_BUTTON_SIZE),
        ]
        for i, btn in enumerate(self._confirm_buttons):
            btn.rect.center = (cx - 60 + i * 120, cy)
        self._confirm_text = msg

    def update(self, dt: float) -> None:
        for btn in self._confirm_buttons:
            btn.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        surface.blit(self.bg, self.rect.topleft)
        if self._title_surf:
            tr = self._title_surf.get_rect(midtop=(self.rect.centerx, self.rect.top + 10))
            surface.blit(self._title_surf, tr)

        for i, slot in enumerate(self._slots):
            color = (200, 180, 140) if slot.occupied else (120, 110, 90)
            bg_color = (50, 48, 42) if i == self._selected_idx else (30, 28, 22)
            pygame.draw.rect(surface, bg_color, slot.rect, border_radius=4)
            if i == self._selected_idx:
                pygame.draw.rect(surface, (120, 100, 60), slot.rect, border_radius=4, width=2)
            sf = theme.menu_font(18).render(slot.label, False, color)
            surface.blit(sf, (slot.rect.left + 8, slot.rect.top + 6))

        if self._confirm_action:
            overlay = pygame.Surface(self.bg.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            surface.blit(overlay, self.rect.topleft)
            cf = theme.menu_font(24).render(self._confirm_text, False, (255, 230, 180))
            surface.blit(cf, cf.get_rect(center=(self.rect.centerx, self.rect.centery)))
            for i, btn in enumerate(self._confirm_buttons):
                btn.selected = i == self._confirm_selected
                btn.draw(surface)


class SavePanel(SaveLoadPanel):
    _TITLE = "Save Game"


class LoadPanel(SaveLoadPanel):
    _TITLE = "Load Game"

    def __init__(self, scene: Scene, hud: HUD | None = None, on_load: Callable[[int], None] | None = None) -> None:
        super().__init__(scene, hud)
        self.on_load = on_load

    def _do_load(self, slot_idx: int) -> None:
        success = self.game.save_manager.load(slot_idx)
        if success:
            self.scene.add_notification("Game loaded", NotificationTypeEnum.info)
            if self.on_load is not None:
                self.on_load(slot_idx)
        self._confirm_action = None

    def _refresh_slots(self) -> None:
        infos = self.game.save_manager.list_slots()
        self._slots.clear()
        y = self.rect.top + 60
        for i in range(MAX_SAVE_SLOTS):
            slot_rect = pygame.Rect(self.rect.left + _PAD, y, self.rect.width - 2 * _PAD, 30)
            info = infos[i] if i < len(infos) else None
            occ = info is not None and info.is_occupied
            if occ:
                self._slots.append(_SlotButton(i, info, slot_rect))
            y += 34

    def _on_slot_click(self, slot: _SlotButton) -> None:
        self._show_confirm("load", slot)


class DeathScreen(Widget):
    def __init__(self, scene: Scene, hud: HUD) -> None:
        super().__init__()
        self.scene = scene
        self.game = scene.game

        bw, bh = 500, 300
        self.bg = theme.nine_patch("nine_patch_12b.png", bw, bh)
        self.rect = self.bg.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        self._title_surf = theme.menu_font(48).render("You Died!", False, (200, 40, 40))
        self._buttons: list[Button] = []
        self._selected_idx: int = 0
        self._build_buttons()

    def _close_state(self) -> None:
        if self.game.states and self.game.states[-1].__class__.__name__ == "DeadState":
            self.game.states[-1].exit_state()

    def _on_restart(self) -> None:
        import scene as scene_mod
        import splash_screen
        self._close_state()
        scene_mod.Scene(self.game, "Village", "start").enter_state()
        splash_screen.SplashScreen(self.game, "GAME OVER").enter_state()

    def _on_load_last(self) -> None:
        slots = self.game.save_manager.list_slots()
        last_idx = -1
        for i, s in enumerate(slots):
            if s is not None and s.is_occupied:
                last_idx = i
        if last_idx >= 0:
            self._close_state()
            self.game.save_manager.load(last_idx) if hasattr(self.game, 'save_manager') else None
        else:
            if self.scene:
                self.scene.add_notification("No save found", NotificationTypeEnum.error)

    def _build_buttons(self) -> None:
        cx = self.rect.centerx
        cy = self.rect.centery + 60
        self._buttons = [
            Button("Load Last Save", self._on_load_last, size=28),
            Button("Restart", self._on_restart, size=28),
        ]
        for i, btn in enumerate(self._buttons):
            btn.rect.center = (cx - 80 + i * 160, cy)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self._selected_idx = 1 - self._selected_idx
                return True
            if event.key == pygame.K_RETURN:
                self._buttons[self._selected_idx].activate()
                return True
            return False
        for btn in self._buttons:
            if btn.handle_event(event):
                return True
        return False

    def update(self, dt: float) -> None:
        for btn in self._buttons:
            btn.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        surface.blit(self.bg, self.rect.topleft)
        tr = self._title_surf.get_rect(midtop=(self.rect.centerx, self.rect.top + 30))
        surface.blit(self._title_surf, tr)
        for i, btn in enumerate(self._buttons):
            btn.selected = i == self._selected_idx
            btn.draw(surface)


from state import State as _State


class DeadState(_State):
    def __init__(self, game: Game) -> None:
        super().__init__(game)
        self.name = "DeadState"
        self._close_me = False
        self._buttons: list[Button] = []
        self._selected_idx: int = 0
        self._title_surf = theme.menu_font(48).render("You Died!", False, (200, 40, 40))
        bg_w, bg_h = 500, 300
        self._bg = theme.nine_patch("nine_patch_12b.png", bg_w, bg_h)
        self._bg_rect = self._bg.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        self._build_buttons()

    def _on_restart(self) -> None:
        import scene as scene_mod
        import splash_screen
        self.exit_state()
        scene_mod.Scene(self.game, "Village", "start").enter_state()
        splash_screen.SplashScreen(self.game, "GAME OVER").enter_state()

    def _on_load_last(self) -> None:
        slots = self.game.save_manager.list_slots()
        last_idx = -1
        for i, s in enumerate(slots):
            if s is not None and s.is_occupied:
                last_idx = i
        if last_idx >= 0:
            self.exit_state()
            self.game.save_manager.load(last_idx)

    def _build_buttons(self) -> None:
        cx = self._bg_rect.centerx
        cy = self._bg_rect.centery + 60
        self._buttons = [
            Button("Load Last Save", self._on_load_last, size=28),
            Button("Restart", self._on_restart, size=28),
        ]
        for i, btn in enumerate(self._buttons):
            btn.rect.center = (cx - 80 + i * 160, cy)

    def update(self, dt: float, events: list[pygame.event.Event]) -> None:
        for btn in self._buttons:
            btn.update(dt)
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    self._selected_idx = 1 - self._selected_idx
                elif event.key == pygame.K_RETURN:
                    self._buttons[self._selected_idx].activate()
            else:
                for btn in self._buttons:
                    btn.handle_event(event)
        for i, btn in enumerate(self._buttons):
            btn.selected = i == self._selected_idx

    def draw(self, screen: pygame.Surface, dt: float) -> None:
        screen.fill((0, 0, 0))
        screen.blit(self._bg, self._bg_rect.topleft)
        tr = self._title_surf.get_rect(midtop=(self._bg_rect.centerx, self._bg_rect.top + 30))
        screen.blit(self._title_surf, tr)
        for btn in self._buttons:
            btn.draw(screen)
