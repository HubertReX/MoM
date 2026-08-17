# Barks - shared pools

The EN mirror of [Barki](../PL/Barki.md). PL is the source of truth: it decides
which pools exist, in what order and under what conditions. This file supplies
**only the translated text**, bullet for bullet, under the same `##` pool keys.

A pool whose bullet count differs from PL is a hard import error - the two files
would silently describe different behaviour.

No pools yet. Add them here only after the PL file has them.


## VILLAGERS

Pool for village residents.

- [`time_of_day("morning") or time_of_day("day")`] Good morning
- [`time_of_day("evening") or time_of_day("night")`] Good evening
- [`sentiment > 70`] Top of the morning to ya
- [`sentiment > 80`] Howdy-do
- [`on_map(`[[the Lost Cork Tavern|Lost Cork Tavern]]`)`] Sure stinks in here
- [`on_map(`[[Blunderhaven]]`) and time_of_day("day")`] Lovely weather we're having
- [`on_map(`[[Blunderhaven]]`) and time_of_day("night")`] Nights are chilly again
- [`activity("stand")`] Work won't do itself
- [`activity("idle")`] Sure is boring around here
- [`activity("wander")`] Could go for a bite
- [`activity("wander")`] Some rest at last
- [`quest_done(`[[Q01_S01 Learn more about the curse]]`)`] Oh, look, here comes our walking disaster
- [`not quest_done(`[[Q01_S01 Learn more about the curse]]`)`] Hmm, who's this fresh meat

## FARM_ANIMALS

All critters

- Moo
- Moo?
- Awoooo
- woof, woof
- meow
- mEOw
