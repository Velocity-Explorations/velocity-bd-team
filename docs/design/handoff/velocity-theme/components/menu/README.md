# Menu

Part of the Velocity Theme app components (26 Oct 2026). Tokens are in tokens-app.css; the card is in card.css.

- Surface on --card-fill (linear-gradient(135deg, #2C2C2C 0%, #262626 45%, #212121 100%)) with --card-shadow (4px 6px 14px rgba(0,0,0,0.45)), 2px #434343 border, radius 6px, padding 6px; opens 4px below its trigger and never covers it.
- Title row 13px 600 with a text button to clear; sections split by 1px #333333 with caps labels.
- Items 28px: menuitemradio with a 6px ink mark, menuitemcheckbox with a 16px box; the chosen item 600 weight on #333333.
- One menu open at a time; a click outside or Escape closes it and focus returns to the trigger. Focus moves into the menu on open; arrow keys move between items.
- Column header menus hold the column’s sort, its filters and keyword search, Hide column and a link to Table settings.
