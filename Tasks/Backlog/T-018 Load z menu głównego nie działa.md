---
id: T-018
title: Load z menu głównego nie działa
status: needs-you
owner: human
priority: p1
type: bug
agent: opencode
created: 2026-07-04
updated: 2026-07-04
tags:
  - task
state: review
---

# T-018 — Load z menu głównego nie działa

Zaraz po uruchomieniu gry i wybraniu "Load" z menu głównego, na ułamek sekundy pojawia się ekran wczytywania, ale zanim zdążę coś wybrać okno jak i cała gra się zamyka.

## 🎯 Goal / Outcome


- [x] po wybraniu "Load" pojawia się ekran wyboru slotu do wczytania i czeka
- [x] Po wybraniu slotu gra się wczytuje i można grać dalej

## 🧭 Context


- brak

## ⛓️ Constraints


- brak

## 🪜 Plan / Subtasks

- brak

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione
- [x] zmiany udokumentowa w tasku (`moab log`)
- [x] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [x] Testy / lint przechodzą (jeśli dotyczy)
- [x] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [x] commit zmian wykonany

![[agent_20260704_T-018_load_menu.png]]

## 📓 Agent Log

- 2026-07-04 22:41 opencode: claimed, starting
- 2026-07-04 23:08 opencode: Zaimplementowano poprawkę dla błędu zamykania gry po wybraniu opcji Load z Menu Głównego. Przyczyną było wywołanie self.exit_state() przy zamykaniu menu, co gdy menu było jedynym stanem na stosie, powodowało ustawienie self.game.is_running = False i zamknięcie gry. Dodatkowo zsynchronizowano zachowanie get_save_dir w automate_display_test.py ze stanem faktycznym (uwzględniając XDG_DATA_HOME).
- 2026-07-04 23:08 opencode: Błąd został usunięty. Główne menu nie jest już usuwane ze stosu przy otwieraniu panelu wczytywania (LoadMenuScreen). Dzięki temu, gdy wczytywanie jest anulowane, gra prawidłowo powraca do menu zamiast się zamykać. Na dodatek, gdy stan jest pomyślnie wczytany, cała pętla gry poprawnie zastępuje stos nową Sceną. Zweryfikowane testem 'Load from Main Menu' i wszystkimi pozostałymi scenariuszami - wszystkie przeszły pomyślnie.


## 🙋 Needs-You / Questions

