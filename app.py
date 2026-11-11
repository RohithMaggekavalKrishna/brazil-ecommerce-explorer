"""
app.py - Olist e-commerce dashboard (Mini-Project 2, Week 7 prototype)

Three coordinated views, linked by cross-filtering:
  View 1  Monthly revenue by category   (line)    - brush a month range
  View 2  Delivery time vs. review score (bubble) - select category/state points
  View 3  Revenue by customer state      (choropleth map) - select states

Each view is filtered by the selections made in the OTHER two views and
highlights its own selection. "Reset selection" clears everything.

Run:  python app.py   then open http://127.0.0.1:8050
Data: data/olist_clean.csv, produced by prep_data.py from the Olist Kaggle data.

Sources / citations
  - Olist Brazilian E-Commerce Public Dataset (Kaggle, olistbr/brazilian-ecommerce)
  - Dash cross-filtering pattern: https://dash.plotly.com/interactive-graphing
  - Color palette: validated 6-hue categorical set (reference palette) + neutral grey
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, ctx, dcc, html

# --------------------------------------------------------------------------- data
DATA_FILE = Path(__file__).parent / "data" / "olist_clean.csv"
GEO_FILE = Path(__file__).parent / "data" / "brazil_states.geojson"
MIN_ORDERS_PER_POINT = 5          # hide category/state points with fewer orders (noisy means)

df = pd.read_csv(DATA_FILE)
df["pair"] = df["category_group"] + "|" + df["customer_state"]   # key used for View 2 selection

MONTHS = sorted(df["order_month"].unique())
# Category order: by total revenue, "other" always last so it never steals a hue.
_rev = df.groupby("category_group")["price"].sum().sort_values(ascending=False)
CATEGORIES = [c for c in _rev.index if c != "other"] + ["other"]

# Fixed category -> colour map (colour follows the entity, never its rank in a filtered view).
HUES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#6250d6"]
COLORS = {c: HUES[i] for i, c in enumerate(CATEGORIES[:-1])}
COLORS["other"] = "#8a8985"        # neutral grey = "everything else"

MAX_ORDERS = df.groupby(["category_group", "customer_state"])["order_id"].nunique().max()
FONT = dict(family="Inter, Arial, sans-serif", size=12, color="#0b0b0b")
GRID = "#e4e3df"
DIM = 0.28                          # opacity of unselected marks

# Brazil state outlines (simplified) for the map. Feature id = two-letter state code.
# Source: giuliano-macedo/geodata-br-states (IBGE boundaries), simplified with shapely.
with open(GEO_FILE) as fh:
    GEOJSON = json.load(fh)
STATE_NAMES = {f["id"]: f["properties"]["name"] for f in GEOJSON["features"]}


def _label_position(feature):
    """Centre of a state's bounding box, used to place its two-letter label."""
    pts, stack = [], [feature["geometry"]["coordinates"]]
    while stack:
        item = stack.pop()
        if isinstance(item[0], (int, float)):
            pts.append(item)
        else:
            stack.extend(item)
    lons, lats = [p[0] for p in pts], [p[1] for p in pts]
    return (min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2


LABEL_POS = {f["id"]: _label_position(f) for f in GEOJSON["features"]}
# Sequential single-hue ramp, light -> dark (lightness decreases monotonically = greyscale safe).
REVENUE_RAMP = ["#e8f0fb", "#b4cdf0", "#6fa3e3", "#2a78d6", "#14407a"]

EMPTY_SEL = {"months": [], "pairs": [], "states": []}


# ------------------------------------------------------------------- filtering helpers
def apply_filters(data, months=None, pairs=None, states=None):
    """Filter the item-level table by whichever selections are active."""
    if months:
        data = data[data["order_month"].isin(months)]
    if pairs:
        data = data[data["pair"].isin(pairs)]
    if states:
        data = data[data["customer_state"].isin(states)]
    return data


def base_layout(**kw):
    """Shared figure styling: light, thin gridlines, no chart junk (data-ink ratio)."""
    layout = dict(
        font=FONT, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=56, r=16, t=8, b=44), dragmode="select", clickmode="event+select",
        hoverlabel=dict(bgcolor="#ffffff", font=dict(family=FONT["family"], size=12, color="#0b0b0b")),
        legend=dict(orientation="h", y=-0.22, x=0, font=dict(size=11)),
        uirevision="keep",          # keep zoom/brush state when figures are re-rendered
    )
    layout.update(kw)
    return layout


def style_axes(fig, xtitle=None, ytitle=None):
    fig.update_xaxes(title=xtitle, showgrid=False, linecolor="#b9b8b2", ticks="outside", tickcolor="#b9b8b2")
    fig.update_yaxes(title=ytitle, gridcolor=GRID, zeroline=False)


# --------------------------------------------------------------------------- figures
def figure_trend(sel):
    """View 1: revenue per month, one line per category (Y position = revenue, X = month)."""
    d = apply_filters(df, pairs=sel["pairs"], states=sel["states"])
    g = (d.groupby(["order_month", "category_group"])["price"].sum()
         .unstack().reindex(index=MONTHS, columns=CATEGORIES).fillna(0))
    picked = [i for i, m in enumerate(MONTHS) if m in sel["months"]]
    fig = go.Figure()
    for cat in CATEGORIES:
        fig.add_trace(go.Scatter(
            x=MONTHS, y=g[cat], name=cat, mode="lines+markers",
            line=dict(color=COLORS[cat], width=2), marker=dict(color=COLORS[cat], size=7),
            selectedpoints=picked or None,
            selected=dict(marker=dict(opacity=1, size=10)),
            unselected=dict(marker=dict(opacity=DIM if picked else 1)),
            hovertemplate="<b>%{fullData.name}</b><br>%{x}<br>Revenue: R$ %{y:,.0f}<extra></extra>",
        ))
    fig.update_layout(base_layout(selectdirection="h"))
    style_axes(fig, ytitle="Revenue (R$)")
    fig.update_yaxes(tickformat="~s")
    return fig


def figure_scatter(sel):
    """View 2: one bubble per category x state. X = avg delivery days, Y = avg review,
    size = order count, hue = category."""
    d = apply_filters(df, months=sel["months"], states=sel["states"])
    g = (d.groupby(["category_group", "customer_state"])
         .agg(days=("delivery_days", "mean"), score=("review_score", "mean"),
              orders=("order_id", "nunique"), revenue=("price", "sum"))
         .reset_index())
    g = g[g["orders"] >= MIN_ORDERS_PER_POINT]
    fig = go.Figure()
    for cat in CATEGORIES:
        s = g[g["category_group"] == cat].reset_index(drop=True)
        picked = [i for i, st in enumerate(s["customer_state"]) if f"{cat}|{st}" in sel["pairs"]]
        fig.add_trace(go.Scatter(
            x=s["days"], y=s["score"], name=cat, mode="markers",
            customdata=s[["category_group", "customer_state", "orders", "revenue"]].to_numpy(),
            marker=dict(color=COLORS[cat], opacity=0.8, line=dict(color="#fcfcfb", width=1.5),
                        size=s["orders"], sizemode="area",
                        sizeref=2.0 * MAX_ORDERS / (34 ** 2), sizemin=4),
            selectedpoints=picked if sel["pairs"] else None,
            selected=dict(marker=dict(opacity=1)),
            unselected=dict(marker=dict(opacity=DIM)),
            showlegend=False,
            hovertemplate=("<b>%{customdata[0]}</b> in <b>%{customdata[1]}</b><br>"
                           "Avg delivery: %{x:.1f} days<br>Avg review: %{y:.2f} / 5<br>"
                           "Orders: %{customdata[2]:,}<br>Revenue: R$ %{customdata[3]:,.0f}<extra></extra>"),
        ))
    fig.update_layout(base_layout(margin=dict(l=56, r=16, t=8, b=44)))
    style_axes(fig, xtitle="Average delivery time (days)", ytitle="Average review score (1-5)")
    fig.update_xaxes(showgrid=True, gridcolor=GRID)
    return fig


def figure_states(sel):
    """View 3: choropleth map of revenue by customer state.
    Colour (sequential single hue, log scale) = revenue; position = geography."""
    d = apply_filters(df, months=sel["months"], pairs=sel["pairs"])
    g = (d.groupby("customer_state")
         .agg(revenue=("price", "sum"), orders=("order_id", "nunique")).reset_index())
    g = g[g["revenue"] > 0].reset_index(drop=True)
    picked = [i for i, s in enumerate(g["customer_state"]) if s in sel["states"]]
    fig = go.Figure()
    # Grey base layer so states with no data in the current filter still show their outline.
    fig.add_trace(go.Choroplethmap(
        geojson=GEOJSON, locations=list(STATE_NAMES), z=[0] * len(STATE_NAMES),
        colorscale=[[0, "#ecebe7"], [1, "#ecebe7"]], showscale=False,
        marker=dict(line=dict(color="#fcfcfb", width=0.8)), hoverinfo="skip"))
    if len(g):
        z = np.log10(g["revenue"])                      # log scale: SP is ~100x the smallest states
        lo, hi = float(z.min()), float(z.max())
        if hi - lo < 0.3:                               # avoid a degenerate colour range
            lo, hi = hi - 0.3, hi
        ticks = [t for t in range(2, 8) if lo <= t <= hi]
        fig.add_trace(go.Choroplethmap(
            geojson=GEOJSON, locations=g["customer_state"], z=z,
            zmin=lo, zmax=hi, colorscale=[[i / 4, c] for i, c in enumerate(REVENUE_RAMP)],
            text=[STATE_NAMES[s] for s in g["customer_state"]],
            customdata=g[["revenue", "orders"]].to_numpy(),
            marker=dict(line=dict(color="#fcfcfb", width=0.8)),
            selectedpoints=picked if sel["states"] else None,
            selected=dict(marker=dict(opacity=1)),
            unselected=dict(marker=dict(opacity=DIM)),
            colorbar=dict(orientation="h", thickness=10, len=0.6, x=0.5, y=-0.02, yanchor="top",
                          title=dict(text="Revenue (R$, log scale)", side="top", font=dict(size=11)),
                          tickvals=ticks, ticktext=[f"{10 ** t:,.0f}" for t in ticks],
                          tickfont=dict(size=10), outlinewidth=0),
            hovertemplate=("<b>%{text}</b> (%{location})<br>Revenue: R$ %{customdata[0]:,.0f}"
                           "<br>Orders: %{customdata[1]:,}<extra></extra>"),
        ))
    # Direct labels: two-letter state codes (text only, never selectable). White text on dark
    # fills and dark text on light fills keeps every label readable.
    dark_fill = set()
    if len(g):
        norm = (z - lo) / (hi - lo)
        dark_fill = set(g["customer_state"][norm >= 0.55])
        if sel["states"]:                       # unselected states are dimmed, so they need dark text
            dark_fill &= set(sel["states"])
    for on_dark, color in ((False, "#0b0b0b"), (True, "#ffffff")):
        codes = [s for s in STATE_NAMES if (s in dark_fill) == on_dark]
        fig.add_trace(go.Scattermap(
            lon=[LABEL_POS[s][0] for s in codes], lat=[LABEL_POS[s][1] for s in codes],
            text=codes, mode="text", textfont=dict(size=11, color=color),
            hoverinfo="skip", showlegend=False, selectedpoints=[]))
    fig.update_layout(base_layout(margin=dict(l=0, r=0, t=0, b=0)))
    # "white-bg" = no background tiles, so the map needs no internet access to render.
    fig.update_layout(map=dict(style="white-bg", center=dict(lon=-53.5, lat=-14.5), zoom=2.8))
    return fig


# ---------------------------------------------------------------------------- layout
def panel(title, subtitle, graph_id, cls):
    """A bordered card (Gestalt enclosure) holding one view."""
    return html.Section(className=f"panel {cls}", children=[
        html.H2(title), html.P(subtitle, className="sub"),
        dcc.Graph(id=graph_id, config={"displaylogo": False, "responsive": True,
                                       "modeBarButtonsToRemove": ["autoScale2d", "lasso2d"]},
                  style={"height": "100%"}),
    ])


app = Dash(__name__, title="Olist E-Commerce Dashboard")
server = app.server

app.layout = html.Main(className="page", children=[
    html.Header(className="top", children=[
        html.Div([html.H1("Olist e-commerce: sales, delivery and satisfaction"),
                  html.P("Brazil, Jan 2017 to Aug 2018 - delivered orders only", className="sub")]),
        html.Div(className="controls", children=[            # proximity: status + reset together
            html.Span(id="status", className="status"),
            html.Button("Reset selection", id="reset", n_clicks=0, className="btn"),
        ]),
    ]),
    html.Div(className="legend-row", id="legend"),
    panel("1. Monthly revenue by category",
          "Drag horizontally to brush a month range. The other views filter to it.",
          "v1", "hero"),
    html.Div(className="row", children=[
        panel("2. Delivery time vs. review score",
              "One bubble per category and state (5+ orders). Size = orders. Drag to select.",
              "v2", "half"),
        panel("3. Revenue by customer state",
              "Darker = more revenue (log scale). Click a state, shift-click for several, or drag a box.",
              "v3", "half"),
    ]),
    dcc.Store(id="sel", data=EMPTY_SEL),
])


# ------------------------------------------------------------------------- callbacks
def _points(event, key):
    """Extract the unique values of `key` from a Plotly selectedData event."""
    if not event or not event.get("points"):
        return []
    if key == "pair":
        return sorted({f'{p["customdata"][0]}|{p["customdata"][1]}' for p in event["points"]})
    if key == "x":
        # Plotly auto-detects "2017-11" as a date and reports "2017-11-01"; trim back to YYYY-MM.
        return sorted({str(p["x"])[:7] for p in event["points"]})
    return sorted({p[key] for p in event["points"]})


@app.callback(
    Output("sel", "data"),
    Input("v1", "selectedData"), Input("v2", "selectedData"), Input("v3", "selectedData"),
    Input("reset", "n_clicks"), State("sel", "data"),
    prevent_initial_call=True,
)
def update_selection(s1, s2, s3, _reset, current):
    """Record which view the user just brushed; reset clears all three."""
    who = ctx.triggered_id
    if who == "reset":
        return EMPTY_SEL
    sel = dict(current)
    if who == "v1":
        sel["months"] = _points(s1, "x")
    elif who == "v2":
        sel["pairs"] = _points(s2, "pair")
    elif who == "v3":
        sel["states"] = _points(s3, "location")
    return sel


@app.callback(
    Output("v1", "figure"), Output("v2", "figure"), Output("v3", "figure"),
    Output("status", "children"), Output("legend", "children"),
    Input("sel", "data"),
)
def render(sel):
    """Redraw all views from the shared selection state."""
    n = [len(sel["months"]), len(sel["pairs"]), len(sel["states"])]
    status = ("No selection - drag on a chart to filter the others" if not any(n) else
              f"Selected: {n[0]} months, {n[1]} category-state points, {n[2]} states")
    legend = [html.Span(className="key", children=[
        html.Span(className="swatch", style={"background": COLORS[c]}), c]) for c in CATEGORIES]
    return figure_trend(sel), figure_scatter(sel), figure_states(sel), status, legend


if __name__ == "__main__":
    app.run(debug=False, port=8050)
