# Olist E-Commerce Dashboard (Mini-Project 2, Week 7 prototype)

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
| Drag horizontally on **View 1** | Brushes a month range; Views 2 and 3 filter to those months |
| Drag a box on **View 2** | Selects category/state bubbles; Views 1 and 3 filter to them |
| Click a state (shift-click for several) or drag a box on the **View 3** map | Selects states; Views 1 and 2 filter to them |
| Hover any mark | Tooltip with details |
| **Reset selection** | Clears all selections |

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

## Known gaps (planned for the final)

- Palette is colourblind-checked pair by pair, but 7 hues in the bubble view are hard to
  tell apart for some viewers; direct labels and a greyscale test are planned.
- Map area is not proportional to revenue (large northern states look bigger than small, busy ones like SP/RJ); the state labels and tooltips compensate, and a ranked list could be added.
- "other" is the largest category group; a finer grouping may be better.
- Usability testing, annotated screenshots and the reflection come in the final submission.

## Credits

Dataset: Olist (Kaggle). Brazil state outlines: github.com/giuliano-macedo/geodata-br-states (IBGE boundaries), simplified with shapely; confirm its licence before the final. Pattern: Dash cross-filtering docs (dash.plotly.com/interactive-graphing).
