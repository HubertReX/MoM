#!/usr/bin/env python3
"""Regeneracja grafik do dokumentu migracji dialogów (Dialog System).

Tworzy dwa obrazki w ``doc/img/`` z PRAWDZIWYCH modułów MoM (headless, SDL dummy):

- ``mom-emote-sheet.png``   - arkusz ``emote_all_anim.png`` pocięty wg
  ``settings.EMOTE_SHEET_DEFINITION`` z nałożonymi kluczami ``:key:``, wariantami
  ``anim`` i współrzędnymi (kolumna, wiersz).
- ``mom-richtext-tags.png`` - render silnikiem ``ui.widgets.rich_text.RichText``
  całej palety znaczników tekstu + inline emote (nine-patch jak w grze).

Obrazki ilustrują decyzję **D3** (mapowanie znaczników rich -> MoM) w
``doc/dialog-migration-plan.html``. Uruchom po dodaniu nowych emote/tagów, aby je odświeżyć.

Użycie:
    just gen-dialog-docs
    # lub bezpośrednio:
    .venv/bin/python doc/gen_dialog_doc_assets.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "project"
OUT = ROOT / "doc" / "img"

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, str(PROJECT))

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((1280, 720))  # potrzebne do convert_alpha() w trybie dummy

import settings  # noqa: E402


def _font(size: int):
    """Zwróć TTF czytelny do etykiet (cross-platform), z fallbackiem na default."""
    from PIL import ImageFont
    for p in (
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def gen_emote_sheet() -> Path:
    """Anotowany contact-sheet arkusza emote z kluczami :key:."""
    from PIL import Image, ImageDraw

    D = settings.EMOTE_SHEET_DEFINITION
    CW, CH = 14, 13          # rozmiar komórki w arkuszu źródłowym
    COLS = ROWS = 8
    SCALE = 8
    SW, SH = CW * SCALE, CH * SCALE
    PAD, LABEL_H, HEADER, FOOTER, MARGIN = 16, 34, 76, 60, 24
    CELL_W = SW + PAD
    CELL_H = SH + LABEL_H + PAD

    sheet = Image.open(str(settings.EMOTE_SHEET_FILE)).convert("RGBA")

    single: dict[tuple[int, int], list[str]] = {}
    anim_owner: dict[tuple[int, int], set[str]] = {}
    for k, frames in D.items():
        if len(frames) == 1:
            single.setdefault(tuple(frames[0]), []).append(k)
        else:
            for cr in frames:
                anim_owner.setdefault(tuple(cr), set()).add(k)

    BG, CELL_BG, GRID = (28, 31, 40), (44, 48, 60), (70, 76, 92)
    WHITE, MUTE, ACCENT = (230, 232, 236), (140, 146, 160), (255, 200, 90)

    W = MARGIN * 2 + COLS * CELL_W
    H = HEADER + ROWS * CELL_H + FOOTER
    img = Image.new("RGBA", (W, H), BG)
    dr = ImageDraw.Draw(img)
    f_title, f_lbl, f_sm = _font(26), _font(15), _font(12)

    dr.text((MARGIN, 20), "MoM - arkusz emote  (klucze :key: z EMOTE_SHEET_DEFINITION)",
            font=f_title, fill=WHITE)
    dr.text((MARGIN, 52), "komorka 14x13 px - siatka 8x8 (kolumna, wiersz) - sprite skalowany x8 nearest",
            font=f_sm, fill=MUTE)

    for r in range(ROWS):
        for c in range(COLS):
            x = MARGIN + c * CELL_W
            y = HEADER + r * CELL_H
            dr.rectangle([x, y, x + SW + PAD - 4, y + SH + LABEL_H + PAD - 4],
                         fill=CELL_BG, outline=GRID)
            crop = sheet.crop((c * CW, r * CH, c * CW + CW, r * CH + CH)).resize((SW, SH), Image.NEAREST)
            img.alpha_composite(crop, (x + (SW + PAD - 4 - SW) // 2, y + 6))
            dr.text((x + 5, y + 3), f"{c},{r}", font=f_sm, fill=MUTE)
            ly = y + SH + 8
            names = single.get((c, r), [])
            if names:
                dr.text((x + 6, ly), f":{names[0]}:", font=f_lbl, fill=ACCENT)
                extra = list(names[1:]) + ["▶" + a for a in sorted(anim_owner.get((c, r), ()))]
                if extra:
                    dr.text((x + 6, ly + 17), " ".join(extra), font=f_sm, fill=MUTE)
            elif (an := anim_owner.get((c, r))):
                dr.text((x + 6, ly), "(klatka anim)", font=f_sm, fill=MUTE)
                dr.text((x + 6, ly + 15), " ".join(sorted(an)), font=f_sm, fill=(110, 116, 132))

    anim_keys = sorted(k for k, v in D.items() if len(v) > 1)
    dr.text((MARGIN, H - FOOTER + 6), "Warianty animowane (_anim): " + ", ".join(anim_keys),
            font=f_sm, fill=MUTE)

    out = OUT / "mom-emote-sheet.png"
    img.convert("RGB").save(out)
    return out


def _import_sheet(path: str, definition: dict, w: int, h: int) -> dict:
    """Lokalna kopia scene.import_sheet (bez ładowania całej sceny)."""
    img = pygame.image.load(path).convert_alpha()
    res: dict = {}
    for key, defn in definition.items():
        frames = [img.subsurface(pygame.Rect(x * w, y * h, w, h))
                  for (x, y) in defn if pygame.Rect(x * w, y * h, w, h).colliderect(img.get_rect())]
        if frames:
            res[key] = frames
    return res


def gen_richtext() -> Path:
    """Render palety znaczników RichText na nine-patchu (styl _dialog.png)."""
    from ui import theme
    from ui.widgets.rich_text import RichText

    icons = _import_sheet(str(settings.EMOTE_SHEET_FILE), settings.EMOTE_SHEET_DEFINITION, 14, 13)

    text = (
        "[center][big][shadow][act]MoM RichText - dostepne znaczniki[/act][/shadow][/big][/center]\n"
        "\n"
        "[bold]Kolory:[/bold]  [act]act[/act]   [char]char[/char]   [item]item[/item]   [loc]loc[/loc]   "
        "[num]num[/num]   [quest]quest[/quest]   [text]text[/text]   [error]error[/error]\n"
        "\n"
        "[bold]Style:[/bold]  [bold]bold[/bold]   [italic]italic[/italic]   [underline]underline[/underline]   "
        "[shadow]shadow[/shadow]   [big]big[/big]   [small]small[/small]\n"
        "\n"
        "[bold]Naglowek h3:[/bold] [h3]Rozdzial pierwszy[/h3]\n"
        "\n"
        "[bold]Link:[/bold] [link http://example.com]LINK[/link]      [bold]Wyrownanie:[/bold] left / center / right\n"
        "\n"
        "[bold]Emote inline (:key:):[/bold]  :smile: :happy: :sad: :angry: :neutral: :love: :blessed: "
        ":doubt: :wondering: :evil: :dead: :star: :heart: :question: :$:\n"
        "\n"
        "[bold]Przyklad zdania:[/bold] [char]Malachi[/char] :smile: wchodzi do [loc]Gafowa Kolonia[/loc]; "
        "[item]czterolistna koniczyna[/item] daje [num]+100[/num] szczescia, a [char]Zielarka[/char] jest [act]zla[/act] :angry:."
    )

    B, inner_w = 30, 1000
    rt = RichText(text, pygame.Rect(B, B, inner_w, 6000), icons, base_size=22)
    content_h = rt.content_surface.get_height()
    bg_w, bg_h = inner_w + 2 * B, content_h + 2 * B
    panel = theme.nine_patch("nine_patch_01c.png", bg_w, bg_h)

    OUTER, DARK = 22, (28, 31, 40)
    canvas = pygame.Surface((bg_w + 2 * OUTER, bg_h + 2 * OUTER))
    canvas.fill(DARK)
    canvas.blit(panel, (OUTER, OUTER))

    rt.rect = pygame.Rect(OUTER + B, OUTER + B, inner_w, content_h)
    rt.max_scroll = 0
    rt.scroll = 0
    rt.show_scrollbar = False
    rt.draw(canvas)

    out = OUT / "mom-richtext-tags.png"
    pygame.image.save(canvas, str(out))
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for p in (gen_emote_sheet(), gen_richtext()):
        print("saved:", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
