# Table

Part of the Velocity Theme app components (26 Oct 2026). Tokens are in tokens-app.css; the card is in card.css.

- Grid rows with role table, row, columnheader and cell. Header: min 36px, 1px rule above, 2px below, Chakra Petch 12px 600 #BEBEBE; the sorted column is ink with an accent arrow and aria-sort.
- Each header has a 20px menu button (chevron; filter icon and accent line while a filter is set).
- Rows: 1px #333333 rule, cells padded 12px 10px, text wraps; a date breaks before its time, never inside it.
- Expanded panels (reasons, notes) open under the row on #1A1A1A with a 24px close button. Hidden columns give their width to the rest.
- Empty state: an 8px square, a 16px to 20px title, one line saying why, and a way out (Clear filters).
