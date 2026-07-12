# SKILL: EN Dialog Sync

Translate English dialog files from their Polish source files, preserving all formatting tags, structure and frontmatter metadata.

## When to Use

Use this skill when asked to:
- "Translate EN dialog from PL"
- "Sync EN dialogs with PL"
- "Update English dialog files"
- "Odtwórz EN dialog z PL"

## File Locations

The dialog sources live in the `doc/` Obsidian vault. File names are the localized display names; the config key lives only in the frontmatter `aliases` list (the importer discovers files by alias, not by name).

- **PL source (source of truth):** `doc/PL/Postacie/<Polska Nazwa>.md` (e.g. `Barman Absyntnent.md`)
- **EN target:** `doc/EN/Characters/<English Name>.md` (e.g. `Barman Absinthrayner.md`)
- **Importer:** `project/dialog/markdown_importer.py`
- **Tests:** `tests/test_dialog_import.py`

To pair PL and EN files, match the frontmatter `aliases` key (e.g. `BARMAN_ABSINTHRAYNER`) or use the `name_PL`/`name_EN` columns of `project/config_model/characters.csv`.

## Characters (with IMPORTABLE_CHARACTERS status)

| Character key | PL file | EN file | Importable |
|---|---|---|---|
| HAMMER_HOAXHEART | Kowal Kłamca.md | Hammer Hoaxheart.md | Yes |
| BARMAN_ABSINTHRAYNER | Barman Absyntnent.md | Barman Absinthrayner.md | Yes |
| CLAPBACK_SWORD | Miecz Ciętej-riposty.md | Clapback Sword.md | Yes |
| POTIONEER_PUZZLEMINT | Zielarka Zmora.md | Potioneer Puzzlemint.md | Yes |
| MADAME_SARCASMIA | Madame Sarkażmijka.md | Madame Sarcasmia.md | Yes |
| MARRY | Marysia.md | Marry.md | No (legacy prose) |
| ROB | Kuba.md | Rob.md | No (legacy prose) |

## Frontmatter Sync Rules

**PL frontmatter is the source of truth** for character metadata. The importer reads ONLY the PL file for these fields; the EN copies exist for the author's convenience and must be kept in sync by this skill:

- `sprite:` - asset folder name from `project/assets/NinjaAdventure/characters/`
- `friendly:` - base sentiment 0..1 (initial NPC sentiment = friendly * 100)
- sentiment weights: `kind`, `weak`, `angry`, `smart`, `funny` (integers -2..2; `neutral` and `technical` are implicit 0 and never listed)
- `aliases:` - ONLY the config key (e.g. `BARMAN_ABSINTHRAYNER`); the display name is the file name itself

EN-only frontmatter field: `PL: "[[<Polska Nazwa>]]"` backlink. PL-only field: `EN: "[[<English Name>]]"` backlink.

When syncing: copy `sprite`/`friendly`/weights values from PL to EN verbatim. Never edit them in EN independently.

## Formatting Tags to Preserve

These tags appear in PL and must be carried over to EN exactly:

- `[loc]` - location references
- `[quest]` - quest names
- `[char]` - character names (auto-wrapped by importer on wikilinks)
- `[item]` - item names
- `[bold]...[/bold]` - bold text
- `[shadow]...[/shadow]` - shadow text
- `[dark]...[/dark]` - dark text
- `[b]...[/b]` - alternate bold
- `[u]...[/u]` - underline
- `:emoji_name:` - emoji codes
- `[SENTIMENT-X]` - sentiment value node result
- `[act]` - action marker

## Dialog Structure

- Node headings are `## <number>` (e.g. `## 000`, `## 015-end`); everything before the first numeric heading (frontmatter, `# Info` section) is ignored by the importer.
- Option lines: `* [[#001]] 1😇: Option text` - the emoji maps to canonical sentiment names (😇 kind, 😢 weak, 😐 neutral, 😡 angry, 🧠 smart, 😉 funny, 🤖 technical). PL and EN must have the same node keys and option counts/order.
- Resume links: `[[#KEY]]` on its own line right under a `-end` heading.
- Character wikilinks in text: `[[<File Name>]]` or `[[<File Name>|<declined form>]]` - the target identifies the character (file name or config key), the pipe part is the display text (grammatical declension). In EN translate the display form; link targets should point at the EN file names.

## Workflow

1. Read the PL file to understand character voice, humor, and formatting
2. Read the EN file to see current state
3. Sync EN frontmatter metadata from PL (see Frontmatter Sync Rules)
4. Translate all EN text from PL, matching tone and personality
5. Preserve ALL formatting tags exactly as they appear in PL
6. Preserve node structure (headings, options, resume links)
7. Run verification (full pipeline MD -> characters.csv -> config.json):

```bash
just import-dialogs "<Character Name>"
```

8. Run tests:

```bash
.venv/bin/python tests/test_dialog_import.py
```

## Style Guide by Character

### Barman Absinthrayner
- Friendly, casual tavern keeper
- Uses gossip and humor
- Warm but not overly formal

### Hammer Hoaxheart
- Grumpy, hostile blacksmith
- Short, curt responses
- Impatient with questions

### Clapback Sword
- Sarcastic, grumpy sword companion
- Dark humor, self-deprecating
- Informal, conversational

### Potioneer Puzzlemint
- Elderly herbalist
- Slightly condescending tone
- Nature and herb references

## Key Rules

- Never modify PL files
- Always verify with `just import-dialogs` after changes
- Option links use `[[#KEY]]` format
- Resume links use `[[#KEY]]` on a separate line under the `-end` heading
- Wikilinks: `[[File Name]]`, `[[File Name|declined display form]]`, or `[[CHAR_KEY]]` (all resolve to `[char]...[/char]` at import)
