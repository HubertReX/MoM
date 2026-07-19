from __future__ import annotations

import re
import string
import time
from typing import TYPE_CHECKING, Callable

import pygame
from enums import NotificationTypeEnum
from save_load.models import MAX_SLOT_NAME_LEN, SaveSlotInfo
import settings
from settings import FONT_SIZE_LARGE, FONT_SIZE_SMALL, MAX_SAVE_SLOTS, PANEL_BG_COLOR, _

from .. import keycap, theme
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
_SLOT_FONT = 16          # save-slot row text (>= SMALL 14, design-system minimum)
_ROW_INSET = 12          # left/right text inset inside a slot row
_CAP_ROW_H = 32          # native keycap height (design-system: caps render at 32px)
_BOX_NINE_PATCH = "nine_patch_12b.png"  # darker sub-panel for confirm / rename dialogs

_RICH_TAG = re.compile(r"\[/?[a-zA-Z]+\]")
_KEY_MARKUP = re.compile(r"[{}]")


def _strip_rich(text: str) -> str:
    """Drop RichText ``[tag]`` markup so a plain font render doesn't show the tags."""
    return _RICH_TAG.sub("", text)


def _strip_key_markup(text: str) -> str:
    """Fallback for hint strings when no keycap sprites are available (main-menu load):
    turn ``{Enter} zapisz`` into ``Enter zapisz``."""
    return _KEY_MARKUP.sub("", text)


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
    return _("save.playtime_format", h=h, m=m)


class _SlotButton:
    def __init__(self, idx: int, info: SaveSlotInfo | None, rect: pygame.Rect) -> None:
        self.idx = idx
        self.info = info
        self.rect = rect
        self.occupied = info is not None and info.is_occupied

    @property
    def label(self) -> str:
        name, meta = self.parts
        return name if not meta else f"{name}   {meta}"

    @property
    def parts(self) -> tuple[str, str]:
        """Row text split into (name, meta). ``meta`` (timestamp + playtime) is drawn
        right-aligned so a long name can never push the playtime off the panel edge -
        the clipping bug from the single concatenated label."""
        if not self.occupied or self.info is None or self.info.metadata is None:
            return _("save.slot_empty", n=self.idx + 1), ""
        m = self.info.metadata
        name = m.slot_name or _("save.slot_default_name", n=self.idx + 1)
        meta = f"{_format_timestamp(m.timestamp)}  {_format_playtime(m.playtime)}"
        return name, meta


def _draw_slot_row(surface: pygame.Surface, slot: "_SlotButton", selected: bool) -> None:
    """Shared render for one save/load slot row: name left, meta (date + playtime)
    right-aligned, so nothing clips regardless of name length."""
    bg_color = (50, 48, 42) if selected else (30, 28, 22)
    pygame.draw.rect(surface, bg_color, slot.rect)
    if selected:
        pygame.draw.rect(surface, theme.GOLD, slot.rect, width=2)
    font = theme.menu_font(_SLOT_FONT)
    name, meta = slot.parts
    name_col = theme.WHITE if slot.occupied else theme.GREY
    cy = slot.rect.centery
    name_surf = font.render(name, False, name_col)
    surface.blit(name_surf, name_surf.get_rect(midleft=(slot.rect.left + _ROW_INSET, cy)))
    if meta:
        meta_surf = font.render(meta, False, theme.GREY)
        surface.blit(meta_surf, meta_surf.get_rect(midright=(slot.rect.right - _ROW_INSET, cy)))


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
        self._confirm_text = _("save.load_confirm", n=slot.idx + 1)
        cx = self.rect.centerx
        cy = self.rect.centery
        self._confirm_buttons = [
            Button(_("menu.yes"), self._confirm_yes, size=_BUTTON_SIZE),
            Button(_("menu.no"), self._confirm_no, size=_BUTTON_SIZE),
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
        pygame.draw.rect(surface, (30, 28, 22), self.rect)
        pygame.draw.rect(surface, (80, 70, 55), self.rect, width=2)

        if not self._slots:
            empty_surf = theme.menu_font(20).render(_("save.no_saves"), False, (120, 110, 90))
            surface.blit(empty_surf, empty_surf.get_rect(center=self.rect.center))

        for i, slot in enumerate(self._slots):
            _draw_slot_row(surface, slot, i == self._selected_idx)

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
    _TITLE_KEY = ""

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
        self._confirm_lines: list[str] = []
        self._confirm_box: pygame.Rect | None = None

        # inline rename editor (TextInput) — active only while renaming a slot
        self._editor: TextInput | None = None
        self._editing_slot_idx: int = -1
        # the same physical key that opens the editor (R) also emits a TEXTINPUT "r";
        # swallow that one stray character so it doesn't land in the field
        self._swallow_next_textinput: bool = False

        self._build_background()
        self._refresh_slots()

    def _build_background(self) -> None:
        bw, bh = 800, 520
        self.bg = theme.nine_patch("nine_patch_04.png", bw, bh)
        self.rect = self.bg.get_rect(center=(settings.WIDTH // 2, settings.HEIGHT // 2))
        self._title_surf = theme.menu_font(32).render(_(self._TITLE_KEY), False, theme.NAME)
        self._close_btn = Label("[X]", size=24)

    # header/footer sit inside the 9-patch border (scale 4 x border 6 = 24px thick),
    # so the title/footer must clear that border - keep the slot list clear of both.
    _HEADER_Y = 32
    _FOOTER_Y = 40         # footer text baseline, measured up from the panel bottom
    _FOOTER_RULE_Y = 64    # divider line above the footer, measured up from the bottom

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
            self.scene.add_notification(_("save.game_saved"), NotificationTypeEnum.success)
        self._confirm_action = None
        self._refresh_slots()

    def open(self) -> None:
        self._confirm_action = None
        self._confirm_slot_idx = -1
        self._confirm_selected = 0
        self._selected_idx = 0
        self._close_editor()
        # Re-fit to the current viewport (the panel is cached; the resolution may have
        # changed since it was built). Slot rects derive from self.rect, so rebuild the
        # background first, then the slots.
        self._build_background()
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
        editor.set_text(slot.info.metadata.slot_name or _("save.slot_default_name", n=slot.idx + 1))
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
            msg = _("save.overwrite", n=slot.idx + 1)
        elif action == "delete":
            self._confirm_action = "delete"
            msg = _("save.delete_confirm")
        else:
            self._confirm_action = "load"
            msg = _("save.load_confirm", n=slot.idx + 1)
        self._confirm_slot_idx = slot.idx
        self._confirm_selected = 0
        self._confirm_text = msg
        self._confirm_lines = [_strip_rich(line) for line in msg.split("\n")]
        self._confirm_buttons = [
            Button(_("menu.yes"), self._confirm_yes, size=_BUTTON_SIZE),
            Button(_("menu.no"), self._confirm_no, size=_BUTTON_SIZE),
        ]
        self._layout_confirm_box()

    # geometry of the confirm sub-panel (a centered nine-patch box sized to its content)
    _BOX_PAD = 36
    _BOX_TEXT_GAP = 6        # between wrapped text lines
    _BOX_BUTTON_GAP = 24     # between the text block and the button row
    _BOX_BTN_SPACING = 28    # between the two buttons

    def _layout_confirm_box(self) -> None:
        font = theme.menu_font(22)
        line_h = font.get_height()
        text_w = max((font.size(ln)[0] for ln in self._confirm_lines), default=0)
        text_h = len(self._confirm_lines) * line_h + (len(self._confirm_lines) - 1) * self._BOX_TEXT_GAP
        btn_w = sum(b.rect.width for b in self._confirm_buttons) + self._BOX_BTN_SPACING
        btn_h = max((b.rect.height for b in self._confirm_buttons), default=0)
        content_w = max(text_w, btn_w)
        content_h = text_h + self._BOX_BUTTON_GAP + btn_h
        box_w = content_w + 2 * self._BOX_PAD
        box_h = content_h + 2 * self._BOX_PAD
        box = pygame.Rect(0, 0, box_w, box_h)
        box.center = self.rect.center
        self._confirm_box = box
        # place the two buttons in a centered row on the box's lower half
        row_x = box.centerx - btn_w // 2
        row_y = box.top + self._BOX_PAD + text_h + self._BOX_BUTTON_GAP
        for btn in self._confirm_buttons:
            btn.rect.topleft = (row_x, row_y)
            row_x += btn.rect.width + self._BOX_BTN_SPACING

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

        if self._slots:
            for i, slot in enumerate(self._slots):
                _draw_slot_row(surface, slot, i == self._selected_idx)
        else:
            # empty list (e.g. LoadPanel with no saves) — say so instead of a blank box
            msg = theme.menu_font(20).render(_("save.no_saves"), False, theme.GREY)
            list_mid = (self._list_top() + (self.rect.bottom - self._FOOTER_RULE_Y)) // 2
            surface.blit(msg, msg.get_rect(center=(self.rect.centerx, list_mid)))

        # footer: Esc-to-close always on the left; per-slot actions on the right when an
        # occupied slot is selected (design-system: close/actions left, context right)
        if not self._confirm_action and self._editor is None:
            self._draw_footer(surface)

        if self._editor is not None:
            self._draw_rename_editor(surface)
        elif self._confirm_action:
            self._draw_confirm_box(surface)

    #############################################################################################################
    # MARK: footer + hint rendering (design-system keycaps)

    def _draw_footer(self, surface: pygame.Surface) -> None:
        """Panel shortcuts strip (design-system: shortcuts live in the footer, on
        sprite keycaps, above a RULE divider). Left = rename/delete (while an occupied
        slot is selected); right = Esc-to-close (always)."""
        inner_l = self.rect.left + _PAD
        inner_r = self.rect.right - _PAD
        rule_y = self.rect.bottom - self._FOOTER_RULE_Y
        cy = self.rect.bottom - self._FOOTER_Y
        pygame.draw.line(surface, theme.RULE, (inner_l, rule_y), (inner_r, rule_y), 2)
        if self._selected_is_occupied():
            self._blit_hint(surface, _("save.action_hint"), (inner_l, cy), align="left")
        self._blit_hint(surface, _("save.close_hint"), (inner_r, cy), align="right")

    def _blit_hint(self, surface: pygame.Surface, markup: str,
                   pos: tuple[int, int], *, align: str = "left") -> None:
        """Render a ``{TOKEN}`` hint anchored at ``pos`` (a point on the row's vertical
        centre) using shared keycaps, with a plain-text fallback when no sprite sheet is
        available (main-menu load path). ``align`` is left / center / right."""
        text_font = theme.get_font(FONT_SIZE_SMALL)
        cx, cy = pos
        icons = self.hud.icons if self.hud is not None else None
        if icons is None:
            plain = theme.menu_font(16).render(_strip_key_markup(markup), False, theme.GREY)
            anchor = {"left": "midleft", "right": "midright"}.get(align, "center")
            surface.blit(plain, plain.get_rect(**{anchor: (cx, cy)}))
            return
        glyph_font = theme.get_font(FONT_SIZE_SMALL)
        sep_font = theme.get_font(FONT_SIZE_LARGE)
        y = cy - _CAP_ROW_H // 2
        if align == "right":
            keycap.render_hint(
                surface, icons, glyph_font, text_font, markup, (cx, y), theme.GREY,
                align="right", glyph_color=theme.WHITE, shadow_color=PANEL_BG_COLOR, sep_font=sep_font,
            )
            return
        if align == "center":
            w = keycap.measure(icons, glyph_font, text_font, markup, theme.WHITE, sep_font=sep_font)
            cx -= w // 2
        keycap.render_hint(
            surface, icons, glyph_font, text_font, markup, (cx, y), theme.GREY,
            glyph_color=theme.WHITE, shadow_color=PANEL_BG_COLOR, sep_font=sep_font,
        )

    #############################################################################################################
    # MARK: confirm / rename sub-panels

    def _dim_panel(self, surface: pygame.Surface, alpha: int) -> None:
        overlay = pygame.Surface(self.bg.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, alpha))
        surface.blit(overlay, self.rect.topleft)

    def _draw_confirm_box(self, surface: pygame.Surface) -> None:
        self._dim_panel(surface, 150)
        box = self._confirm_box
        if box is None:
            return
        surface.blit(theme.nine_patch(_BOX_NINE_PATCH, box.width, box.height), box.topleft)
        font = theme.menu_font(22)
        line_h = font.get_height()
        y = box.top + self._BOX_PAD
        for line in self._confirm_lines:
            ls = font.render(line, False, theme.WHITE)
            surface.blit(ls, ls.get_rect(midtop=(box.centerx, y)))
            y += line_h + self._BOX_TEXT_GAP
        for i, btn in enumerate(self._confirm_buttons):
            btn.selected = i == self._confirm_selected
            btn.draw(surface)

    def _draw_rename_editor(self, surface: pygame.Surface) -> None:
        assert self._editor is not None
        self._dim_panel(surface, 170)
        editor = self._editor
        title_font = theme.menu_font(22)
        title = title_font.render(_("save.rename_title"), False, theme.TITLE)
        # box wraps the title, the input field and the keycap hint
        gap = 18
        title_top = editor.rect.top - gap - title.get_height()
        hint_top = editor.rect.bottom + gap
        content_w = max(editor.rect.width, title.get_width(), 320)
        box_w = content_w + 2 * self._BOX_PAD
        box_top = title_top - self._BOX_PAD
        box_bottom = hint_top + _CAP_ROW_H + self._BOX_PAD
        box = pygame.Rect(0, 0, box_w, box_bottom - box_top)
        box.centerx = self.rect.centerx
        box.top = box_top
        surface.blit(theme.nine_patch(_BOX_NINE_PATCH, box.width, box.height), box.topleft)
        surface.blit(title, title.get_rect(midtop=(box.centerx, title_top)))
        editor.draw(surface)
        self._blit_hint(surface, _("save.rename_hint"),
                        (box.centerx, hint_top + _CAP_ROW_H // 2), align="center")


class SavePanel(SaveLoadPanel):
    _TITLE_KEY = "save.title_save"


class LoadPanel(SaveLoadPanel):
    _TITLE_KEY = "save.title_load"

    def __init__(self, scene: Scene, hud: HUD | None = None, on_load: Callable[[int], None] | None = None) -> None:
        super().__init__(scene, hud)
        self.on_load = on_load

    def _do_load(self, slot_idx: int) -> None:
        success = self.game.save_manager.load(slot_idx)
        if success:
            self.scene.add_notification(_("save.game_loaded"), NotificationTypeEnum.info)
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
        self.rect = self.bg.get_rect(center=(settings.WIDTH // 2, settings.HEIGHT // 2))
        self._title_surf = theme.menu_font(48).render(_("save.you_died"), False, (200, 40, 40))

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

        self._restart_btn = Button(_("save.restart"), self._on_restart, size=28)
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
        splash_screen.SplashScreen(self.game, _("save.game_over")).enter_state()

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
        self._title_surf = theme.menu_font(48).render(_("save.you_died"), False, (200, 40, 40))
        bg_w, bg_h = 600, 520
        self._bg = theme.nine_patch("nine_patch_12b.png", bg_w, bg_h)
        self._bg_rect = self._bg.get_rect(center=(settings.WIDTH // 2, settings.HEIGHT // 2))

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

        self._restart_btn = Button(_("save.restart"), self._on_restart, size=28)
        self._restart_btn.rect.center = (self._bg_rect.centerx, self._bg_rect.bottom - 40)
        self._focus: str = "slots"

    def _on_restart(self) -> None:
        import scene as scene_mod
        import splash_screen

        self.exit_state()
        scene_mod.Scene(self.game, "Village", "start").enter_state()
        splash_screen.SplashScreen(self.game, _("save.game_over")).enter_state()

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
