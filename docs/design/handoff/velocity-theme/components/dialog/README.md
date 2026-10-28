# Dialog

Part of the Velocity Theme app components (26 Oct 2026). Tokens are in tokens-app.css; the card is in card.css.

- Overlay rgba(0,0,0,0.6). Panel on --card-fill (linear-gradient(135deg, #2C2C2C 0%, #262626 45%, #212121 100%)) with --card-shadow (4px 6px 14px rgba(0,0,0,0.45)), 2px #434343 border, radius 6px, padding 24px, 600px to 820px wide.
- Title 20px 600, one lead line in #BEBEBE, then groups with caps labels. Footer ruled off: Reset to defaults on the left, Cancel and Save on the right.
- role dialog with aria-modal; focus moves in on open, Tab stays inside, Escape or Cancel closes and focus returns to the trigger.
