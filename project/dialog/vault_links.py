"""Wikilinki wewnątrz wyrażeń mini-DSL: z notatki Obsidiana na klucz encji.

Warunek napisany w vaulcie ma dwóch czytelników. Silnik chce klucza
(``"BARMAN_ABSINTHRAYNER"``), a Obsidian chce linku - inaczej zależność „ta opcja
otwiera się dopiero po rozmowie z barmanem" nie istnieje w grafie notatek i widać
ją dopiero po przeczytaniu pliku. Zapis przeplatany godzi jednych z drugimi::

    `visited(`[[Barman Absyntnent#012|Barman#012]]`)`

Backquote'y są formatowaniem Obsidiana i schodzą przy imporcie, a link staje się
kluczem (kluczami), na które wskazuje. Odwrotnej drogi nie ma i nie potrzeba:
źródłem prawdy jest notatka, ``config.json`` jest artefaktem.

Moduł mieszka w ``dialog/`` dla towarzystwa: ``dialog/conditions.py`` (mini-DSL,
z którego korzystają i dialogi, i questy) jest tu z tego samego powodu.
"""

from __future__ import annotations

import re
from pathlib import Path

# Katalogi notatek, na które wolno wskazać z wyrażenia, w kolejności pierwszeństwa.
# Postacie niosą klucze dialogów, misje własne klucze, lokalizacje klucze map.
ENTITY_SUBDIRS: tuple[str, ...] = (
    "PL/Postacie", "EN/Characters",
    "PL/Misje", "EN/Quests",
    "PL/Lokalizacje", "EN/Locations",
)

# `[[Cel]]`, `[[Cel#kotwica]]`, `[[Cel#kotwica|napis]]`, `[[#kotwica]]`.
WIKI_RE = re.compile(
    r"\[\[(?P<target>[^\]|#]*)(?:#(?P<anchor>[^\]|]+))?(?:\|(?P<display>[^\]]*))?\]\]"
)

# Klucz encji to UPPER_SNAKE; lista aliasów notatki niesie też nazwy wyświetlane
# (``Barman``, ``Tawerna``), które kluczem nie są.
_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


class VaultLinkError(ValueError):
    """Link, którego nie da się rozwinąć. Woła o ``file:line`` u wołającego."""


def parse_aliases(text: str) -> list[str]:
    """Lista ``aliases`` z frontmatteru YAML notatki.

    Celowo malutkie: vault nie ma zależności od parsera YAML, a z frontmatteru
    potrzebny jest tylko klucz encji.
    """
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == "---"), None)
    if start is None:
        return []
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return []

    aliases: list[str] = []
    in_aliases = False
    for line in lines[start + 1:end]:
        stripped = line.strip()
        if stripped.startswith("aliases:"):
            in_aliases = True
            inline = stripped[len("aliases:"):].strip()
            if inline.startswith("[") and inline.endswith("]"):
                aliases.extend(a.strip().strip("\"'") for a in inline[1:-1].split(",") if a.strip())
                in_aliases = False
            continue
        if in_aliases:
            if stripped.startswith("- "):
                aliases.append(stripped[2:].strip().strip("\"'"))
                continue
            in_aliases = False
    return [a for a in aliases if a]


def note_key(text: str) -> str:
    """Klucz encji z frontmatteru notatki - pierwszy alias w UPPER_SNAKE."""
    return next((a for a in parse_aliases(text) if _KEY_RE.match(a)), "")


def build_entity_index(src_dir: Path) -> dict[str, str]:
    """``{nazwa notatki albo alias: klucz encji}`` dla wszystkiego, co wyrażenie może nazwać.

    Link pisze się tak, jak chce Obsidian - po zlokalizowanej nazwie notatki -
    a wyjść musi klucz, który zna silnik. Obie pisownie trafiają do tej samej
    mapy, więc ``[[Zielarka Zmora#014]]`` i ``[[POTIONEER_PUZZLEMINT#014]]`` to
    jedna krawędź.

    Wygrywa pierwszy wpis, więc nazwa wyświetlana nigdy nie przesłoni notatki,
    która nosi tę nazwę wprost.
    """
    index: dict[str, str] = {}
    for sub in ENTITY_SUBDIRS:
        directory = src_dir / sub
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            key = note_key(text)
            if not key:
                continue
            for name in (path.stem, *parse_aliases(text)):
                index.setdefault(name, key)
    return index


def resolve_entity(name: str, index: dict[str, str]) -> str | None:
    """Cel wikilinku -> klucz encji, albo ``None``, gdy nikt nie nosi tej nazwy."""
    candidate = name.rsplit("/", 1)[-1].strip()
    return index.get(candidate) or index.get(candidate.replace("_", " "))


def expand_links(
    value: str,
    index: dict[str, str],
    *,
    label: str = "expression",
    self_anchor: bool = False,
) -> str:
    """``` `visited(`[[Zielarka Zmora#014|Zielarka#014]]`)` ``` -> gotowy warunek.

    Backquote'y schodzą. Link staje się kluczem (kluczami), które nazywa:
    z kotwicą to węzeł dialogu, więc daje **oba** argumenty ``"KLUCZ", "węzeł"``;
    bez kotwicy samą encję, ``"KLUCZ"``. Sufiks ``-end`` oznacza w nagłówku
    dialogu węzeł końcowy i nie należy do klucza węzła (ta sama reguła, co
    w imporcie dialogów).

    ``self_anchor`` włącza ``[[#005]]`` -> ``"005"``: w dialogu postać wynika
    z kontekstu rozmowy, więc węzeł „u siebie" nie potrzebuje nazwy. W queście
    nie ma czegoś takiego jak bieżąca postać, więc tam taki link jest błędem.
    """

    def _replace(match: re.Match[str]) -> str:
        target = match.group("target").strip()
        anchor = (match.group("anchor") or "").strip()

        if not target:
            if self_anchor and anchor:
                return f'"{anchor.removesuffix("-end")}"'
            raise VaultLinkError(
                f"{label} has a same-note wikilink ({match.group(0)}) — an expression "
                f"here names another note, so the link needs its name"
            )

        key = resolve_entity(target, index)
        if key is None:
            raise VaultLinkError(
                f"{label} links to {target!r}, which is not a character, quest or "
                f"location note in the vault"
            )
        if not anchor:
            return f'"{key}"'
        return f'"{key}", "{anchor.removesuffix("-end")}"'

    return WIKI_RE.sub(_replace, value).replace("`", "").strip()


__all__ = [
    "ENTITY_SUBDIRS",
    "WIKI_RE",
    "VaultLinkError",
    "build_entity_index",
    "expand_links",
    "note_key",
    "parse_aliases",
    "resolve_entity",
]
