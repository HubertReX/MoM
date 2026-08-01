#!/usr/bin/env python3
"""Unit tests for the audio manager - project/audio.py (D01).

Run from the project root:
    .venv/bin/python tests/test_audio.py

Audio is the one system whose failure mode is silence, so what is pinned here is
mostly what must NOT happen: a missing mixer must not raise, an unknown SFX key
must not raise, and re-entering a map must not restart its track. The web gesture
gate gets its own tests, because the probe in D01 showed that calling into the
mixer before the player's first input costs a `NotAllowedError` in the JS console.

The mixer is faked throughout (`_FakeMixer`), so these tests do not depend on
`SDL_AUDIODRIVER=dummy` doing the right thing - the "mixer unavailable" path is
exercised explicitly, not hoped for.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import audio as audio_mod  # noqa: E402
import pygame  # noqa: E402
import settings  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "project" / "config_model" / "audio.toml"
MUSIC_DIR = REPO_ROOT / "project" / "assets" / "audio" / "music"
SFX_DIR = REPO_ROOT / "project" / "assets" / "audio" / "sfx"


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


#############################################################################################################
# MARK: fake mixer


class _FakeSound:
    def __init__(self, path: str) -> None:
        self.path = path
        self.volume = 1.0
        self.plays = 0

    def set_volume(self, value: float) -> None:
        self.volume = value

    def play(self) -> None:
        self.plays += 1


class _FakeMusic:
    def __init__(self) -> None:
        self.loaded: list[str] = []
        self.plays = 0
        self.fadeouts = 0
        self.fade_ins: list[int] = []
        self.volume = 1.0

    def load(self, path: str) -> None:
        self.loaded.append(path)

    # `fade_ms` MUSI tu być: to nim manager robi nieblokujące wejście utworu.
    # Bez tego parametru stub rzucał TypeError, manager łapał go jako "padł mikser"
    # i po cichu wyłączał muzykę - a testy myliły to z normalnym przebiegiem.
    def play(self, loops: int = 0, start: float = 0.0, fade_ms: int = 0) -> None:
        self.plays += 1
        self.fade_ins.append(fade_ms)

    def fadeout(self, ms: int) -> None:
        self.fadeouts += 1

    def set_volume(self, value: float) -> None:
        self.volume = value


class _FakeMixer:
    """Stand-in for ``pygame.mixer`` that records what the manager asked for."""

    def __init__(self, *, init_raises: bool = False, sound_raises: bool = False) -> None:
        self._init_raises = init_raises
        self._sound_raises = sound_raises
        self.music = _FakeMusic()
        self.sounds: list[_FakeSound] = []
        self.channels = 0
        self.inited = False

    def init(self) -> None:
        if self._init_raises:
            raise pygame.error("no audio device")
        self.inited = True

    def set_num_channels(self, count: int) -> None:
        self.channels = count

    def Sound(self, path: str) -> _FakeSound:  # noqa: N802 - mirrors the pygame API
        if self._sound_raises:
            raise FileNotFoundError(path)
        sound = _FakeSound(path)
        self.sounds.append(sound)
        return sound


class _Silence:
    """Swallow the manager's log lines so a passing run stays readable."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, text: str) -> None:
        self.lines.append(text)


def _build(
    *,
    needs_gesture: bool = False,
    gesture_check: Any = None,
    manifest: Path = MANIFEST,
    init_raises: bool = False,
    sound_raises: bool = False,
) -> tuple[audio_mod.AudioManager, _FakeMixer, _Silence]:
    """A manager wired to a fake mixer, with the real manifest by default."""
    mixer = _FakeMixer(init_raises=init_raises, sound_raises=sound_raises)
    log = _Silence()
    real_mixer = pygame.mixer
    pygame.mixer = mixer  # type: ignore[assignment]
    try:
        manager = audio_mod.AudioManager(
            manifest, MUSIC_DIR, SFX_DIR,
            needs_gesture=needs_gesture, gesture_check=gesture_check, log=log,
        )
    finally:
        pygame.mixer = real_mixer  # type: ignore[assignment]
    # later calls swap the fake back in through `_WithMixer`
    return manager, mixer, log


class _WithMixer:
    """Context manager swapping ``pygame.mixer`` for the fake during calls."""

    def __init__(self, mixer: _FakeMixer) -> None:
        self.mixer = mixer
        self._real: Any = None

    def __enter__(self) -> _FakeMixer:
        self._real = pygame.mixer
        pygame.mixer = self.mixer  # type: ignore[assignment]
        return self.mixer

    def __exit__(self, *exc: object) -> None:
        pygame.mixer = self._real  # type: ignore[assignment]


#############################################################################################################
# MARK: manifest


def test_manifest_parses_into_music_and_sfx() -> None:
    manager, _mixer, _log = _build()
    assert_true(manager.available, "manager must come up with a real manifest and a live mixer")
    # `[music.settings]` is a sub-table of `[music]`; it must not be mistaken for a map
    assert_true(not manager.has_music("settings"), "[music.settings] must not become a music key")
    assert_true(manager.has_music("main_menu"), "main_menu is in the manifest")
    assert_true(manager.has_music("Village"), "Village is in the manifest")
    assert_eq(manager._music_file_volume, 0.6, "[music.settings].volume must be read")
    assert_eq(manager._fade_ms, 500, "[music.settings].fade_ms must be read")


def test_every_manifest_key_maps_to_a_file_on_disk() -> None:
    manager, _mixer, _log = _build()
    for key, name in manager._music.items():
        assert_true((MUSIC_DIR / name).is_file(), f"music '{key}' -> missing file {name}")
    for key, name in manager._sfx.items():
        assert_true((SFX_DIR / name).is_file(), f"sfx '{key}' -> missing file {name}")


def test_a_missing_manifest_disables_audio_without_raising() -> None:
    manager, mixer, log = _build(manifest=REPO_ROOT / "nie" / "ma" / "takiego.toml")
    assert_true(not manager.available, "no manifest => no audio")
    assert_true(not mixer.inited, "the mixer must not even be started without a manifest")
    assert_true(any("manifest" in line for line in log.lines), "the reason must be logged once")
    # and every call is a no-op
    with _WithMixer(mixer):
        manager.play_music("Village")
        manager.play_sfx("coins")
        manager.stop_music()
        manager.set_volumes(1.0, 1.0, 1.0)
    assert_eq(mixer.music.plays, 0, "nothing may reach the mixer")


#############################################################################################################
# MARK: mixer unavailable


def test_a_dead_mixer_makes_every_call_a_no_op() -> None:
    manager, mixer, log = _build(init_raises=True)
    assert_true(not manager.available, "mixer.init() raising => available is False")
    assert_true(any("mikser" in line for line in log.lines), "the reason must be logged once")
    with _WithMixer(mixer):
        manager.play_music("Village")
        manager.play_sfx("coins")
        manager.stop_music(200)
        manager.set_volumes(0.5, 0.5, 0.5)
        manager.set_muted(True)
        manager.unlock()
    assert_eq(mixer.music.plays, 0, "no music may be played")
    assert_eq(mixer.music.loaded, [], "no track may even be loaded")
    assert_eq(len(mixer.sounds), 0, "no SFX may be loaded")


def test_a_mixer_that_dies_mid_game_silences_the_rest_of_the_session() -> None:
    manager, mixer, _log = _build()

    def boom(*_args: object, **_kwargs: object) -> None:
        raise pygame.error("device lost")

    mixer.music.set_volume = boom  # type: ignore[method-assign]
    with _WithMixer(mixer):
        manager.set_volumes(1.0, 1.0, 1.0)
    assert_true(not manager.available, "a mixer error in flight must turn audio off")


#############################################################################################################
# MARK: music


def test_the_same_key_twice_does_not_reload_the_track() -> None:
    manager, mixer, _log = _build()
    with _WithMixer(mixer):
        manager.play_music("Village")
        first_loads = list(mixer.music.loaded)
        manager.play_music("Village")
    assert_eq(mixer.music.loaded, first_loads, "re-entering the same map must not reload")
    assert_eq(mixer.music.plays, 1, "re-entering the same map must not restart the track")


def test_a_different_key_fades_the_new_track_in() -> None:
    """Zmiana mapy podmienia utwór, wprowadzając nowy fade-inem.

    Świadomie NIE wołamy tu `music.fadeout()` na starym utworze: `music.load()`
    w trakcie trwającego fade'u blokuje pętlę gry do końca tego fade'u (~723 ms
    przy `fade_ms = 500`), co dawało zauważalne zamrożenie przy każdym przejściu
    mapy. Fade-in przez `play(fade_ms=...)` nie blokuje.
    """
    manager, mixer, _log = _build()
    with _WithMixer(mixer):
        manager.play_music("Village")
        manager.play_music("VillageHouse")
    assert_eq(len(mixer.music.loaded), 2, "a map change must load the new track")
    assert_eq(mixer.music.fadeouts, 0, "a map change must NOT block on a fadeout")
    assert_true(all(ms > 0 for ms in mixer.music.fade_ins),
                "every track must be faded in, not cut in abruptly")
    assert_eq(manager.current_music_key, "VillageHouse", "the manager tracks what plays")


def test_a_map_without_an_entry_is_silence_not_an_error() -> None:
    manager, mixer, _log = _build()
    with _WithMixer(mixer):
        manager.play_music("Village")
        manager.play_music("NoSuchMap")
    assert_eq(manager.current_music_key, None, "an unmapped map means silence")
    assert_eq(len(mixer.music.loaded), 1, "no second track may be loaded")


def test_music_volume_multiplies_master_channel_and_file() -> None:
    manager, mixer, _log = _build()
    with _WithMixer(mixer):
        manager.set_volumes(0.5, 0.5, 1.0)
        manager.play_music("Village")
    # 0.5 (master) * 0.5 (music) * 0.6 ([music.settings].volume)
    assert_eq(round(mixer.music.volume, 4), 0.15, "effective music volume")


def test_muting_does_not_restart_the_track() -> None:
    manager, mixer, _log = _build()
    with _WithMixer(mixer):
        manager.play_music("Village")
        manager.set_muted(True)
        muted_volume = mixer.music.volume
        manager.set_muted(False)
    assert_eq(muted_volume, 0.0, "a pause must drop the volume to zero")
    assert_eq(mixer.music.plays, 1, "a pause must not restart the track")
    assert_true(mixer.music.volume > 0.0, "unpausing must bring the volume back")


#############################################################################################################
# MARK: SFX


def test_an_unknown_sfx_key_is_a_logged_no_op() -> None:
    manager, mixer, log = _build()
    with _WithMixer(mixer):
        manager.play_sfx("nie_ma_takiego_eventu")
    assert_eq(len(mixer.sounds), 0, "an unknown key must not load anything")
    assert_true(any("nie_ma_takiego_eventu" in line for line in log.lines),
                "an unknown key must be named in the log")


def test_a_broken_sfx_file_is_a_logged_no_op() -> None:
    manager, mixer, log = _build(sound_raises=True)
    with _WithMixer(mixer):
        manager.play_sfx("coins")
        manager.play_sfx("coins")
    assert_true(any("coins" in line for line in log.lines), "the failure must be logged")
    assert_true(sum("coins" in line for line in log.lines) == 1,
                "a failed load is cached too - it must not retry on every hit")


def test_sounds_are_loaded_once_and_reused() -> None:
    manager, mixer, _log = _build()
    with _WithMixer(mixer):
        manager.play_sfx("coins")
        manager.play_sfx("coins")
        manager.play_sfx("coins")
    assert_eq(len(mixer.sounds), 1, "the same event must not build a new Sound every time")
    assert_eq(mixer.sounds[0].plays, 3, "but it must be played every time")


def test_nothing_is_loaded_before_the_first_play() -> None:
    manager, mixer, _log = _build()
    assert_eq(len(mixer.sounds), 0, "the constructor must not preload the whole sfx folder")
    assert_eq(mixer.channels, audio_mod.SFX_CHANNELS, "but it must widen the channel pool")


def test_sfx_volume_multiplies_master_and_channel() -> None:
    manager, mixer, _log = _build()
    with _WithMixer(mixer):
        manager.set_volumes(0.5, 1.0, 0.4)
        manager.play_sfx("coins")
    assert_eq(round(mixer.sounds[0].volume, 4), 0.2, "effective sfx volume")


#############################################################################################################
# MARK: web gesture gate


def test_before_the_first_gesture_nothing_reaches_the_mixer() -> None:
    manager, mixer, _log = _build(needs_gesture=True)
    assert_true(manager.available, "the mixer is up - it is only the browser that is not ready")
    assert_true(not manager.unlocked, "web starts locked")
    with _WithMixer(mixer):
        manager.play_music("Village")
        manager.play_sfx("coins")
    assert_eq(mixer.music.plays, 0, "a play() before the gesture is what raises NotAllowedError")
    assert_eq(mixer.music.loaded, [], "not even a load()")
    assert_eq(len(mixer.sounds), 0, "SFX are dropped, not queued")
    assert_eq(manager.current_music_key, "Village", "but the pending track is remembered")


def test_the_first_gesture_starts_the_pending_track() -> None:
    manager, mixer, _log = _build(needs_gesture=True)
    with _WithMixer(mixer):
        manager.play_music("Village")
        manager.unlock()
    assert_true(manager.unlocked, "unlock() opens the gate")
    assert_eq(mixer.music.plays, 1, "the remembered track starts on the first gesture")
    assert_eq(len(mixer.music.loaded), 1, "and it is loaded exactly once")


def test_unlocking_twice_does_not_restart_the_track() -> None:
    manager, mixer, _log = _build(needs_gesture=True)
    with _WithMixer(mixer):
        manager.play_music("Village")
        manager.unlock()
        manager.unlock()
    assert_eq(mixer.music.plays, 1, "every later keypress must not restart the music")


def test_unlocking_with_nothing_pending_plays_nothing() -> None:
    manager, mixer, _log = _build(needs_gesture=True)
    with _WithMixer(mixer):
        manager.unlock()
    assert_eq(mixer.music.plays, 0, "no pending key means no track")


def test_a_synthetic_event_does_not_unlock_when_the_browser_says_no() -> None:
    """The web runner posts KEYDOWN with `pygame.event.post`; the browser does not
    count that as a gesture, so unlocking on it would only buy a NotAllowedError."""
    activated = [False]
    manager, mixer, _log = _build(needs_gesture=True, gesture_check=lambda: activated[0])
    with _WithMixer(mixer):
        manager.play_music("Village")
        manager.unlock()
        assert_true(not manager.unlocked, "no browser activation => stay locked")
        assert_eq(mixer.music.plays, 0, "and nothing may reach the mixer")
        # the player finally clicks
        activated[0] = True
        manager.unlock()
    assert_true(manager.unlocked, "a real gesture opens the gate")
    assert_eq(mixer.music.plays, 1, "and starts the pending track")


def test_desktop_starts_unlocked() -> None:
    manager, mixer, _log = _build()
    assert_true(manager.unlocked, "desktop has no autoplay policy to satisfy")
    with _WithMixer(mixer):
        manager.play_music("Village")
    assert_eq(mixer.music.plays, 1, "and plays straight away")


#############################################################################################################
# MARK: module facade


def test_the_facade_is_a_no_op_before_init() -> None:
    audio_mod.shutdown()
    assert_true(not audio_mod.available(), "no manager => not available")
    # none of these may raise
    audio_mod.play_music("Village")
    audio_mod.play_sfx("coins")
    audio_mod.stop_music()
    audio_mod.set_volumes(1.0, 1.0, 1.0)
    audio_mod.set_muted(True)
    audio_mod.unlock()
    assert_eq(audio_mod.manager(), None, "and there is still no manager")


def test_init_publishes_the_manager_to_the_facade() -> None:
    mixer = _FakeMixer()
    real_mixer = pygame.mixer
    pygame.mixer = mixer  # type: ignore[assignment]
    try:
        manager = audio_mod.init(MANIFEST, MUSIC_DIR, SFX_DIR, log=_Silence())
        assert_eq(audio_mod.manager(), manager, "init() must publish the manager")
        assert_true(audio_mod.available(), "and report it as available")
        audio_mod.play_music("Village")
        assert_eq(mixer.music.plays, 1, "the facade must reach the manager")
    finally:
        pygame.mixer = real_mixer  # type: ignore[assignment]
        audio_mod.shutdown()


#############################################################################################################
# MARK: settings wiring


def test_volume_settings_survive_a_round_trip_through_storage() -> None:
    from save_load.display_settings import DisplaySettings, _parse_settings, _to_dict

    ds = DisplaySettings(resolution_index=1, fullscreen=False, language="EN",
                         volume_master=0.4, volume_music=0.3, volume_sfx=0.9)
    restored = _parse_settings(_to_dict(ds))
    assert_eq(restored.volume_master, 0.4, "master volume must round-trip")
    assert_eq(restored.volume_music, 0.3, "music volume must round-trip")
    assert_eq(restored.volume_sfx, 0.9, "sfx volume must round-trip")


def test_a_settings_file_from_before_audio_still_loads() -> None:
    """The player's existing settings.json has no volume keys - it must not be discarded."""
    from save_load.display_settings import CURRENT_VERSION, _parse_settings

    old = {"version": CURRENT_VERSION, "resolution_index": 2, "fullscreen": True, "language": "EN"}
    restored = _parse_settings(old)
    assert_eq(restored.resolution_index, 2, "the old fields must survive")
    assert_eq(restored.language, "EN", "the old fields must survive")
    assert_eq(restored.volume_master, settings.DEFAULT_VOLUME_MASTER, "missing volume => default")
    assert_eq(restored.volume_music, settings.DEFAULT_VOLUME_MUSIC, "missing volume => default")
    assert_eq(restored.volume_sfx, settings.DEFAULT_VOLUME_SFX, "missing volume => default")


def test_a_corrupt_volume_falls_back_to_the_default() -> None:
    from save_load.display_settings import CURRENT_VERSION, _parse_settings

    raw = {"version": CURRENT_VERSION, "resolution_index": 0, "fullscreen": False,
           "language": "PL", "volume_music": "gło<ośno", "volume_sfx": 5.0}
    restored = _parse_settings(raw)
    assert_eq(restored.volume_music, settings.DEFAULT_VOLUME_MUSIC, "garbage => default")
    assert_eq(restored.volume_sfx, 1.0, "out of range => clamped, not reset")


def main() -> None:
    tests = [
        test_manifest_parses_into_music_and_sfx,
        test_every_manifest_key_maps_to_a_file_on_disk,
        test_a_missing_manifest_disables_audio_without_raising,
        test_a_dead_mixer_makes_every_call_a_no_op,
        test_a_mixer_that_dies_mid_game_silences_the_rest_of_the_session,
        test_the_same_key_twice_does_not_reload_the_track,
        test_a_different_key_fades_the_new_track_in,
        test_a_map_without_an_entry_is_silence_not_an_error,
        test_music_volume_multiplies_master_channel_and_file,
        test_muting_does_not_restart_the_track,
        test_an_unknown_sfx_key_is_a_logged_no_op,
        test_a_broken_sfx_file_is_a_logged_no_op,
        test_sounds_are_loaded_once_and_reused,
        test_nothing_is_loaded_before_the_first_play,
        test_sfx_volume_multiplies_master_and_channel,
        test_before_the_first_gesture_nothing_reaches_the_mixer,
        test_the_first_gesture_starts_the_pending_track,
        test_unlocking_twice_does_not_restart_the_track,
        test_unlocking_with_nothing_pending_plays_nothing,
        test_a_synthetic_event_does_not_unlock_when_the_browser_says_no,
        test_desktop_starts_unlocked,
        test_the_facade_is_a_no_op_before_init,
        test_init_publishes_the_manager_to_the_facade,
        test_volume_settings_survive_a_round_trip_through_storage,
        test_a_settings_file_from_before_audio_still_loads,
        test_a_corrupt_volume_falls_back_to_the_default,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} audio tests passed.")


if __name__ == "__main__":
    main()
