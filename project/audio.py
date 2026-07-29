"""Audio: muzyka per mapa i SFX eventów - jedno wejście do dźwięku dla całej gry.

Moduł systemu wg B01: cała logika to funkcje/metody na jednym obiekcie stanu
(:class:`AudioManager`), a reszta kodu woła fasadę modułową
(``audio.play_sfx("coins")``) i nie przekazuje sobie referencji do managera.

Trzy rzeczy, które trzymają ten moduł w ryzach:

1. **Nic tu nie może wywalić gry.** Brak karty dźwiękowej, ``SDL_AUDIODRIVER=dummy``
   w testach, CI, zepsuty plik - każdy wyjątek gasi audio (``available = False``)
   i od tej pory wszystkie wywołania są cichymi no-opami.
2. **Bramka gestu użytkownika (web).** Sonda D01 pokazała, że pygbag wstaje z
   działającym mikserem, ale przeglądarka blokuje odtwarzanie przed pierwszym
   gestem gracza (``NotAllowedError`` jako nieprzechwycony błąd w konsoli JS),
   a pygbagowe „will retry" nie działa. Dlatego na web ``_unlocked`` startuje jako
   ``False`` i **do miksera nie idzie ani jedno ``play``** - odłożony utwór rusza
   dopiero z :meth:`AudioManager.unlock`, wołanego przy pierwszym realnym wejściu
   gracza (``Game.get_inputs``).
3. **Własny stan zamiast pytania miksera.** ``mixer.music.get_busy()`` na web
   zwraca ``False`` mimo grającego utworu, więc „co teraz gra" trzyma
   ``_current_key``, a nie pygame.

Zero importów z ``scene``/``characters``/``game``/``settings``: moduł ma być
importowalny w teście jednostkowym bez SDL-a i bez reszty gry. Ścieżki dostaje
w :func:`init` od wołającego.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - desktop < 3.11 / środowiska bez tomllib
    import tomli as tomllib  # type: ignore[no-redef]

import pygame

#: Klucze muzyki, które nie są nazwą mapy (walidator zna dokładnie tę listę).
SPECIAL_MUSIC_KEYS: tuple[str, ...] = ("main_menu", "maze", "death")

#: Domyślne ustawienia sekcji ``[music.settings]``, gdy manifest ich nie poda.
DEFAULT_FADE_MS = 500
DEFAULT_MUSIC_FILE_VOLUME = 0.6

#: Kanały SFX. Domyślne 8 to za mało na młóckę w labiryncie (urwany SFX jest
#: lepszy niż zjedzony klawisz - pygame samo wypiera najstarszy dźwięk).
SFX_CHANNELS = 16


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


class AudioManager:
    """Stan dźwięku: manifest, cache SFX-ów, głośności i aktualny utwór."""

    def __init__(
        self,
        manifest_path: Path,
        music_dir: Path,
        sfx_dir: Path,
        *,
        needs_gesture: bool = False,
        gesture_check: Callable[[], bool] | None = None,
        log: Callable[[str], Any] = print,
    ) -> None:
        self._log = log
        self._gesture_check = gesture_check
        self._music_dir = Path(music_dir)
        self._sfx_dir = Path(sfx_dir)
        self._music: dict[str, str] = {}
        self._sfx: dict[str, str] = {}
        self._fade_ms: int = DEFAULT_FADE_MS
        self._music_file_volume: float = DEFAULT_MUSIC_FILE_VOLUME
        self._sounds: dict[str, pygame.mixer.Sound | None] = {}
        self._current_key: str | None = None
        self._volume_master: float = 1.0
        self._volume_music: float = 0.7
        self._volume_sfx: float = 0.8
        # web: cisza do pierwszego gestu gracza (patrz docstring modułu)
        self._unlocked: bool = not needs_gesture
        self._muted: bool = False
        self._available: bool = False

        if not self._load_manifest(Path(manifest_path)):
            return
        self._available = self._init_mixer()

    # --- start ---------------------------------------------------------------

    def _load_manifest(self, path: Path) -> bool:
        try:
            with open(path, "rb") as f:
                data: dict[str, Any] = tomllib.load(f)
        except Exception as e:  # noqa: BLE001 - brak/zepsuty manifest = gra bez dźwięku
            self._log(f"[audio] manifest {path} nie wczytany: {e!r} - dźwięk wyłączony")
            return False

        music = data.get("music", {}) or {}
        # `[music.settings]` jest podtabelą `[music]`, więc siedzi w tym samym diccie
        # co mapy - stąd filtr na wartości tekstowe zamiast ślepego `dict(music)`.
        settings = music.get("settings", {}) or {}
        self._music = {k: v for k, v in music.items() if isinstance(v, str)}
        self._sfx = {k: v for k, v in (data.get("sfx", {}) or {}).items() if isinstance(v, str)}
        self._fade_ms = int(settings.get("fade_ms", DEFAULT_FADE_MS))
        self._music_file_volume = _clamp(float(settings.get("volume", DEFAULT_MUSIC_FILE_VOLUME)))
        return True

    def _init_mixer(self) -> bool:
        try:
            pygame.mixer.init()
            pygame.mixer.set_num_channels(SFX_CHANNELS)
        except Exception as e:  # noqa: BLE001 - brak karty / dummy driver / CI
            self._log(f"[audio] mikser niedostępny ({e!r}) - dźwięk wyłączony")
            return False
        return True

    # --- stan ----------------------------------------------------------------

    @property
    def available(self) -> bool:
        """``True`` gdy mikser wstał i manifest się wczytał."""
        return self._available

    @property
    def unlocked(self) -> bool:
        """``False`` na web do pierwszego gestu gracza."""
        return self._unlocked

    @property
    def current_music_key(self) -> str | None:
        """Klucz utworu, który gra (albo czeka na gest). ``None`` = cisza."""
        return self._current_key

    def has_music(self, key: str) -> bool:
        return key in self._music

    # --- muzyka --------------------------------------------------------------

    def play_music(self, key: str) -> None:
        """Zagraj utwór spod *key* (nazwa mapy albo kontekst specjalny).

        Ten sam klucz drugi raz nic nie robi - powrót na tę samą mapę nie
        restartuje utworu. Nieznany klucz = cisza (mapa bez wpisu to nie błąd).
        """
        if not self._available:
            return
        if key == self._current_key:
            return
        if key not in self._music:
            self.stop_music()
            return

        self._current_key = key
        if not self._unlocked:
            # zapamiętane; ruszy z unlock() - żadnego `play` przed gestem gracza
            return
        self._start_current()

    def stop_music(self, fade_ms: int | None = None) -> None:
        if not self._available:
            return
        self._current_key = None
        if not self._unlocked:
            return
        try:
            pygame.mixer.music.fadeout(self._fade_ms if fade_ms is None else fade_ms)
        except Exception as e:  # noqa: BLE001
            self._fail(e)

    def _start_current(self) -> None:
        key = self._current_key
        if key is None:
            return
        path = self._music_dir / self._music[key]
        try:
            pygame.mixer.music.fadeout(self._fade_ms)
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(self._music_volume())
            pygame.mixer.music.play(-1)
        except Exception as e:  # noqa: BLE001 - brak pliku, zły format, padły mikser
            self._log(f"[audio] nie udało się zagrać '{key}' ({path.name}): {e!r}")
            self._current_key = None

    # --- SFX -----------------------------------------------------------------

    def play_sfx(self, key: str) -> None:
        """Zagraj efekt zarejestrowany pod nazwą eventu *key*.

        Nieznany klucz to ostrzeżenie w logu i no-op - od łapania literówek jest
        ``just validate-world``, a nie wyjątek w środku walki.
        """
        if not self._available or not self._unlocked or self._muted:
            return
        sound = self._sound(key)
        if sound is None:
            return
        try:
            sound.set_volume(self._sfx_volume())
            sound.play()
        except Exception as e:  # noqa: BLE001
            self._fail(e)

    def _sound(self, key: str) -> pygame.mixer.Sound | None:
        """Leniwe ładowanie + cache (16 plików w ``__init__`` to koszt startu na web).

        Nieudane ładowanie też trafia do cache'u (jako ``None``), żeby brakujący
        plik nie próbował się wczytać przy każdym uderzeniu.
        """
        if key in self._sounds:
            return self._sounds[key]
        file_name = self._sfx.get(key)
        if file_name is None:
            self._log(f"[audio] nieznany event SFX '{key}' - sprawdź audio.toml")
            self._sounds[key] = None
            return None
        try:
            sound: pygame.mixer.Sound | None = pygame.mixer.Sound(str(self._sfx_dir / file_name))
        except Exception as e:  # noqa: BLE001
            self._log(f"[audio] nie udało się wczytać SFX '{key}' ({file_name}): {e!r}")
            sound = None
        self._sounds[key] = sound
        return sound

    # --- głośność i pauza ----------------------------------------------------

    def set_volumes(self, master: float, music: float, sfx: float) -> None:
        self._volume_master = _clamp(master)
        self._volume_music = _clamp(music)
        self._volume_sfx = _clamp(sfx)
        if not self._available or not self._unlocked:
            return
        try:
            pygame.mixer.music.set_volume(self._music_volume())
        except Exception as e:  # noqa: BLE001
            self._fail(e)

    def set_muted(self, muted: bool) -> None:
        """Wycisz/odcisz wszystko (pauza gry) bez gubienia bieżącego utworu."""
        if self._muted == muted:
            return
        self._muted = muted
        if not self._available or not self._unlocked:
            return
        try:
            pygame.mixer.music.set_volume(self._music_volume())
        except Exception as e:  # noqa: BLE001
            self._fail(e)

    def _music_volume(self) -> float:
        if self._muted:
            return 0.0
        return _clamp(self._volume_master * self._volume_music * self._music_file_volume)

    def _sfx_volume(self) -> float:
        return _clamp(self._volume_master * self._volume_sfx)

    # --- bramka gestu (web) --------------------------------------------------

    def unlock(self) -> None:
        """Pierwszy gest gracza: od teraz wolno wołać mikser; odpal odłożony utwór.

        ``gesture_check`` (na web: ``navigator.userActivation.hasBeenActive``) jest
        tu, bo zdarzenie pygame nie dowodzi gestu: runner testowy wstrzykuje
        syntetyczne ``KEYDOWN`` przez ``pygame.event.post`` i przeglądarka takiego
        wejścia NIE uznaje za aktywację. Bez tej bramki testy web dostawałyby
        ``NotAllowedError`` w konsoli przy każdym przebiegu. Nieudane sprawdzenie
        nie kosztuje nic - próba wraca przy następnym zdarzeniu.
        """
        if self._unlocked:
            return
        if self._gesture_check is not None and not self._gesture_check():
            return
        self._unlocked = True
        # Jedna linia, raz na sesję. Bez niej „na web nie ma dźwięku" jest nie do
        # odróżnienia od „gest nie dotarł do pygame" - a to dwie różne naprawy.
        self._log(f"[audio] odblokowane gestem gracza (available={self._available}, "
                  f"pending={self._current_key!r})")
        if self._available and self._current_key is not None:
            self._start_current()

    # --- awaria w locie ------------------------------------------------------

    def _fail(self, exc: BaseException) -> None:
        """Mikser padł w trakcie gry: jedna linia logu i cisza do końca sesji."""
        self._log(f"[audio] mikser padł ({exc!r}) - dźwięk wyłączony")
        self._available = False


#############################################################################################################
# MARK: fasada modułowa


_manager: AudioManager | None = None


def init(
    manifest_path: Path,
    music_dir: Path,
    sfx_dir: Path,
    *,
    needs_gesture: bool = False,
    gesture_check: Callable[[], bool] | None = None,
    log: Callable[[str], Any] = print,
) -> AudioManager:
    """Zbuduj managera i zapamiętaj go jako ten, do którego mówi cała gra."""
    global _manager
    _manager = AudioManager(
        manifest_path, music_dir, sfx_dir,
        needs_gesture=needs_gesture, gesture_check=gesture_check, log=log,
    )
    return _manager


def manager() -> AudioManager | None:
    """Aktywny manager albo ``None``, gdy :func:`init` jeszcze nie poszło."""
    return _manager


def shutdown() -> None:
    """Zapomnij managera (testy - żeby jeden przypadek nie zatruwał następnego)."""
    global _manager
    _manager = None


def available() -> bool:
    return _manager is not None and _manager.available


def play_music(key: str) -> None:
    if _manager is not None:
        _manager.play_music(key)


def stop_music(fade_ms: int | None = None) -> None:
    if _manager is not None:
        _manager.stop_music(fade_ms)


def play_sfx(key: str) -> None:
    if _manager is not None:
        _manager.play_sfx(key)


def set_volumes(master: float, music: float, sfx: float) -> None:
    if _manager is not None:
        _manager.set_volumes(master, music, sfx)


def set_muted(muted: bool) -> None:
    if _manager is not None:
        _manager.set_muted(muted)


def unlock() -> None:
    if _manager is not None:
        _manager.unlock()


__all__ = [
    "AudioManager",
    "SPECIAL_MUSIC_KEYS",
    "available",
    "init",
    "manager",
    "play_music",
    "play_sfx",
    "set_muted",
    "set_volumes",
    "shutdown",
    "stop_music",
    "unlock",
]
