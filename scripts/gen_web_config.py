#!/usr/bin/env python3
"""Generate `project/config_model/config.py` (web) from the desktop config model.

The desktop model (`project/config_model/config_pydantic.py`) validates
`config.json` at import time. That validator does not load in pygbag/WASM, so
the web build carries a second, hand-free implementation: plain
`@dataclass(slots=True)` entities with a manual `from_dict`. Two independent
hand-written copies drifted apart twice (G01 audit finding) with no error or
warning - just a chest that never got random loot, and a maze whose RNG
stream silently diverged from the desktop reference for the same seed.

This script removes the hand-editing step: it introspects the desktop
model's fields (`model_fields`, in declaration order) and emits the whole web
module. Two fields do not map field-for-field onto the desktop shape - see
`OVERRIDES` below - everything else is derived.

Usage:
    just gen-web-config
    # or directly:
    .venv/bin/python scripts/gen_web_config.py
"""
from __future__ import annotations

import inspect
import os
import sys
import types
from enum import Enum
from pathlib import Path
from typing import Any, get_args, get_origin

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "project"
OUTPUT_FILE = PROJECT / "config_model" / "config.py"

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, str(PROJECT))

from config_model import config_pydantic as desktop  # noqa: E402
from pydantic.fields import FieldInfo  # noqa: E402
from pydantic_core import PydanticUndefined  # noqa: E402

# Models that exist only for desktop-side concerns and have no web counterpart:
# quest content is validated by Pydantic at import time (decision D4) and the
# runtime reads the plain dict via `quest.graph.init_quests` on both
# platforms, so `Quest`/`QuestReward` never need a dataclass mirror.
# `ConfigForSchemaGen` exists only to generate `config_schema.json`.
SKIP_MODELS = {"Quest", "QuestReward", "ConfigForSchemaGen"}

# One visible table for the two spots where the web shape intentionally does
# NOT mirror the desktop model field-for-field. Each entry is
# (dataclass declaration, from_dict value expression) - the same two pieces
# the generic path would otherwise compute from the desktop FieldInfo.
OVERRIDES: dict[tuple[str, str], tuple[str, str]] = {
    # int | dict[str, int] with a validator that folds a legacy int into the
    # default weights - see the `disposition()` helper below, which mirrors
    # `config_pydantic.Character._convert_disposition`.
    ("Character", "disposition"): (
        "disposition: dict[str, int] = "
        "field(default_factory=lambda: dict(DEFAULT_DISPOSITION_WEIGHTS), repr=False)",
        'disposition(data.get("disposition"))',
    ),
    # Quest definitions stay a plain dict here: the web build has no schema
    # validation (decision D4), and `quest.graph.init_quests` reads exactly
    # this shape.
    ("Config", "quests"): (
        "quests: dict[str, Any] = field(repr=False)",
        'data.get("quests", {})',
    ),
}


def collect_web_models() -> list[type]:
    """Desktop BaseModel subclasses that need a web mirror, in declaration order."""
    candidates = []
    for name, cls in inspect.getmembers(desktop, inspect.isclass):
        if cls.__module__ != desktop.__name__:
            continue
        if not issubclass(cls, desktop.BaseModel):
            continue
        if name in SKIP_MODELS or name == "Config":
            continue
        candidates.append(cls)
    candidates.sort(key=lambda c: inspect.getsourcelines(c)[1])
    return candidates


def python_type_str(annotation: Any) -> str:
    if annotation is Any:
        return "Any"
    if annotation is str:
        return "str"
    if annotation is int:
        return "int"
    if annotation is float:
        return "float"
    if annotation is bool:
        return "bool"
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return annotation.__name__
    origin = get_origin(annotation)
    if origin is list:
        (inner,) = get_args(annotation)
        return f"list[{python_type_str(inner)}]"
    if origin is dict:
        key_t, val_t = get_args(annotation)
        return f"dict[{python_type_str(key_t)}, {python_type_str(val_t)}]"
    if origin is types.UnionType:
        args = get_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1 and type(None) in args:
            return f"{python_type_str(non_none[0])} | None"
    raise ValueError(f"gen_web_config: unhandled annotation {annotation!r} - add a case or an OVERRIDES entry")


def _default_factory_kwarg(info: FieldInfo) -> str:
    if info.default_factory is list:
        return "default_factory=list"
    if info.default_factory is dict:
        return "default_factory=dict"
    raise ValueError(f"gen_web_config: unhandled default_factory {info.default_factory!r}")


def from_dict_expr(field_name: str, annotation: Any, info: FieldInfo) -> str:
    """The value expression a generated `from_dict`/`build` uses for one field.

    Fields the desktop model requires (no default) fall back to an "empty"
    sentinel that keeps a genuinely missing key loud: `Enum("")` raises
    `ValueError` immediately, which is the point - a required field silently
    defaulting would be exactly the kind of drift this generator exists to
    prevent.
    """
    key = field_name
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        fallback = '""' if info.is_required() else repr(info.default)
        return f'{annotation.__name__}(data.get("{key}", {fallback}))'
    if annotation is str:
        fallback = '""' if info.is_required() else repr(info.default)
        return f'str(data.get("{key}", {fallback}))'
    if annotation is int:
        fallback = "0" if info.is_required() else repr(info.default)
        return f'int(data.get("{key}", {fallback}))'
    if annotation is float:
        fallback = "0.0" if info.is_required() else repr(info.default)
        return f'float(data.get("{key}", {fallback}))'
    if annotation is bool:
        fallback = "False" if info.is_required() else repr(info.default)
        return f'bool(data.get("{key}", {fallback}))'

    origin = get_origin(annotation)
    if origin is list:
        (inner,) = get_args(annotation)
        if isinstance(inner, type) and issubclass(inner, Enum):
            return f'[{inner.__name__}(x) for x in data.get("{key}", [])]'
        if inner is str:
            return f'[str(x) for x in data.get("{key}", [])]'
        raise ValueError(f"gen_web_config: unhandled list element type {inner!r} for field {key!r}")
    if origin is dict:
        _key_t, val_t = get_args(annotation)
        if val_t is Any:
            return f'data.get("{key}", {{}})'
        raise ValueError(f"gen_web_config: unhandled dict value type {val_t!r} for field {key!r}")
    if origin is types.UnionType:
        args = get_args(annotation)
        if type(None) in args:
            return f'data.get("{key}")'

    raise ValueError(f"gen_web_config: unhandled annotation {annotation!r} for field {key!r} - add a case or an OVERRIDES entry")


def _forced_defaults(model: type) -> set[str]:
    """Field names that must carry a literal dataclass default.

    A dataclass cannot have a required field after a defaulted one. Only
    `OVERRIDES` ever forces a default (`disposition`); once one is forced,
    every field after it in declaration order needs one too, using the
    desktop model's own default. If a *required* field ever ended up after a
    forced default, this would raise - that's the generator telling you the
    field order needs a new OVERRIDES entry, not something to paper over.
    """
    names = list(model.model_fields.keys())
    forced: set[str] = set()
    running = False
    for name in names:
        if (model.__name__, name) in OVERRIDES:
            running = True
        if running:
            info = model.model_fields[name]
            if info.is_required() and (model.__name__, name) not in OVERRIDES:
                raise ValueError(
                    f"gen_web_config: {model.__name__}.{name} is required but follows a forced "
                    "default in declaration order - dataclasses can't express that; add an "
                    "OVERRIDES entry or reorder the desktop model."
                )
            forced.add(name)
    return forced


def render_field_decl(field_name: str, annotation: Any, info: FieldInfo, *, force_default: bool) -> str:
    type_str = python_type_str(annotation)
    kwargs = []
    if not info.repr:
        kwargs.append("repr=False")
    if force_default:
        if info.default_factory is not None:
            kwargs.append(_default_factory_kwarg(info))
        else:
            kwargs.append(f"default={info.default!r}")
    if not kwargs:
        return f"    {field_name}: {type_str}"
    return f"    {field_name}: {type_str} = field({', '.join(kwargs)})"


def render_model_class(model: type) -> str:
    name = model.__name__
    forced = _forced_defaults(model)
    field_lines: list[str] = []
    kwarg_lines: list[str] = []
    for field_name, info in model.model_fields.items():
        override = OVERRIDES.get((name, field_name))
        if override is not None:
            decl, expr = override
            field_lines.append(f"    {decl}")
        else:
            decl = render_field_decl(field_name, info.annotation, info, force_default=field_name in forced)
            field_lines.append(decl)
            expr = from_dict_expr(field_name, info.annotation, info)
        kwarg_lines.append(f"            {field_name}={expr},")

    fields_src = "\n".join(field_lines)
    kwargs_src = "\n".join(kwarg_lines)
    # A field literally named `type` (Item.type) shadows the builtin `type` used in
    # `cls: type["Name"]` - mypy then reads that annotation as the *instance
    # attribute* `Item.type`, not the builtin. Leave `cls` unannotated in that case;
    # mypy infers it fine for a classmethod, same as the original hand-written file.
    cls_param = "cls" if "type" in model.model_fields else f'cls: type["{name}"]'
    return (
        f"@dataclass(slots=True)\n"
        f"class {name}():\n"
        f"{fields_src}\n"
        f"\n"
        f"    @classmethod\n"
        f'    def from_dict({cls_param}, data: dict[str, Any]) -> "{name}":\n'
        f"        return cls(\n"
        f"{kwargs_src}\n"
        f"        )\n"
    )


def render_config_class(entity_model_names: set[str]) -> str:
    field_lines: list[str] = []
    build_blocks: list[list[str]] = []  # each block: unindented statement lines, one blank line between blocks
    kwarg_lines: list[str] = []

    for field_name, info in desktop.Config.model_fields.items():
        override = OVERRIDES.get(("Config", field_name))
        if override is not None:
            decl, expr = override
            field_lines.append(f"    {decl}")
            build_blocks.append([f"{field_name} = {expr}"])
            kwarg_lines.append(f"            {field_name}={field_name},")
            continue

        annotation = info.annotation
        origin = get_origin(annotation)
        if origin is dict:
            key_t, val_t = get_args(annotation)
            if isinstance(val_t, type) and val_t.__name__ in entity_model_names:
                type_str = f"dict[{python_type_str(key_t)}, {val_t.__name__}]"
                field_lines.append(f"    {field_name}: {type_str}")
                key_expr = "int(key)" if key_t is int else "key"
                build_blocks.append([
                    f"{field_name}: {type_str} = {{}}",
                    f'for key, entry in data["{field_name}"].items():',
                    f"    {field_name}[{key_expr}] = {val_t.__name__}.from_dict(entry)",
                ])
                kwarg_lines.append(f"            {field_name}={field_name},")
                continue

        type_str = python_type_str(annotation)
        field_lines.append(f"    {field_name}: {type_str}")
        build_blocks.append([f'{field_name} = data.get("{field_name}", {{}})'])
        kwarg_lines.append(f"            {field_name}={field_name},")

    fields_src = "\n".join(field_lines)
    body_src = "\n\n".join("\n".join(f"        {line}" for line in block) for block in build_blocks)
    kwargs_src = "\n".join(kwarg_lines)
    return (
        f"@dataclass\n"
        f"class Config():\n"
        f"{fields_src}\n"
        f"\n"
        f"    @classmethod\n"
        f'    def build(cls, data: dict[str, Any]) -> "Config":\n'
        f"{body_src}\n"
        f"\n"
        f"        # keyword args on purpose: this used to be positional, and inserting a\n"
        f"        # field in the middle would have silently shifted a value into the wrong slot\n"
        f"        return cls(\n"
        f"{kwargs_src}\n"
        f"        )\n"
    )


BANNER = '''"""Model konfiguracji gry (web) - WYGENEROWANY, NIE EDYTUJ RECZNIE.

Ten plik tworzy `scripts/gen_web_config.py` z modelu desktopowego w tym samym
katalogu (`config_model/`). Zeby zmienic pole - zmien je tam i uruchom
`just gen-web-config`, zeby przeniesc zmiane tutaj. Reczna edycja tego pliku
zniknie przy nastepnym uruchomieniu generatora i zostanie wykryta przez test
swiezosci (`tests/test_config_web_codegen.py`).

Web (pygbag/WASM) nie waliduje configu przy starcie - walidacja spojnosci
(czy przedmioty/postacie/skrzynie z odwolan istnieja) dzieje sie wylacznie na
desktopie, przy imporcie tresci.
"""'''

IMPORTS = """import json
from dataclasses import dataclass, field
from os import PathLike
from typing import Any

from enums import AttitudeEnum, ItemTypeEnum, RaceEnum
from settings import DEFAULT_DISPOSITION_WEIGHTS
"""

DISPOSITION_HELPER = '''def disposition(raw: object) -> dict[str, int]:
    # Mirrors the desktop model's disposition validator: int -> default
    # weights, dict -> copied + cast to int, anything else -> defaults.
    if isinstance(raw, int):
        return dict(DEFAULT_DISPOSITION_WEIGHTS)
    if isinstance(raw, dict):
        return {str(k): int(v) for k, v in raw.items()}
    return dict(DEFAULT_DISPOSITION_WEIGHTS)
'''

LOAD_CONFIG = '''def load_config(file_name: PathLike) -> "Config":
    with open(file_name, "r") as f:
        config_json = json.load(f)

    config_json.pop("$schema", None)
    return Config.build(config_json)
'''


def generate_source() -> str:
    models = collect_web_models()
    entity_model_names = {m.__name__ for m in models}

    blocks = [BANNER, IMPORTS.rstrip("\n"), DISPOSITION_HELPER.rstrip("\n")]
    for model in models:
        blocks.append(render_model_class(model).rstrip("\n"))
    blocks.append(render_config_class(entity_model_names).rstrip("\n"))
    blocks.append(LOAD_CONFIG.rstrip("\n"))
    return "\n\n\n".join(blocks) + "\n"


def main() -> None:
    source = generate_source()
    OUTPUT_FILE.write_text(source, encoding="utf-8")
    print(f"[gen-web-config] wrote {OUTPUT_FILE.relative_to(ROOT)} ({len(source.splitlines())} lines)")


if __name__ == "__main__":
    main()
