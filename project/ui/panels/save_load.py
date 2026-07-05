from __future__ import annotations

import string
import time
from typing import TYPE_CHECKING, Callable

import pygame
from enums import NotificationTypeEnum
from save_load.models import MAX_SLOT_NAME_LEN, SaveSlotInfo
from settings import HEIGHT, MAX_SAVE_SLOTS, WIDTH

from .. import theme
from ..widget import Widget
from ..widgets import Button, Label, TextInput

if TYPE_CHECKING:
    from game import Game
    from scene import Scene
    from state import State as _StateT

    from .hud import HUD

_PAD = 20
_GAP = 10
_BUTTON_SIZE = 28


def _slot_name_char(ch: str) -> bool:
    """Characters allowed in a save-slot name: Latin letters, digits and space.

    Deliberately excludes the hyphen/apostrophe that :class:`CharSet.LATIN` allows and
    any diacritics, per T-021. Sanitization at save time (``sanitize_slot_name``) is the
    real safety net; this predicate just shapes what the player can type.
    """
    return ch in string.ascii_letters or ch in string.digits or ch == " "


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


class _LoadSlotSelector:
    """Reusable occupied-slot list with keyboard/mouse selection and load confirmation."""

    def __init__(
        self,
        game: "Game",
        rect: pygame.Rect,
        on_load: Callable[[int], None],
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        self.game = game
        self.rect = rect
        self.on_load = on_load
        self.on_cancel = on_cancel

        self._slots: list[_SlotButton] = []
        self._selected_idx: int = 0
        self._confirm_action: str | None = None
        self._confirm_slot_idx: int = -1
        self._confirm_selected: int = 0
        self._confirm_buttons: list[Button] = []
        self._confirm_text: str = ""

        self._refresh_slots()

    def _refresh_slots(self) -> None:
        infos = self.game.save_manager.list_slots()
        self._slots.clear()
        y = self.rect.top + 12
        for i in range(MAX_SAVE_SLOTS):
            info = infos[i] if i < len(infos) else None
            occ = info is not None and info.is_occupied
            if occ:
                slot_rect = pygame.Rect(self.rect.left + _PAD, y, self.rect.width - 2 * _PAD, 30)
                self._slots.append(_SlotButton(i, info, slot_rect))
                y += 34
        if self._selected_idx >= len(self._slots):
            self._selected_idx = max(0, len(self._slots) - 1)

    def _show_confirm(self, slot: _SlotButton) -> None:
        self._confirm_action = "load"
        self._confirm_slot_idx = slot.idx
        self._confirm_selected = 0
        self._confirm_text = f"Load slot {slot.idx + 1}?"
        cx = self.rect.centerx
        cy = self.rect.centery
        self._confirm_buttons = [
            Button("Yes", self._confirm_yes, size=_BUTTON_SIZE),
            Button("No", self._confirm_no, size=_BUTTON_SIZE),
        ]
        for i, btn in enumerate(self._confirm_buttons):
            btn.rect.center = (cx - 60 + i * 120, cy)

    def _confirm_yes(self) -> None:
        if self._confirm_action == "load" and self.on_load is not None:
            self.on_load(self._confirm_slot_idx)
        self._confirm_action = None
        self._confirm_slot_idx = -1

    def _confirm_no(self) -> None:
        self._confirm_action = None
        self._confirm_slot_idx = -1

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
                self._show_confirm(self._slots[self._selected_idx])
                return True
            if event.key == pygame.K_ESCAPE:
                if self.on_cancel is not None:
                    self.on_cancel()
                return True
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, slot in enumerate(self._slots):
                if slot.rect.collidepoint(event.pos):
                    self._selected_idx = i
                    self._show_confirm(slot)
                    return True
        return False

    def update(self, dt: float) -> None:
        for btn in self._confirm_buttons:
            btn.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, (30, 28, 22), self.rect, border_radius=4)
        pygame.draw.rect(surface, (80, 70, 55), self.rect, border_radius=4, width=2)

        if not self._slots:
            empty_surf = theme.menu_font(20).render("No saved games found", False, (120, 110, 90))
            surface.blit(empty_surf, empty_surf.get_rect(center=self.rect.center))

        for i, slot in enumerate(self._slots):
            color = (200, 180, 140) if slot.occupied else (120, 110, 90)
            bg_color = (50, 48, 42) if i == self._selected_idx else (30, 28, 22)
            pygame.draw.rect(surface, bg_color, slot.rect, border_radius=4)
            if i == self._selected_idx:
                pygame.draw.rect(surface, (120, 100, 60), slot.rect, border_radius=4, width=2)
            sf = theme.menu_font(18).render(slot.label, False, color)
            surface.blit(sf, (slot.rect.left + 8, slot.rect.top + 6))

        if self._confirm_action:
            overlay = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            surface.blit(overlay, self.rect.topleft)
            cf = theme.menu_font(24).render(self._confirm_text, False, (255, 230, 180))
            surface.blit(cf, cf.get_rect(center=(self.rect.centerx, self.rect.centery)))
            for i, btn in enumerate(self._confirm_buttons):
                btn.selected = i == self._confirm_selected
                btn.draw(surface)


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
        self._confirm_text: str = ""

        # inline rename editor (TextInput) — active only while renaming a slot
        self._editor: TextInput | None = None
        self._editing_slot_idx: int = -1
        # the same physical key that opens the editor (R) also emits a TEXTINPUT "r";
        # swallow that one stray character so it doesn't land in the field
        self._swallow_next_textinput: bool = False

        self._build_background()
        self._refresh_slots()

    def _build_background(self) -> None:
        bw, bh = 600, 420
        self.bg = theme.nine_patch("nine_patch_04.png", bw, bh)
        self.rect = self.bg.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        self._title_surf = theme.menu_font(32).render(self._TITLE, False, theme.NAME)
        self._close_btn = Label("[X]", size=24)

    # header/footer sit inside the 9-patch border; keep the slot list clear of both
    _HEADER_Y = 18
    _FOOTER_Y = 30

    def _list_top(self) -> int:
        return self.rect.top + self._HEADER_Y + self._title_surf.get_height() + 12

    def _refresh_slots(self) -> None:
        infos = self.game.save_manager.list_slots()
        self._slots.clear()
        y = self._list_top()
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
        elif self._confirm_action == "delete":
            self.game.save_manager.delete_slot(self._confirm_slot_idx)
        self._confirm_action = None
        self._confirm_slot_idx = -1
        self._refresh_slots()
        # deleting may shrink the visible list (LoadPanel lists only occupied slots)
        if self._selected_idx >= len(self._slots):
            self._selected_idx = max(0, len(self._slots) - 1)

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
        self._close_editor()
        self._refresh_slots()

    def handle_event(self, event: pygame.event.Event) -> bool:
        # while the rename editor is open it swallows input (Esc cancels, Enter commits)
        if self._editor is not None:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._close_editor()  # cancel: leaves the saved name unchanged
                return True
            if event.type == pygame.TEXTINPUT and self._swallow_next_textinput:
                # drop the stray "r" produced by the same keypress that opened the editor
                self._swallow_next_textinput = False
                return True
            return self._editor.handle_event(event)

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
            if event.key == pygame.K_r and self._slots:
                self._begin_rename(self._slots[self._selected_idx])
                return True
            if event.key in (pygame.K_d, pygame.K_DELETE) and self._slots:
                self._begin_delete(self._slots[self._selected_idx])
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

    #############################################################################################################
    # MARK: rename / delete slot actions

    def _begin_rename(self, slot: _SlotButton) -> None:
        """Open the inline TextInput to rename an occupied slot (no-op for empty slots)."""
        if not slot.occupied or slot.info is None or slot.info.metadata is None:
            return
        editor = TextInput(
            width=360,
            max_length=MAX_SLOT_NAME_LEN,
            predicate=_slot_name_char,
            on_submit=self._commit_rename,
        )
        editor.rect.center = (self.rect.centerx, self.rect.centery)
        editor.set_text(slot.info.metadata.slot_name or f"Slot {slot.idx + 1}")
        editor.set_focus(True)
        self._editor = editor
        self._editing_slot_idx = slot.idx
        self._swallow_next_textinput = True

    def _commit_rename(self, text: str) -> None:
        if self._editing_slot_idx >= 0:
            self.game.save_manager.rename_slot(self._editing_slot_idx, text)
        self._close_editor()
        self._refresh_slots()

    def _close_editor(self) -> None:
        if self._editor is not None:
            self._editor.set_focus(False)
        self._editor = None
        self._editing_slot_idx = -1
        self._swallow_next_textinput = False

    def _begin_delete(self, slot: _SlotButton) -> None:
        """Ask for confirmation before deleting an occupied slot (no-op for empty slots)."""
        if not slot.occupied:
            return
        self._show_confirm("delete", slot)

    def _on_slot_click(self, slot: _SlotButton) -> None:
        if not slot.occupied:
            self._do_save(slot.idx)
            self._refresh_slots()
        else:
            self._show_confirm("overwrite", slot)

    def _show_confirm(self, action: str, slot: _SlotButton) -> None:
        if action == "overwrite":
            self._confirm_action = "save"
            msg = f"Overwrite save in slot {slot.idx + 1}?"
        elif action == "delete":
            self._confirm_action = "delete"
            msg = "Delete this save? This cannot be undone."
        else:
            self._confirm_action = "load"
            msg = f"Load slot {slot.idx + 1}?"
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
        if self._editor is not None:
            self._editor.update(dt)
            # the stray char from the opening keypress (if any) arrives in the same frame
            # as the KEYDOWN, i.e. before this update(); after one frame stop swallowing so
            # the player's real first keystroke is kept.
            self._swallow_next_textinput = False

    def _selected_is_occupied(self) -> bool:
        return bool(self._slots) and self._slots[self._selected_idx].occupied

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        surface.blit(self.bg, self.rect.topleft)
        if self._title_surf:
            tr = self._title_surf.get_rect(midtop=(self.rect.centerx, self.rect.top + self._HEADER_Y))
            surface.blit(self._title_surf, tr)

        for i, slot in enumerate(self._slots):
            color = (200, 180, 140) if slot.occupied else (120, 110, 90)
            bg_color = (50, 48, 42) if i == self._selected_idx else (30, 28, 22)
            pygame.draw.rect(surface, bg_color, slot.rect, border_radius=4)
            if i == self._selected_idx:
                pygame.draw.rect(surface, (120, 100, 60), slot.rect, border_radius=4, width=2)
            sf = theme.menu_font(18).render(slot.label, False, color)
            surface.blit(sf, (slot.rect.left + 8, slot.rect.top + 6))

        # hint for the per-slot actions, shown whenever an occupied slot is selected
        if self._selected_is_occupied() and not self._confirm_action and self._editor is None:
            hint = theme.menu_font(16).render("[R] Rename   [D] Delete", False, (150, 140, 110))
            surface.blit(hint, hint.get_rect(midbottom=(self.rect.centerx, self.rect.bottom - self._FOOTER_Y)))

        if self._editor is not None:
            self._draw_rename_editor(surface)
        elif self._confirm_action:
            overlay = pygame.Surface(self.bg.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            surface.blit(overlay, self.rect.topleft)
            cf = theme.menu_font(24).render(self._confirm_text, False, (255, 230, 180))
            surface.blit(cf, cf.get_rect(center=(self.rect.centerx, self.rect.centery)))
            for i, btn in enumerate(self._confirm_buttons):
                btn.selected = i == self._confirm_selected
                btn.draw(surface)

    def _draw_rename_editor(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(self.bg.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        surface.blit(overlay, self.rect.topleft)
        assert self._editor is not None
        prompt = theme.menu_font(22).render("Rename slot", False, (255, 230, 180))
        surface.blit(prompt, prompt.get_rect(midbottom=(self.rect.centerx, self._editor.rect.top - 12)))
        self._editor.draw(surface)
        hint = theme.menu_font(16).render("Enter = save    Esc = cancel", False, (170, 160, 130))
        surface.blit(hint, hint.get_rect(midtop=(self.rect.centerx, self._editor.rect.bottom + 12)))


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
        y = self._list_top()
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

        bw, bh = 600, 520
        self.bg = theme.nine_patch("nine_patch_12b.png", bw, bh)
        self.rect = self.bg.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        self._title_surf = theme.menu_font(48).render("You Died!", False, (200, 40, 40))

        slot_rect = pygame.Rect(
            self.rect.left + _PAD,
            self.rect.top + 80,
            self.rect.width - 2 * _PAD,
            380,
        )
        self._selector = _LoadSlotSelector(
            self.game,
            slot_rect,
            on_load=self._on_load_slot,
        )

        self._restart_btn = Button("Restart", self._on_restart, size=28)
        self._restart_btn.rect.center = (self.rect.centerx, self.rect.bottom - 40)
        self._focus: str = "slots"

    def _close_state(self) -> None:
        if self.game.states and self.game.states[-1].__class__.__name__ == "DeadState":
            self.game.states[-1].exit_state()
        if self.scene is not None:
            self.scene.ui.close(type(self))

    def _on_restart(self) -> None:
        import scene as scene_mod
        import splash_screen

        self._close_state()
        scene_mod.Scene(self.game, "Village", "start").enter_state()
        splash_screen.SplashScreen(self.game, "GAME OVER").enter_state()

    def _on_load_slot(self, slot_idx: int) -> None:
        if not hasattr(self.game, "save_manager"):
            return
        self._close_state()
        self.game.save_manager.load(slot_idx)

    def _toggle_focus(self) -> None:
        self._focus = "restart" if self._focus == "slots" else "slots"

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self._focus == "slots":
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_TAB, pygame.K_RIGHT):
                self._toggle_focus()
                return True
            if self._selector.handle_event(event):
                return True
        else:
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_TAB, pygame.K_LEFT):
                self._toggle_focus()
                return True
            if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                self._restart_btn.activate()
                return True
            if self._restart_btn.handle_event(event):
                return True
        return False

    def update(self, dt: float) -> None:
        self._selector.update(dt)
        self._restart_btn.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        surface.blit(self.bg, self.rect.topleft)
        tr = self._title_surf.get_rect(midtop=(self.rect.centerx, self.rect.top + 30))
        surface.blit(self._title_surf, tr)

        self._selector.draw(surface)
        self._restart_btn.selected = self._focus == "restart"
        self._restart_btn.draw(surface)


from state import State as _State


class DeadState(_State):
    def __init__(self, game: Game) -> None:
        super().__init__(game)
        self.name = "DeadState"
        self._title_surf = theme.menu_font(48).render("You Died!", False, (200, 40, 40))
        bg_w, bg_h = 600, 520
        self._bg = theme.nine_patch("nine_patch_12b.png", bg_w, bg_h)
        self._bg_rect = self._bg.get_rect(center=(WIDTH // 2, HEIGHT // 2))

        slot_rect = pygame.Rect(
            self._bg_rect.left + _PAD,
            self._bg_rect.top + 80,
            self._bg_rect.width - 2 * _PAD,
            380,
        )
        self._selector = _LoadSlotSelector(
            self.game,
            slot_rect,
            on_load=self._on_load_slot,
        )

        self._restart_btn = Button("Restart", self._on_restart, size=28)
        self._restart_btn.rect.center = (self._bg_rect.centerx, self._bg_rect.bottom - 40)
        self._focus: str = "slots"

    def _on_restart(self) -> None:
        import scene as scene_mod
        import splash_screen

        self.exit_state()
        scene_mod.Scene(self.game, "Village", "start").enter_state()
        splash_screen.SplashScreen(self.game, "GAME OVER").enter_state()

    def _on_load_slot(self, slot_idx: int) -> None:
        self.game.save_manager.load(slot_idx)
        # SaveManager.load pushed a new Scene; discard this DeadState.
        if self.game.states:
            self.game.states[:] = [self.game.states[-1]]

    def _toggle_focus(self) -> None:
        self._focus = "restart" if self._focus == "slots" else "slots"

    def update(self, dt: float, events: list[pygame.event.Event]) -> None:
        self._selector.update(dt)
        self._restart_btn.update(dt)
        for event in events:
            if self._focus == "slots":
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_TAB, pygame.K_RIGHT):
                    self._toggle_focus()
                    continue
                if self._selector.handle_event(event):
                    continue
            else:
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_TAB, pygame.K_LEFT):
                    self._toggle_focus()
                    continue
                if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    self._restart_btn.activate()
                    continue
                if self._restart_btn.handle_event(event):
                    continue

    def draw(self, screen: pygame.Surface, dt: float) -> None:
        screen.fill((0, 0, 0))
        screen.blit(self._bg, self._bg_rect.topleft)
        tr = self._title_surf.get_rect(midtop=(self._bg_rect.centerx, self._bg_rect.top + 30))
        screen.blit(self._title_surf, tr)

        self._selector.draw(screen)
        self._restart_btn.selected = self._focus == "restart"
        self._restart_btn.draw(screen)
