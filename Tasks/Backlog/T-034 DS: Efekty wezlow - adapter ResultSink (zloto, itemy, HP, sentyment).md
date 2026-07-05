---
id: T-034
title: DS: Efekty wezlow - adapter ResultSink (zloto, itemy, HP, sentyment)
status: backlog
owner: human
priority: p2
type: feature
agent:
created: 2026-07-05
updated: 2026-07-05
tags:
  - task
---

# T-034 - DS: Efekty wezlow (adapter ResultSink)

## 🎯 Goal / Outcome

- [ ] Adapter `ResultSink` (Protocol) mapujący 7 kategorii `NodeVisitResult` na systemy MoM: złoto, `Inventory`, HP gracza, sentyment NPC
- [ ] Silnik dialogu bez importów z gry; gra dostarcza konkretny sink (odwrócona zależność)
- [ ] Flaga `visited` chroni przed dublem - efekt liczony raz przy pierwszej wizycie węzła
- [ ] Test: węzeł z `MONEY+` / `ITEMS+` zmienia stan gracza dokładnie jednokrotnie

## 🧭 Context

- **Kontekst wspólny (przeczytaj najpierw):** [[DS-epic-brief]] - lokalizacje repo (RPG i MoM), mapa źródeł RPG↔MoM, decyzje D1-D11.
- Decyzja **D8** (cienki adapter) - `../doc/dialog-migration-plan.html`. Źródło: RPG `main.py:process_result`.
- MoM: `Inventory`, hero/health, klucze itemów z `project/config_model/items.csv`.
- Zależy od: [[T-029 DS: Encje dialogu i budowa grafu (DialogNode, Option, Result + init_dialog)]], [[T-023 DS: Model NPC i pola sentymentu (dialog_key, sentiment, disposition)]], [[T-033 DS: UI DialogPanel - lista opcji i wybor (hybryda kursor + 1-9 + mysz)]].
- Odblokowuje: [[T-030 DS: Persystencja stanu rozmowy w save-load (oba backendy + testy korupcji)]], [[T-035 DS: Sentyment w rozgrywce - odkrywanie, bramkowanie opcji, mnoznik cen]].

## ⛓️ Constraints

- Nazwy itemów w efektach muszą zgadzać się z kluczami `items.csv` (walidacja przy imporcie - łączy się z pipeline).
- Dual-target desktop + web.
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [ ] `ResultSink` (Protocol) + `apply_result()` (match po kategorii).
- [ ] Konkretny `GameSink` spięty z Inventory/hero/HP/sentyment.
- [ ] Ochrona `visited` przed podwójnym naliczeniem.
- [ ] Test jednokrotności efektu.

## ✅ Definition of Done

- [ ] Kryteria z Goal spełnione
- [ ] zmiany udokumentowa w tasku (`moab log`)
- [ ] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [ ] Testy / lint przechodzą (jeśli dotyczy)
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

## 📓 Agent Log

## 🙋 Needs-You / Questions
