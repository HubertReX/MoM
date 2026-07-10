---
aliases:
  - MADAME_SARCASMIA
---
# **Madame Sarcasmia**

translation: [**Madame Sarcasmia**](../PL/Madame_Sarcasmia.md)

* friendly=0.5
* 😇kind+
* 😢week--
* 😐neutral
* 😡angry-
* 🧠smart+
* 😉funny++

## EN

### 000

* Well, well, well, what do we have here? Another lost soul seeking a cure, I presume? Raises an eyebrow :wondering:.

* [001](#001) 1[not visited("005")]😇: Uh, yes, actually. I heard you're a powerful sorceress, and I was hoping you could help me break this… age-old curse of perpetual bad luck.
* [001](#001) 2[not visited("005")]😉: No, I just thought your chamber could use some redecorating.
* [007](#007) 3[not visited("005")]🧠: Can you tell me a bit more about yourself?
* [011](#011) 4[visited("005")]😐: I'm back. Any leads for me yet?

### 001

* Sighs dramatically: Ah, the age-old curse predicament. How original :dots:. Fine, I suppose I could assist you, but magic doesn't come cheap, you know.

* [002](#002) 1😇: I'll do whatever it takes. Just name your price.
* [002](#002) 2😉: Well, tough luck, because I was planning to pay you in gratitude.

### 002

* Oh, I will, don't you worry. You see, darling, I need a few trinkets for a little… project. Retrieve them for me, and I might just whip up a potion that, in theory, could break your curse. Or turn you into a newt. We'll see.

* [003](#003) 1😇: Trinkets, you say? What exactly are we talking about?
* [003](#003) 2😉: This should be a piece of cake, right?

### 003

* Oh, nothing much:
[act]*[/act] the [item]tear[/item] of the [char]Melancholic Mermaid[/char],
[act]*[/act] a [char]Mopey Phoenix[/char] [item]feather[/item] plucked during a solar eclipse,
[act]*[/act] and a [item]whisker[/item] of the [char]Grumpy Gnome[/char].

Should be a piece of cake. Rolls eyes :dots:.

* [004](#004) 1😇: Oh, I'm new around here. Could you tell me where to find all this?
* [004](#004) 2😉: Really?

### 004

* Nods Indeed:
[act]*[/act] Rumor has it, the [char]Melancholic Mermaid[/char] spends her time sobbing on a lonely rock near the [loc]Misty Mire[/loc].
[act]*[/act] The [char]Mopey Phoenix[/char] frequents the [loc]Cliffside Clamor[/loc], because of course it does.
[act]*[/act] And the [char]Grumpy Gnome[/char], well, let's just say you might find him in the [loc]Quicksand Quagmire[/loc].

Good luck, dearie.

* [005](#005-end) 1😐: [char]Mermaid[/char] [item]tear[/item], [char]Mopey Phoenix[/char] [item]feather[/item], and [char]Grumpy Gnome[/char] [item]whisker[/item]. Got it.
* [005](#005-end) 2😉: I'll be back with your trinkets before you can say "abracadabra" — just have that potion ready.
* [006](#006-end) 3😢: That sounds… awful.

### 005-end [011](#011)

* Now, off you go. Chop-chop. And if you manage to survive, I'll consider brewing that "cure" you're so desperate for. No refunds, though. Ta-ta!

### 006-end [011](#011)

* Oh, don't be such a princess :love:. Now, off you go. Chop-chop. And if you manage to survive, I'll consider brewing that "cure" you're so desperate for. No refunds, though. Ta-ta!

### 007

* Oh, goody! Questions! Fire away, and try not to bore me :dots:.

* [008](#008) 1[not selected("007to008_1")]🧠: What's the deal with all the sarcasm? Can't you be serious for a moment?
* [009](#009) 2[not selected("007to009_2")]🧠: Are there any recent developments or news around these parts?
* [010](#010) 3[not selected("007to010_3")]🧠: One more question. What's your favorite thing about these lands?
* [000](#000) 9😐: Alright, I've learned enough.

### 008

* Sarcasm is my coping mechanism for dealing with the mundane and the insipid. Life's too short to be serious all the time.

* [000](#000) 1😐: Alright, I've learned enough.
* [007](#007) 9😐: I see, thank you.

### 009

* Recent developments? Well, the local [char]goblin[/char] population is planning a "[shadow]Goblin Got Talent[/shadow]" show. I can't wait to see their interpretive dance numbers.

* [000](#000) 1😐: Alright, I've learned enough.
* [007](#007) 9😐: I see, thank you.

### 010

* My favorite thing? Definitely the way the moonlight reflects off the [loc]Treacherous Cliffs[/loc], casting an eerie glow that perfectly complements my dramatic nature.

* [000](#000) 1😐: Alright, I've learned enough.
* [007](#007) 9😐: I see, thank you.

### 011

* Ah, back so soon, I see. Do tell, have you managed to scrounge up my little collection of trinkets?

* [012](#012) 1[has_item("MERMAIDS_TEAR") and has_item("GNOMES_WHISKER") and has_item("PHOENIX_FEATHER")]😐: Indeed, I have all three items you requested. A [char]Mermaid's[/char] [item]tear[/item], a [char]Phoenix[/char] [item]feather[/item], and a [char]Gnome's[/char] [item]whisker[/item].
* [013](#013) 2[not has_item("MERMAIDS_TEAR") and (has_item("GNOMES_WHISKER") or has_item("PHOENIX_FEATHER"))]😢: Well, I don't have the [char]Mermaid's[/char] [item]tear[/item].
* [014](#014) 3[not has_item("GNOMES_WHISKER") and (has_item("MERMAIDS_TEAR") or has_item("PHOENIX_FEATHER"))]😢: Well, I don't have the [char]Gnome's[/char] [item]whisker[/item].
* [015](#015) 4[not has_item("PHOENIX_FEATHER") and (has_item("GNOMES_WHISKER") or has_item("MERMAIDS_TEAR"))]😢: Well, I don't have the [char]Phoenix's[/char] [item]feather[/item].
* [016](#016) 5[not has_item("MERMAIDS_TEAR") and not has_item("GNOMES_WHISKER") and not has_item("PHOENIX_FEATHER")]😢: Unfortunately, I've come empty-handed. Turns out, [char]Mermaids[/char] are rather protective of their [item]tears[/item], [char]Phoenix[/char] don't appreciate plucking, and [char]Gnomes[/char] are surprisingly agile.

### 012

* [ITEMS-GNOMES_WHISKER,MERMAIDS_TEAR,PHOENIX_FEATHER] Well, color me surprised. It seems you've managed to outwit fate itself and gather the trifecta of ridiculousness. Hand them over, then, and let's see if my magic can concoct the miracle you so desperately desire.

* [017](#017) 1😐: Here they are, in all their mischievous glory. I trust your potion-making skills won't disappoint?

### 013

* How very typical. You've never been one for completing tasks, have you?

* [018](#018) 1😢: But the other items are right here, so work your magic, figuratively speaking.

### 014

* Pathetic. [char]Gnomes[/char] are rather agile indeed. Perhaps next time you'll consider the art of negotiation.

* [018](#018) 1😢: But the other items are right here, so work your magic, figuratively speaking.

### 015

* Oh, how utterly unsurprising. A [char]Phoenix[/char] [item]feather[/item] eludes you, you say?

* [018](#018) 1😢: But the other items are right here, so work your magic, figuratively speaking.

### 016

* Oh, my poor, unfortunate soul. I see you're more adept at returning empty-handed than not. I guess you're doomed for good.

* [019](#019-end) 1😐: Who needs a cure anyway, right?

### 017

* Oh, ye of little faith! Hand them over, and let's see if your efforts were in vain or not.

* [020](#020-end) 1😉: Should I hide behind this big chest?
* [020](#020-end) 2😐: Let's see…
* [020](#020-end) 3😇: I can't wait!

### 018

* Oh, how charmingly dramatic! I'll do my best with the incomplete collection you've managed to gather.

* [021](#021-end) 1😢: On the other hand, perhaps I should have collected them all…
* [021](#021-end) 2😐: It must work, it must work, it must work…
* [021](#021-end) 3😉: It was so clever of me not to bother to collect all items…

### 019-end
[011](#011)

* A resigned acceptance of one's fate, how delightfully refreshing. You've certainly mastered the art of embracing the inevitable. Go in peace.

### 020-end
[011](#011)

* [ITEMS+POTION_CURSE_NO_MORE] Let the magic weave its mysteries. Take this [item]potion[/item] and drink it… somewhere else. If all goes well, your curse will be no more. In other cases, I don't want to clean your guts from my alchemy workshop's walls.

### 021-end
[011](#011)

* Here goes nothing, I suppose. I'll see what can be done with what you've provided…

. .. ...

* Psssssssst….

* I'm afraid it's no use. You need to come back with all ingredients.

