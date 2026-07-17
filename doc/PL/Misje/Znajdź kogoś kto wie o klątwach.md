---
aliases:
  - Q03
---

# Znajdź kogoś kto wie o klątwach

Wątek śledczy: kto się zna, gdzie jej szukać, którędy tam dojść. Parasol domyka
się sam, gdy wszystkie trzy kroki są zrobione.

## S00_LEARN_ABOUT_CURSE

**Tytuł**: Znajdź kogoś kto wie o klątwach

W tej okolicy nikt nie zaglądał do książki od czasów, gdy karczma miała jeszcze cały dach. Ale ktoś, gdzieś, musi wiedzieć o klątwach coś więcej niż plotki.

**Completion**: all_subquests
**Requires**: Q01_S01_LEARN_ABOUT_CURSE
**Sukces**: Wiesz już, kto się na tym zna, gdzie jej szukać i którędy tam dojść. Trzy odpowiedzi i ani grama magii.
**Nagroda**: max_health=10

## S01_WHO_HAS_MORE_KNOWLEDGE

**Tytuł**: Kto ma wiedzę o magii?

Zielarka warzy mikstury i pamięta wyraźnie więcej, niż mówi. Może pamięta też kogoś, kto zna się na rzeczach oficjalnie zakazanych.

**Completion**: test
**Test**: visited("POTIONEER_PUZZLEMINT", "014") or visited("POTIONEER_PUZZLEMINT", "017")
**Sukces**: Kiedyś wołali na nią Mariolka. Teraz mówią Bibliofilistka des Informacja i podobno pilnuje zakazanych ksiąg w tajnej bibliotece.

## S02_WHERE_TO_FIND_THIS_PERSON

**Tytuł**: Gdzie znaleźć tę osobę?

Imię już jest. Zostaje drobiazg: adres. Kowal bywa w świecie częściej niż reszta wioski, więc może akurat coś wie.

**Completion**: test
**Test**: visited("HAMMER_HOAXHEART", "009")
**Sukces**: Kowal do miasta nie jeździ i nie zamierza zacząć. Wie za to dokładnie, kto w tej wiosce gada ze wszystkimi przybyszami.

## S03_HOW_TO_GET_THERE

**Tytuł**: Jak tam dotrzeć?

Miasto jest gdzieś na północy. "Gdzieś" to stanowczo za mało, żeby ruszać w drogę.

**Completion**: test
**Test**: visited("BARMAN_ABSINTHRAYNER", "017")
**Sukces**: Dwa dni na północ, za Splątanym lasem irytacji skręcić na wschód. Barman w mieście nie był, ale trasę zna na pamięć.
