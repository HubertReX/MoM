---
id: T-019
title: ręczny zapis screenshot (F6) nie działa
status: needs-you
owner: human
priority: p2
type: bug
agent: opencode
created: 2026-07-04
updated: 2026-07-04
tags:
  - task
state: review
---

# T-019 — ręczny zapis screenshot (F6) nie działa

klawisz F6 powinien uruchomić logikę ręcznego zapisu zdjęcia gry (screenshot). WAŻNE: nie korzystaj chwilowo z agent ss-reviewer bo jego limit tokenów się wyczerpał - użyj własnych miejętności vision jeśli to konieczne.

## 🎯 Goal / Outcome


- [x] Po naciśnięciu F6 screenshot zapisuje się w odpowiednim katalogu

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

![[agent_20260704_T-019_screenshot_f6.png]]

## 📓 Agent Log

- 2026-07-04 23:17 opencode: claimed, starting
- 2026-07-04 23:21 opencode: Naprawiono blad z niepoprawnym zapisem zrzutu ekranu (F6) przy wylaczonych shaderach (USE_SHADERS = False). Logika save_screenshot polegala wylacznie na buforze OpenGL z postprocessingu, przez co w trybie bez shaderow wchodzila w nieskonczona petle i nie zapisywala pliku. Teraz dla trybu bez shaderow zapisuje self.screen bezposrednio na dysk przy uzyciu pygame.image.save i od razu resetuje stan INPUTS['screenshot'].
- 2026-07-04 23:21 opencode: Zaimplementowano obsluge zapisu zrzutu ekranu w trybie z wylaczonymi shaderami (USE_SHADERS = False). Zrzut ekranu jest teraz zapisywany przy uzyciu pygame.image.save, co rozwiazuje blad nieskonczonej petli. Aby przetestować, wystarczy uruchomic gre i nacisnac klawisz F6.
- 2026-07-04 23:21 opencode: Naprawiono manualny zapis zrzutu ekranu (F6) w trybie bez shaderow. Zrzut ekranu jest teraz zapisywany przy uzyciu pygame.image.save, a powiadomienie wyswietla sie poprawnie przy uzyciu aktywnego managera powiadomien stanu gry.


## 🙋 Needs-You / Questions

