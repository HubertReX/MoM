# 📋 Scenariusze testowe (stan drzewa roboczego: 18)

Filtrowanie per backend robi pole `platform` w `scenarios.json`: brak pola = oba backendy; `"web"` = tylko web. **Desktop: 17, Web: 18.**

| #   | Scenariusz                 | Desktop | Web | Co weryfikuje                                                  | Asercje / setup              |
| --- | -------------------------- | :-----: | :-: | -------------------------------------------------------------- | ---------------------------- |
| 1   | Display Settings Flow      |    ✓    |  ✓  | Nawigacja do ustawień, zmiana rozdzielczości, weryfikacja      | -                            |
| 2   | Save and Load Basic        |    ✓    |  ✓  | Quick save (F5) + quick load (F9)                              | -                            |
| 3   | Quick Save and Load        |    ✓    |  ✓  | Zapis, ruch, wczytanie wraca na pozycję startową               | -                            |
| 4   | Death then Load            |    ✓    |  ✓  | Ekran śmierci → wczytanie zapisu                               | -                            |
| 5   | Multiple Quick Saves       |    ✓    |  ✓  | Dwa sloty zapisu, wybór drugiego                               | `file_exists` save_0, save_1 |
| 6   | Auto Save on Map Change    |    ✓    |  ✓  | Auto-zapis przy zmianie mapy                                   | `file_exists` save_0         |
| 7   | Corrupt Save Handling      |    ✓    |  ✓  | Uszkodzony zapis po cichu ignorowany                           | setup: corrupt save_0        |
| 8   | Web Save in localStorage   |    —    |  ✓  | Zapis trafia do `localStorage` (web-only)                      | `localstorage_exists` save_0 |
| 9   | Empty Slot Load            |    ✓    |  ✓  | Pusty LoadPanel gdy brak zapisów                               | -                            |
| 10  | Load from Main Menu        |    ✓    |  ✓  | Wczytanie z menu głównego                                      | `file_exists` save_0         |
| 11  | UI Flow - Full Save Load   |    ✓    |  ✓  | Pełny przepływ zapis/wczytanie przez UI                        | -                            |
| 12  | TextInput Basic            |    ✓    |  ✓  | Widget TextInput: filtry charset, max_length, hasło, backspace | -                            |
| 13  | Manage Saves               |    ✓    |  ✓  | Zmiana nazwy + usuwanie slotu zapisu                           | -                            |
| 14  | In-Game LoadPanel Paused   |    ✓    |  ✓  | LoadPanel zamraża grę; R = rename, nie reload                  | -                            |
| 15  | Maze Save Blocked          |    ✓    |  ✓  | Zapis zablokowany w lochu/labiryncie                           | -                            |
| 16  | In-Game Reload Confirm     |    ✓    |  ✓  | R w grze = dialog potwierdzenia reload                         | -                            |
| 17  | In-Game Esc Shows Continue |    ✓    |  ✓  | Esc w grze = menu z Continue                                   | -                            |
| 18  | Load from Menu then Esc    |    ✓    |  ✓  | Po wczytaniu Esc pokazuje menu, nie wychodzi                   | -                            |

