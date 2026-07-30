# Źródła i licencje dźwięków

Wszystkie pliki pochodzą z [Pixabay](https://pixabay.com/service/license-summary/)
(licencja Pixabay Content License - wolno używać komercyjnie, bez atrybucji, ale
atrybucja jest tu zachowana, żeby dało się wrócić do oryginału).

Assety przeniesiono z poprzedniej gry autora (`~/Projects/RPG/sounds/`), gdzie leżały
jako mp3 (łącznie 60 MB). Do MoM trafiają skonwertowane do ogg vorbis - patrz
[Konwersja](#konwersja). Mapowanie plików na mapy i eventy siedzi w
`project/config_model/audio.toml`, nie tutaj.

## Muzyka (`music/`)

| Plik w MoM | Plik źródłowy (RPG) | Źródło |
| --- | --- | --- |
| `this-is-epic.ogg` | `this-is-epic-115231.mp3` | <https://pixabay.com/music/beats-this-is-epic-115231/> |
| `best-adventure-ever.ogg` | `best-adventure-ever-122726.mp3` | <https://pixabay.com/music/fantasy-dreamy-childrens-best-adventure-ever-122726/> |
| `deep-in-the-dell.ogg` | `deep-in-the-dell-126916.mp3` | <https://pixabay.com/music/fantasy-dreamy-childrens-deep-in-the-dell-126916/> |
| `let-the-mystery-unfold.ogg` | `let-the-mystery-unfold-122118.mp3` | <https://pixabay.com/music/fantasy-dreamy-childrens-let-the-mystery-unfold-122118/> |
| `scary-spooky-ambient.ogg` | `scary-spooky-creepy-horror-ambient-dark-piano-cinematic-115052.mp3` | <https://pixabay.com/music/electronic-scary-spooky-creepy-horror-ambient-dark-piano-cinematic-115052/> |
| `caves-of-dawn.ogg` | `caves-of-dawn-10376.mp3` | <https://pixabay.com/music/ambient-caves-of-dawn-10376/> |
| `tubular-bell-of-death.ogg` | `tubular-bell-of-death-89485.mp3` | <https://pixabay.com/de/sound-effects/musical-tubular-bell-of-death-89485/> |
| `to-the-death.ogg` | `to-the-death-159171.mp3` | <https://pixabay.com/music/video-games-to-the-death-159171/> |
| `stranger-things.ogg` | `synthwave-stranger-things-124008.mp3` | <https://pixabay.com/music/synthwave-stranger-things-124008/> |

## Efekty (`sfx/`)

| Plik w MoM | Plik źródłowy (RPG) | Uwagi |
| --- | --- | --- |
| `male_hurt7.ogg` | `male_hurt7-48124.mp3` | |
| `punch-2.ogg` | `punch-2-123106.mp3` | |
| `body-fall.ogg` | `body-fall-47877.mp3` | |
| `tubular-bell-of-death.ogg` | `tubular-bell-of-death-89485.mp3` | przycięte do 3 s (wersja z `music/` jest pełna, do pętli) |
| `item.ogg` | `item-39146.mp3` | |
| `item-equip.ogg` | `item-equip-6904.mp3` | |
| `cardboard-box-drop.ogg` | `cardboard-box-drop-hit-handling-32135.mp3` | przycięte do 2 s |
| `coins27.ogg` | `coins27-36030.mp3` | |
| `game-level-complete.ogg` | `game-level-complete-143022.mp3` | |
| `failfare.ogg` | `failfare-86009.mp3` | |
| `success-fanfare-trumpets.ogg` | `success-fanfare-trumpets-6185.mp3` | |
| `backpack.ogg` | `backpack-34942.mp3` | przycięte do 2 s |
| `game-bonus.ogg` | `game-bonus-144751.mp3` | |
| `stairwellwalk.ogg` | `stairwellwalk-107715.mp3` | przycięte do 2 s |
| `voice-hero.ogg` | `voicepack-64401.mp3` | pierwsza próbka paczki (`trim 0.11 1.50`) |
| `voice-char.ogg` | `voicepack-64401.mp3` | druga próbka paczki (`trim 1.85 1.68`) |
| `dreamy-rain-ambience.ogg` | `universfield-dreamy-rain-ambience-454686.mp3` | |
| `error-notification-08.ogg` | `universfield-error-notification-08-206492.mp3` | |


Pełna lista plików w paczce źródłowej (także tych, których MoM nie używa) jest w
`~/Projects/RPG/sounds/sfx/sfx.txt` i `~/Projects/RPG/sounds/music/sources.txt` oraz na portalu **Pixabay**:

- [SSiS music](https://pixabay.com/accounts/collections/17714023/)
- [SSiS effects](https://pixabay.com/accounts/collections/17714217/)


## Konwersja

Homebrew ffmpeg 8.1.1 jest zbudowany **bez `libvorbis`** (ma tylko eksperymentalny
enkoder `vorbis`, który obsługuje wyłącznie stereo), więc kodowanie idzie przez
`sox`, linkowanego z prawdziwym libvorbis. Parametry odpowiadają budżetowi z zadania
D01 (mono, ~50-55 kbps dla muzyki; ≤ 1,5 MB na utwór, ≤ 10 MB na cały katalog):

```bash
# muzyka: mono 44,1 kHz, vorbis -C 1 (~54 kbps)
sox in.mp3 -C 1 -c 1 -r 44100 out.ogg

# SFX: mono 22,05 kHz, vorbis -C 2, obcięta cisza na końcu
sox in.mp3 -C 2 -c 1 -r 22050 out.ogg reverse silence 1 0.05 0.5% reverse

# SFX ciągnące się sekundami - dodatkowo twarde przycięcie długości
sox in.mp3 -C 2 -c 1 -r 22050 out.ogg trim 0 2 reverse silence 1 0.05 0.5% reverse
```

Granice próbek w `voicepack-64401.mp3` wyznaczono przez
`ffmpeg -i voicepack-64401.mp3 -af silencedetect=noise=-30dB:d=0.1 -f null -`.
