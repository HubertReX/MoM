# Info

[quest-system-ssis-2026-07-16.html](file://Users/hnafalsk/Projects/MoM/doc/_attachements/quest-system-ssis-2026-07-16.html)

## Questy główne i podquesty

### 01_main_01 (eval)
- test: `characters["troll_001"].is_met == True`
- bonus: `max_health:50`
- unlocks: —
- podquesty:
  - 01_get_gloves: test=`'gloves' in hero.inventory.items`, bonus=`eloquence:15`, unlocks=02_fight_fairy
  - 02_fight_fairy: test=`characters["fairy_001"].is_met == True and characters["fairy_001"].hp <= 0`, bonus=`hp:15`, unlocks=03_tomb_rider
  - 03_tomb_rider: test=`curr_loc.name_key=="MAP08_MAZE_06x11" and curr_loc.is_searched`, bonus=`health:100`, unlocks=—

### 02_game_mechanics (agg)
- test: `False`
- bonus: `max_health:20`
- unlocks: —
- podquesty:
  - 01_johnny_walker: test=`hero.unique_loc_visited_cnt >= 100`, bonus=`max_items:2`, unlocks=—
  - 02_items_collector: test=`len(hero.inventory.items) >= 3`, bonus=`hp:20`, unlocks=03_speed_run
  - 03_lucky_luke_beginner: test=`hero.searched_loc >= 5`, bonus=`agility:5`, unlocks=04_lucky_luke_master
  - 04_lucky_luke_master: test=`hero.searched_loc >= 10`, bonus=`agility:15`, unlocks=—

### 03_speed_run (agg)
- test: `false`
- bonus: `max_health:20`
- unlocks: —
- podquesty:
  - 01_coc_long: test=`len(coc) > 0`, bonus=`agility:5`, unlocks=02_coc_2in1
  - 02_coc_2in1: test=`coc != coc.upper()`, bonus=`agility:5`, unlocks=03_coc_comment
  - 03_coc_comment: test=`"_" in coc`, bonus=`agility:5`, unlocks=04_coc_for
  - 04_coc_for: test=`hero.coc_for`, bonus=`agility:5`, unlocks=05_coc_until
  - 05_coc_until: test=`hero.coc_until`, bonus=`agility:5`, unlocks=06_coc_cmd
  - 06_coc_cmd: test=`hero.coc_cmd`, bonus=`agility:5`, unlocks=—

### Q00_S00_WHAT_IS_GOING_ON (char)
- test: `characters["CLAPBACK_SWORD_001"].dialog.key == "015"`
- bonus: `agility:10`
- unlocks: Q01_S00_BREAK_THE_CURSE
- podquesty:

### Q01_S00_BREAK_THE_CURSE (agg)
- test: `False`
- bonus: `max_health:100`
- unlocks: —
- podquesty:
  - Q01_S01_LEARN_ABOUT_CURSE: test=`characters["BARMAN_ABSINTHRAYNER_001"].dialog.key == "012"`, bonus=`agility:10`, unlocks=Q03_S00_LEARN_ABOUT_CURSE
  - Q01_S05_BREAK_THE_CURSE_MEET_MADAME_SARCASMIA: test=`characters["MADAME_SARCASMIA_001"].dialog.key == "SARCASMIA_AA_BACK_SO_SOON"`, bonus=`eloquence:50`, unlocks=Q02_S00_TRINKETS_FOR_SARCASMIA
  - Q01_S06_BREAK_THE_CURSE_GAIN_POTION_CURSE_NO_MORE: test=`"POTION_CURSE_NO_MORE" in hero.inventory.items`, bonus=`health:70`, unlocks=Q01_S07_BREAK_THE_CURSE_FIND_A_SAFE_PLACE
  - Q01_S07_BREAK_THE_CURSE_FIND_A_SAFE_PLACE: test=`False`, bonus=`agility:100`, unlocks=—

### Q02_S00_TRINKETS_FOR_SARCASMIA (agg)
- test: `False`
- bonus: `agility:50`
- unlocks: Q01_S06_BREAK_THE_CURSE_GAIN_POTION_CURSE_NO_MORE
- podquesty:
  - Q02_S01_TRINKETS_FOR_SARCASMIA_MERMAIDS_TEAR: test=`"MERMAIDS_TEAR" in hero.inventory.items`, bonus=`agility:10`, unlocks=—
  - Q02_S02_TRINKETS_FOR_SARCASMIA_GNOMES_WHISKER: test=`"GNOMES_WHISKER" in hero.inventory.items`, bonus=`agility:10`, unlocks=—
  - Q02_S03_TRINKETS_FOR_SARCASMIA_PHOENIX_FEATHER: test=`"PHOENIX_FEATHER" in hero.inventory.items`, bonus=`agility:10`, unlocks=—

### Q03_S00_LEARN_ABOUT_CURSE (agg)
- test: `False`
- bonus: `agility:10`
- unlocks: —
- podquesty:
  - Q03_S01_WHO_HAS_MORE_KNOWLEDGE: test=`characters["POTIONEER_PUZZLEMINT_001"].dialog.key == "014" or characters["POTIONEER_PUZZLEMINT_001"].dialog.key == "017"`, bonus=`-`, unlocks=—
  - Q03_S02_WHERE_TO_FIND_THIS_PERSON: test=`characters["HAMMER_HOAXHEART_001"].dialog.key == "009"`, bonus=`agility:10`, unlocks=—
  - Q03_SO3_HOW_TO_GET_THERE: test=`characters["BARMAN_ABSINTHRAYNER_001"].dialog.key == "017"`, bonus=`-`, unlocks=—

## Pułapki portowania
1. eval na całym cfg (płytka blokada __builtins__)
2. tylko pierwsza niezerowa nagroda (break w apply_quest_bonus)
3. test_total działa tylko gdy test_progress aktywne
4. unlocks niespójnie typowane (false/null/string)
5. graf to DAG, nie drzewo (międzyłańcuchowe unlocks)
6. max_items trzymane na hero.inventory
7. literówka klucza Q03_SO3_ (powinno być S03)
8. clamp health zawsze po nagrodzie
