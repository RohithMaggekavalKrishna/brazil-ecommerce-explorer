# Olist E-Commerce Dashboard (Mini-Project 2, Final)

Interactive dashboard built with **Plotly Dash** on the Olist Brazilian E-Commerce dataset
(Kaggle, `olistbr/brazilian-ecommerce`). Author: Rohith Maggekaval Krishna.

## Run it (about 1 minute)

Requires Python 3.9+.

```bash
cd olist_dashboard
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:8050 in a browser. The cleaned data (`data/olist_clean.csv`) and map outlines are
included, so nothing needs to be downloaded. The map uses no background tiles, so it works offline.

## How to use it

| Action | Result |
| --- | --- |
| Click a **category chip** (top row) | Shows only that category in all three views; click several to compare, click again to remove |
| Drag horizontally on **View 1** | Brushes a month range; Views 2 and 3 filter to those months |
| **Linear / Log** toggle on View 1 | Switches the revenue axis; log keeps small categories readable next to "other" |
| **Delivery time / Item price** toggle on View 2 | Changes the scatter x axis, so the same bubbles answer "does delivery time or price relate to reviews?" |
| Drag a box on **View 2** or click a bubble | Selects category/state bubbles; Views 1 and 3 filter to them |
| Click a state on the **View 3** map | Toggles that state on or off (click again to unselect); click several for a multi-state view, or drag a box |
| Hover any mark | Tooltip with details |
| Summary line and ranked list | One-line totals and the top 5 states by revenue share for whatever is currently selected |
| **Reset selection** | Clears all selections, including category chips |

Each view is filtered by the selections made in the *other two* views and highlights its own.

## Views and encodings

| View | Question | Encodings |
| --- | --- | --- |
| 1. Monthly revenue by category | How do sales trend, and which categories drive them? | Revenue = y-position, month = x-position, category = colour hue |
| 2. Delivery time vs. review score | Do slower deliveries get lower reviews? | Avg delivery days = x, avg review = y, order count = size, category = hue |
| 3. Revenue by customer state (map) | Where does revenue come from? | Revenue = colour lightness (sequential single hue, log scale), state = geographic position |

Change from the proposal: View 2 plots one aggregated bubble per category and state
(5+ orders) instead of one point per order, because 109,000 raw points would be unreadable.

## Rebuilding the data (optional)

Download the dataset from Kaggle, put the CSVs in `data/raw/`, then run:

```bash
python prep_data.py data/raw
```

Cleaning steps are listed at the top of `prep_data.py`: delivered orders only, one review per
order (latest), English category names, top 6 categories plus "other", and Jan 2017 to Aug 2018.

## Changes after peer feedback

| Feedback | Change |
| --- | --- |
| Category row looked clickable but was not; the line legend was clickable but did not look it | The chips are now real buttons that filter every view; the built-in legend is removed |
| Could not filter categories in the scatter plot | Chips filter all views, including the scatter |
| "other" skews the line chart | Linear / Log toggle on View 1 |
| What is "other"? | Note under the chips: categories outside the top 6 by revenue plus products with no category |
| Could not select several states independently | Click toggles a state on or off; Reset clears all |
| Clicking a scatter point showed a flat zero line for an unrelated category | Categories with no data under the current filters are no longer drawn |
| Needs insight headlines | Each panel has a one-line takeaway computed from the currently filtered data (peak month and revenue; reviews for orders delivered within 7 days vs after 21 days; top 3 states' revenue share, or the selected states' share) |
| Hues hard to tell apart | Each category also has its own marker symbol (circle, square, diamond, triangle, cross, x; hollow circle for "other"), shown in the line chart, the scatter and the chips |
| Month brush not obvious | Selected months are shaded on View 1 with a "Selected: Jan 2018 to Mar 2018" label; with nothing selected, a "Drag across months to filter" hint is shown |

Further additions: direct end-labels on the line chart; an item-price option on the scatter (price vs satisfaction); a summary line of orders, revenue, average review and delivery time; a ranked top-5 state list under the map to offset the map's area bias; explicit axis ranges so the Linear/Log toggle never leaves a stale axis.

## Known gaps (planned for the final)

- Palette is colourblind-checked pair by pair, but 7 hues in the bubble view are hard to
  tell apart for some viewers; direct labels and a greyscale test are planned.
- Map area is not proportional to revenue (large northern states look bigger than small, busy ones like SP/RJ); the state labels and tooltips compensate, and a ranked list could be added.
- "other" is the largest category group; a finer grouping may be better.
- Usability testing, annotated screenshots and the reflection come in the final submission.

## Credits

Dataset: Olist (Kaggle). Brazil state outlines: github.com/giuliano-macedo/geodata-br-states (IBGE boundaries), simplified with shapely; confirm its licence before the final. Pattern: Dash cross-filtering docs (dash.plotly.com/interactive-graphing).
