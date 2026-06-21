# AGENTS.md — shadery OpenGL/WebGL (`project/shaders/`)

Post-processing GLSL renderowany przez **zengl**. Kontekst nadrzędny: [`../AGENTS.md`](../AGENTS.md).

## Dwa zestawy: desktop vs web

| Folder | Profil | Tryb |
|---|---|---|
| `OpenGL3.3/` | OpenGL Core 3.3 | **desktop** |
| `OpenGL3.0_ES/` | OpenGL ES 3.0 (WebGL) | **web** |
| `common/` | Wspólne includes: `common.glsl` (`#define` rozdzielczości, `MAX_LIGHTS_COUNT`), `RGB2HSV.glsl` | oba |

Oba zestawy zawierają ten sam komplet efektów:
`vs.glsl`, `fs.glsl` (bazowe), `fs_SATURATED.glsl`, `fs_B_AND_W.glsl`,
`fs_RETRO_CRT.glsl`, `fs_LIGHTING.glsl` (cykl dzień/noc, do 32 świateł).

> ⚠️ **Edytując shader na desktopie (`OpenGL3.3/`), zsynchronizuj wariant ES
> (`OpenGL3.0_ES/`)** — inaczej wersja web się rozjedzie. Pamiętaj o różnicach składni
> GLSL Core vs ES.

## Render

- Wrapper: `../opengl_shader.py` (kompilacja/render przez zengl). Init różni się desktop vs web.
- Wybór katalogu shaderów (`SHADERS_DIR`) zależy od `IS_WEB` (`settings.py`).
- Includes (`common.glsl`, `RGB2HSV.glsl`) wstrzykiwane jako `includes` przy kompilacji.

## Status: domyślnie wyłączone

- **`USE_SHADERS = False`** (`settings.py:92`) — shadery są obecnie **wyłączone** ze względu
  na wydajność (zwłaszcza na web). Pełnoekranowy filtr dzień-noc również jest pomijany na web
  (`scene.py:1515`, `if USE_ALPHA_FILTER and not IS_WEB`).
- `pygbag.ini` (root) **wyklucza `OpenGL3.3` z buildu web** (desktopowy profil nie jest tam
  potrzebny).

Włączając shadery (`USE_SHADERS = True`), przetestuj wydajność w **obu** trybach przed
trwałym włączeniem.
