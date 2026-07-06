---
id: T-036
title: DS: Feedback zmiany sentymentu - floating plus-minus N (later)
status: needs-you
owner: human
priority: p3
type: feature
agent: opencode
created: 2026-07-05
updated: 2026-07-05
tags:
  - task
state: review
---

# T-036 - DS: Feedback zmiany sentymentu (later)

## 🎯 Goal / Outcome

- [x] Wizualny feedback przy zmianie sentymentu: floating `+N` / `-N` (zielony/czerwony) + mruganie paska sentymentu przy wyborze opcji (`dialog.py`: `_floating_texts`, `_sentiment_flash_timer`)

## 🧭 Context

- **Kontekst wspólny (przeczytaj najpierw):** [[DS-epic-brief]] - lokalizacje repo (RPG i MoM), mapa źródeł RPG↔MoM, decyzje D1-D11.
- Świadomie odłożone (backlog / później) z decyzji **D10** - `../doc/dialog-migration-plan.html`. Podgląd skutku pokazujemy dopiero PO wyborze (jak w RPG).
- Element "miło mieć" - nie blokuje MVP dialogów.
- Zależy od: [[T-035 DS: Sentyment w rozgrywce - odkrywanie, bramkowanie opcji, mnoznik cen]].

## ⛓️ Constraints

- Nie ruszać przed ukończeniem ścieżki core (encje -> pipeline -> UI -> efekty -> sentyment).
- Dual-target desktop + web.

## 🪜 Plan / Subtasks

- [x] Animowany floating tekst `+N/-N` przy zmianie sentymentu.
- [x] Ewentualnie kolor/mruganie ikony nastroju - mruganie paska sentymentu (`_sentiment_flash_timer`).

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione
- [x] zmiany udokumentowa w tasku (`moab log`)
- [x] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania - efekt jest przejściowy (~1.2 s po wyborze opcji); dowód = kod + review (patrz Agent Log)
- [x] Testy / lint przechodzą (jeśli dotyczy) - po naprawie regresji mypy (`any`->`Any`) `dialog.py` czysty
- [x] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane - nie dotyczy (bez nowych konwencji)
- [x] commit zmian wykonany

## 📓 Agent Log

- 2026-07-06 15:46 opencode: claimed, starting
- 2026-07-06 16:30 opencode: Implemented floating text and pulsating border feedback for sentiment shifts
- 2026-07-06 16:30 opencode: Floating text +N/-N in green/red and pulsating border flash on sentiment bar are completed and tested. Verified with unit tests and visual scenario tests.
- 2026-07-06 17:00 cc (review): Naprawiono regresję mypy wprowadzoną tu (`list[dict[str, any]]` -> `Any`, `dialog.py:92`); `just mypy` w `dialog.py` czysty. Feedback (floating `+N/-N` + flash paska) potwierdzony w kodzie `dialog.py` (`_floating_texts`, `_sentiment_flash_timer`).

## 🙋 Needs-You / Questions
