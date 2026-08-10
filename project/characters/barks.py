"""Reżyser barków - kto się odzywa, kiedy i czym (H01, etap 2).

Moduł systemu wg B01 (D1): stan siedzi na scenie (``scene.barks``), a cała
logika to metody jednej klasy bez pygame'a poza odczytem pozycji.

Bark to **tło, nie wiadomość**. Z tego jednego zdania wynika prawie wszystko
niżej: kwestia, która nie zmieściła się w limicie dwóch naraz, po prostu
przepada (nie czeka w kolejce), a milczenie jest stanem domyślnym, nie awarią.

Dwa wyzwalacze (W4), różne dlatego, że różnie brzmią w grze:

- **na zbliżenie** - gracz wchodzi w promień. Rzut kością raz na wejście, nie co
  klatkę: bez tego przejście obok kogokolwiek ZAWSZE dawałoby kwestię i wieś
  tykałaby jak zegarek.
- **z rutyny** - postaci właśnie zmienił się krok dnia i ma o tym coś do
  powiedzenia („głodny", gdy idzie na lunch). Wtedy wolno jej zagadać z dalszej
  odległości i bez rzutu kością, bo ma konkretny powód. Sama TREŚĆ związana
  z rutyną jest warunkiem `activity(...)` na linii, nie osobnym mechanizmem.

Losowość idzie z generatora zasianego jak cząstki (A04), **nigdy** z gołego
``random``: bark, który przy tym samym ziarnie raz wypada tak, a raz inaczej,
unieważnia każdą asercję scenariusza agentowego.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

from dialog.bark_context import NPCBarkContext
from dialog.conditions import ConditionError, ConditionScope, check_condition
from settings import (
    BARK_CHANCE,
    BARK_COOLDOWN_GLOBAL,
    BARK_COOLDOWN_NPC,
    BARK_MAX_ON_SCREEN,
    BARK_RADIUS_TILES,
    BARK_ROUTINE_RADIUS_TILES,
    TILE_SIZE,
    get_msg,
)

if TYPE_CHECKING:
    from characters import NPC
    from scene.scene import Scene


class BarkDirector:
    """Decyduje, która postać się odzywa. Jeden na scenę."""

    def __init__(self, scene: "Scene") -> None:
        self.scene = scene
        # Zasiany w trybie deterministycznym (A04), losowy w normalnej grze.
        # Trzymany, a nie tworzony na żądanie: `scene._particle_rng()` oddaje
        # ZA KAŻDYM RAZEM świeży generator od tego samego ziarna, więc wołany
        # per bark dawałby w kółko ten sam wynik.
        self.rng: random.Random = scene._particle_rng() or random.Random()
        #: klucz postaci -> ile sekund jeszcze milczy
        self.cooldowns: dict[str, float] = {}
        #: klucz postaci -> klucz ostatnio użytej kwestii; wykluczany z następnego
        #: losowania, żeby Barman nie powtórzył tego samego żartu dwa razy pod rząd
        self.last_said: dict[str, str] = {}
        #: klucz postaci -> krok rutyny, na którym widzieliśmy ją ostatnio.
        #: Zmiana = „ma świeżą nowinę" (wyzwalacz z rutyny).
        self._seen_slot: dict[str, str] = {}
        #: postacie, które mają świeżą nowinę i jeszcze jej nie powiedziały
        self._has_news: set[str] = set()
        #: kto był w promieniu w poprzedniej klatce - rzut kością robimy raz,
        #: na WEJŚCIU gracza w zasięg, a nie co klatkę
        self._in_range: set[str] = set()
        self.global_cooldown: float = 0.0

    # -- odczyt stanu (asercje agentowe, A02) --------------------------------

    def active(self) -> list[dict[str, str]]:
        """Kto mówi w tej chwili i czym - dla ``debug_ui_state``.

        Scenariusz „Ambient Barks" asertuje TO, a nie zrzut ekranu: headless nie
        jest wierny dla kompozycji całej klatki, więc zrzut nie rozstrzyga, czy
        bark jest widoczny.
        """
        return [
            {"npc": npc.config_key, "msg": npc.bark.message_key}
            for npc in self.scene.NPCs
            if getattr(npc, "bark", None) is not None and npc.bark.is_speaking
        ]

    # -- pętla ----------------------------------------------------------------

    def update(self, dt: float) -> None:
        self._tick_cooldowns(dt)
        self._note_routine_changes()

        if self.global_cooldown > 0.0 or len(self.active()) >= BARK_MAX_ON_SCREEN:
            # Trzeci bark PRZEPADA, nie czeka: gdyby czekał, wieś odzywałaby się
            # seriami długo po tym, jak gracz stamtąd odszedł.
            return

        candidate = self._pick_speaker()
        if candidate is not None:
            self.speak(candidate)

    def _tick_cooldowns(self, dt: float) -> None:
        self.global_cooldown = max(0.0, self.global_cooldown - dt)
        for key in list(self.cooldowns):
            remaining = self.cooldowns[key] - dt
            if remaining <= 0.0:
                del self.cooldowns[key]
            else:
                self.cooldowns[key] = remaining

    def _note_routine_changes(self) -> None:
        """Zauważ, komu właśnie zmienił się krok dnia.

        Czytane stąd, a nie zgłaszane przez NPC: reżyser zostaje samowystarczalny,
        a `update_schedule` nie musi wiedzieć, że barki w ogóle istnieją.
        """
        for npc in self.scene.NPCs:
            slot = getattr(npc, "_schedule_slot", None)
            if slot is None:
                continue
            key = npc.config_key
            marker = f"{slot.from_minutes}:{slot.activity}"
            if self._seen_slot.get(key) != marker:
                if key in self._seen_slot:
                    # pierwszy odczyt to nie „zmiana", tylko poznanie stanu -
                    # inaczej cała wieś zagadałaby w pierwszej klatce po wczytaniu
                    self._has_news.add(key)
                self._seen_slot[key] = marker

    def _pick_speaker(self) -> "NPC | None":
        """Postać, która ma prawo i powód się odezwać - albo ``None``.

        Kolejność przeglądania to kolejność `scene.NPCs`, a wybór spośród
        równorzędnych idzie przez zasiany generator, więc przy tym samym ziarnie
        wychodzi ten sam ciąg.
        """
        player_pos = self.scene.player.pos
        near_radius = BARK_RADIUS_TILES * TILE_SIZE
        news_radius = BARK_ROUTINE_RADIUS_TILES * TILE_SIZE

        eligible: list[NPC] = []
        still_in_range: set[str] = set()
        for npc in self.scene.NPCs:
            key = npc.config_key
            distance = player_pos.distance_to(npc.pos)
            has_news = key in self._has_news

            if distance <= near_radius:
                still_in_range.add(key)
            if not self._can_speak(npc):
                continue

            if has_news and distance <= news_radius:
                # ma konkretny powód - żadnego rzutu kością
                eligible.append(npc)
            elif distance <= near_radius and key not in self._in_range:
                # gracz właśnie wszedł w promień: jeden rzut, nie co klatkę
                if self.rng.random() < BARK_CHANCE:
                    eligible.append(npc)

        self._in_range = still_in_range
        if not eligible:
            return None
        return eligible[0] if len(eligible) == 1 else self.rng.choice(eligible)

    def _can_speak(self, npc: "NPC") -> bool:
        if getattr(npc, "bark", None) is None or npc.bark.is_speaking:
            return False
        if npc.is_dead or getattr(npc, "is_asleep", False):
            # Śpiący nie gada. `sleep` ma własny kanał - stałe `zzz` nad głową.
            return False
        return npc.config_key not in self.cooldowns

    # -- treść ----------------------------------------------------------------

    def owners_for(self, npc: "NPC") -> list[str]:
        """Skąd ta postać bierze kwestie: własna sekcja **i** wspólna pula (D2).

        Sumują się, nie wykluczają - inaczej każda postać z choćby jednym własnym
        żartem musiałaby mieć przepisany cały komplet „dzień dobry".
        """
        owners = [npc.config_key]
        pool = str(getattr(npc.model, "barks", "") or "").strip()
        if pool:
            owners.append(pool)
        return owners

    def candidates_for(self, npc: "NPC") -> list[dict[str, str]]:
        """Kwestie, których warunek zapala się dla tej postaci tu i teraz."""
        barks = getattr(self.scene.game.conf, "barks", None) or {}
        context = NPCBarkContext(npc, self.scene.player)
        matching: list[dict[str, str]] = []
        for owner in self.owners_for(npc):
            for entry in barks.get(owner, ()):
                if self._matches(entry, context, owner):
                    matching.append(entry)
        return matching

    def _matches(self, entry: dict[str, str], context: NPCBarkContext, owner: str) -> bool:
        condition = entry.get("condition") or "True"
        if condition == "True":
            return True
        try:
            return check_condition(condition, context, ConditionScope.bark)
        except ConditionError as exc:
            # Walidator (reguła 20) i importer łapią to wcześniej; jeśli mimo to
            # coś tu dotarło, jedna postać ma milczeć, a nie cała gra się wywalić.
            print(f"[barks] bad condition in {owner}/{entry.get('msg', '?')}: {exc}")
            return False

    def speak(self, npc: "NPC") -> bool:
        """Wybierz kwestię i każ ją powiedzieć. ``False`` = nie miała nic do powiedzenia."""
        candidates = self.candidates_for(npc)
        key = npc.config_key
        if not candidates:
            # Postać bez pasującej kwestii nie ma za co być karana cooldownem
            # wsi - to nie jest bark, który się odbył. Ale nowina się zużywa,
            # inaczej próbowałaby w każdej klatce.
            self._has_news.discard(key)
            self.cooldowns[key] = BARK_COOLDOWN_NPC
            return False

        entry = self._choose(candidates, key)
        text = get_msg(self.scene.game.conf.messages, entry["msg"])
        npc.bark.say(text, entry["msg"])

        self.last_said[key] = entry["msg"]
        self.cooldowns[key] = BARK_COOLDOWN_NPC
        self.global_cooldown = BARK_COOLDOWN_GLOBAL
        self._has_news.discard(key)
        self._in_range.add(key)
        return True

    def _choose(self, candidates: list[dict[str, str]], key: str) -> dict[str, str]:
        """Losuj z zasianego generatora, z wykluczeniem ostatnio użytej kwestii (D5).

        Bez wykluczenia Barman powtórzy ten sam żart dwa razy pod rząd i wyjdzie
        z tego usterka, a nie żart. Przy jednym kandydacie wykluczać nie ma czego -
        wtedy powtórzenie jest jedyną możliwą treścią.
        """
        fresh = [entry for entry in candidates if entry["msg"] != self.last_said.get(key)]
        pool = fresh or candidates
        return pool[0] if len(pool) == 1 else self.rng.choice(pool)


