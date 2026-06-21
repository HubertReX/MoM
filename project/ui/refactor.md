# Refactor by CC

MoM Session from 2026-06-21

## Co powstało (`project/ui/`)

|Warstwa|Pliki|
|---|---|
|Rdzeń|`widget.py` (cache dirty-flag), `manager.py`, `theme.py` (cache fontów/teł), `layout.py`|
|Tekst|[`text/markup.py`](https://github.com/HubertReX/pygame-ce-web-boilerplate/blob/NinjaAdventure/text/markup.py) (parser tagów z `STYLE_TAGS_DICT` + emoji), [`text/style.py`](https://github.com/HubertReX/pygame-ce-web-boilerplate/blob/NinjaAdventure/text/style.py)|
|Widżety|`widgets/` — `Label`, `Image`, `Button`, `RichText` (zawijanie, scroll, linki, animowane emoji)|
|Ekrany|`panels/` — `main_menu`, `hud`, `dialog`, `modal`, `inventory`, `trade`|
|Kontroler|`game_ui.py` — **`GameUI`** z czystym API|

### Czyste API (to był główny cel — łatwość użycia)

```Python
ui.open(DialogPanel, npc=npc, text=npc.dialogs)

ui.open(TradePanel);
ui.toggle(InventoryPanel)

ui.close(DialogPanel);
ui.is_open(TradePanel)
```

Koniec luźnych boolean-flag — stan żyje wewnątrz paneli (`TradePanel.is_buying`).
