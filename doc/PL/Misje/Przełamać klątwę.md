---
aliases:
  - Q01
---

# Przełamać klątwę

Główny wątek fabularny. Parasol jest `manual` - domyka go dopiero treść, której jeszcze nie ma (S06/S07, dług treści D15), a nie warunek.

[[O co tu chodzi]]

## S00_BREAK_THE_CURSE

**Tytuł**: Przełamać klątwę

Klątwa nie zdejmie się sama. Ktoś pewnie wie jak to działa, ktoś pewnie umie ją zdjąć, a ktoś - czyli [char]Ty[/char] - musi pozbierać jedno z drugim do kupy.

**Completion**: manual
**Requires**: Q00_S00_WHAT_IS_GOING_ON
**Sukces**: Klątwa złamana! Miecz oczywiście twierdzi, że to była głównie jego zasługa.
**Nagroda**: max_health=20
**Nagroda**: damage=5

## S01_LEARN_ABOUT_CURSE

**Tytuł**: Dowiedz się więcej o klątwie

Bajki dla dzieci i bajania bardów to za mało, żeby cokolwiek z tym zrobić. W [loc]karczmie[/loc] mówi się wszystkim i o wszystkich - trzeba tylko zapytać właściwej osoby o właściwą rzecz.

**Completion**: test
**Test**: visited("BARMAN_ABSINTHRAYNER", "012")
**Sukces**: [char]Barman[/char] zna kogoś od mikstur. Stara, ślepa, mieszka koło lasu i czasem ludziom robi się po jej miksturach gorzej. Rekomendacja jak marzenie.

## S05_MEET_MADAME_SARCASMIA

**Tytuł**: Spotkaj się z [char]Sarkażmijką[/char]

Wiedzieć o klątwie to jedno, a zdjąć ją to zupełnie inna para kaloszy. Podobno jest ktoś, kto się takimi rzeczami para - i podobno ma o sobie bardzo wysokie mniemanie.

**Completion**: test
**Test**: visited("MADAME_SARCASMIA", "001")
**Requires**: Q01_S01_LEARN_ABOUT_CURSE
**Sukces**: [char]Sarkażmijka[/char] wysłuchała, westchnęła dramatycznie i uznała, że to pewnie zwykły pech. Pomóc jednak może, ale za drobną przysługę.
