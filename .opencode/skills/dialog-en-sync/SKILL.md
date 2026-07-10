# SKILL: EN Dialog Sync

Translate English dialog files from their Polish source files, preserving all formatting tags and structure.

## When to Use

Use this skill when asked to:
- "Translate EN dialog from PL"
- "Sync EN dialogs with PL"
- "Update English dialog files"
- "Odtwórz EN dialog z PL"

## File Locations

- **PL source:** `project/assets/dialogs/PL/<Character_Name>.md`
- **EN target:** `project/assets/dialogs/EN/<Character_Name>.md`
- **Importer:** `project/dialog/markdown_importer.py`
- **Tests:** `tests/test_dialog_import.py`

## Characters (with IMPORTABLE_CHARACTERS status)

| Character | Importable | Notes |
|---|---|---|
| Hammer Hoaxheart | Yes | Grumpy blacksmith, hostile, short responses |
| Barman Absinthrayner | Yes | Friendly tavern keeper, casual, helpful |
| Clapback Sword | Yes | Sarcastic sword companion, dark humor |
| Potioneer Puzzlemint | Yes | Elderly herbalist, condescending, nature-focused |
| Madame Sarcasmia | Yes | Already fully translated, verify only |
| Marry | No (config only) | Frontmatter/alias only |
| Rob | No (config only) | Frontmatter/alias only |

## Formatting Tags to Preserve

These tags appear in PL and must be carried over to EN exactly:

- `[loc]` — location references
- `[quest]` — quest names
- `[char]` — character names (auto-wrapped by importer on wikilinks)
- `[item]` — item names
- `[bold]...[/bold]` — bold text
- `[shadow]...[/shadow]` — shadow text
- `[dark]...[/dark]` — dark text
- `[b]...[/b]` — alternate bold
- `[u]...[/u]` — underline
- `:emoji_name:` — emoji codes
- `[SENTIMENT-X]` — sentiment value (0-10)
- `[act]` — action marker

## Workflow

1. Read the PL file to understand character voice, humor, and formatting
2. Read the EN file to see current state
3. Translate all EN text from PL, matching tone and personality
4. Preserve ALL formatting tags exactly as they appear in PL
5. Preserve node structure (headers, options, resume links)
6. Run verification:

```bash
.venv/bin/python -m project.dialog.markdown_importer project/assets/dialogs/EN/<Character_Name>.md
```

7. Run tests:

```bash
.venv/bin/python -m pytest tests/test_dialog_import.py -v
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
- Always verify with importer after changes
- Option links use `[[#KEY]]` format
- Resume links use `[[#KEY]]` on separate line
- Heading inline format `### 990-end [001](#001)` preserved for backward compat
- Wikilinks: `[[CHAR_KEY]]` (simple) or `[[lang/file|CHAR_KEY]]` (pipe)
