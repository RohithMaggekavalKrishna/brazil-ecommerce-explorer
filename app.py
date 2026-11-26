"""
app.py - Olist e-commerce dashboard (Mini-Project 2, final)

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
from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update

# --------------------------------------------------------------------------- data
DATA_FILE = Path(__file__).parent / "data" / "olist_clean.csv"
GEO_FILE = Path(__file__).parent / "data" / "brazil_states.geojson"
XHOVER = {"days": "Avg delivery: %{x:.1f} days", "price": "Avg item price: R$ %{x:,.0f}"}
XTITLE = {"days": "Average delivery time (days)", "price": "Average item price (R$)"}
LINE_PLOT_PX = 190                # approx. plot height of View 1, used to space end-labels
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

EMPTY_SEL = {"months": [], "pairs": [], "states": [], "cats": []}


# ------------------------------------------------------------------- filtering helpers
def apply_filters(data, months=None, pairs=None, states=None, cats=None):
    """Filter the item-level table by whichever selections are active."""
    if cats:
        data = data[data["category_group"].isin(cats)]
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
        transition=dict(duration=300, easing="cubic-in-out"),   # animated updates when filters change
    )
    layout.update(kw)
    return layout


def style_axes(fig, xtitle=None, ytitle=None):
    fig.update_xaxes(title=xtitle, showgrid=False, linecolor="#b9b8b2", ticks="outside", tickcolor="#b9b8b2")
    fig.update_yaxes(title=ytitle, gridcolor=GRID, zeroline=False)


# --------------------------------------------------------------------------- figures
def figure_trend(sel, log_scale=False):
    """View 1: revenue per month, one line per category (Y position = revenue, X = month).
    log_scale=True switches the y axis to log so small categories are not flattened by "other"."""
    d = apply_filters(df, pairs=sel["pairs"], states=sel["states"], cats=sel["cats"])
    g = (d.groupby(["order_month", "category_group"])["price"].sum()
         .unstack().reindex(index=MONTHS, columns=CATEGORIES).fillna(0))
    picked = [i for i, m in enumerate(MONTHS) if m in sel["months"]]
    fig = go.Figure()
    for cat in CATEGORIES:
        if g[cat].sum() == 0:
            continue    # no revenue under the current filters: draw nothing, not a flat zero line
        y = g[cat].replace(0, np.nan) if log_scale else g[cat]   # log axis cannot show 0
        fig.add_trace(go.Scatter(
            x=MONTHS, y=y, name=cat, mode="lines+markers",
            line=dict(color=COLORS[cat], width=2), marker=dict(color=COLORS[cat], size=7),
            selectedpoints=picked or None,
            selected=dict(marker=dict(opacity=1, size=10)),
            unselected=dict(marker=dict(opacity=DIM if picked else 1)),
            hovertemplate="<b>%{fullData.name}</b><br>%{x}<br>Revenue: R$ %{y:,.0f}<extra></extra>",
        ))
    # Explicit axis ranges: stops the end-labels from stretching the x axis, and keeps the y axis
    # correct when the Linear/Log toggle changes its type during an animated update.
    allv = g[[c for c in CATEGORIES if g[c].sum() > 0]].to_numpy().ravel() if g.to_numpy().any() else np.array([1.0])
    if log_scale:
        yrange = [float(np.log10(allv[allv > 0].min())) - 0.1, float(np.log10(allv.max())) + 0.1]
    else:
        yrange = [-0.04 * float(allv.max()), 1.08 * float(allv.max())]
    # Direct end-labels (no legend lookup needed). Labels are nudged apart so they never overlap.
    ends = [(c, g[c].iloc[-1]) for c in CATEGORIES if g[c].sum() > 0 and g[c].iloc[-1] > 0]
    if ends:
        tf = np.log10 if log_scale else (lambda v: v)
        vals = [tf(v) for _, v in ends]
        px = [(v - yrange[0]) / (yrange[1] - yrange[0]) * LINE_PLOT_PX for v in vals]   # approx. pixel height
        order = sorted(range(len(ends)), key=lambda i: px[i])
        placed = {}
        for rank, i in enumerate(order):                                # enforce >= 15 px spacing
            placed[i] = max(px[i], placed[order[rank - 1]] + 15) if rank else px[i]
        moved = [placed[i] - px[i] for i in placed if placed[i] - px[i] > 0.5]
        recentre = sum(moved) / len(moved) / 2 if moved else 0.0      # spread labels both ways, not only up
        placed = {i: placed[i] - recentre for i in placed}
        for i, (c, v) in enumerate(ends):
            fig.add_annotation(x=MONTHS[-1], y=float(np.log10(v)) if log_scale else float(v),
                               xref="x", yref="y", text=c.replace("_", " "), showarrow=False,
                               xanchor="left", xshift=12, yshift=placed[i] - px[i],
                               font=dict(size=11, color="#0b0b0b"))
    # The chips above the charts are the legend (and the category filter), so no built-in legend.
    fig.update_layout(base_layout(selectdirection="h", showlegend=False, margin=dict(l=56, r=150, t=8, b=44),
                                  uirevision="log" if log_scale else "linear"))
    style_axes(fig, ytitle="Revenue (R$, log scale)" if log_scale else "Revenue (R$)")
    fig.update_yaxes(tickformat="~s", type="log" if log_scale else "linear", range=yrange, autorange=False)
    fig.update_xaxes(range=["2016-12-15", "2018-09-15"])
    return fig


def figure_scatter(sel, xmode="days"):
    """View 2: one bubble per category x state. X = avg delivery days, Y = avg review,
    size = order count, hue = category."""
    d = apply_filters(df, months=sel["months"], states=sel["states"], cats=sel["cats"])
    g = (d.groupby(["category_group", "customer_state"])
         .agg(days=("delivery_days", "mean"), price=("price", "mean"), score=("review_score", "mean"),
              orders=("order_id", "nunique"), revenue=("price", "sum"))
         .reset_index())
    g = g[g["orders"] >= MIN_ORDERS_PER_POINT]
    fig = go.Figure()
    for cat in CATEGORIES:
        s = g[g["category_group"] == cat].reset_index(drop=True)
        picked = [i for i, st in enumerate(s["customer_state"]) if f"{cat}|{st}" in sel["pairs"]]
        fig.add_trace(go.Scatter(
            x=s[xmode], y=s["score"], name=cat, mode="markers",
            customdata=s[["category_group", "customer_state", "orders", "revenue"]].to_numpy(),
            marker=dict(color=COLORS[cat], opacity=0.8, line=dict(color="#fcfcfb", width=1.5),
                        size=s["orders"], sizemode="area",
                        sizeref=2.0 * MAX_ORDERS / (34 ** 2), sizemin=4),
            selectedpoints=picked if sel["pairs"] else None,
            selected=dict(marker=dict(opacity=1)),
            unselected=dict(marker=dict(opacity=DIM)),
            showlegend=False,
            hovertemplate=("<b>%{customdata[0]}</b> in <b>%{customdata[1]}</b><br>"
                           + XHOVER[xmode] + "<br>Avg review: %{y:.2f} / 5<br>"
                           "Orders: %{customdata[2]:,}<br>Revenue: R$ %{customdata[3]:,.0f}<extra></extra>"),
        ))
    fig.update_layout(base_layout(margin=dict(l=56, r=16, t=8, b=44)))
    style_axes(fig, xtitle=XTITLE[xmode], ytitle="Average review score (1-5)")
    fig.update_xaxes(showgrid=True, gridcolor=GRID)
    return fig


def figure_states(sel):
    """View 3: choropleth map of revenue by customer state.
    Colour (sequential single hue, log scale) = revenue; position = geography."""
    d = apply_filters(df, months=sel["months"], pairs=sel["pairs"], cats=sel["cats"])
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
    fig.update_layout(base_layout(margin=dict(l=0, r=0, t=0, b=0), clickmode="event"))  # click = toggle (callback)
    # "white-bg" = no background tiles, so the map needs no internet access to render.
    fig.update_layout(map=dict(style="white-bg", center=dict(lon=-53.5, lat=-14.5), zoom=2.8))
    return fig


# ---------------------------------------------------------------------------- layout
def panel(title, subtitle, graph_id, cls, extra=None, bottom=None):
    """A bordered card (Gestalt enclosure) holding one view. `extra` = optional header control."""
    return html.Section(className=f"panel {cls}", children=[
        html.Div(className="panel-head", children=[html.H2(title)] + ([extra] if extra is not None else [])),
        html.P(subtitle, className="sub"),
        dcc.Graph(id=graph_id, config={"displaylogo": False, "responsive": True,
                                       "modeBarButtonsToRemove": ["autoScale2d", "lasso2d"]},
                  className="graph", style={"height": "100%"}),
    ] + ([bottom] if bottom is not None else []))


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
    # Category chips: legend (colour key) AND filter. Click to show only that category in all views.
    html.Div(className="legend-row", children=[
        html.Button([html.Span(className="swatch", style={"background": COLORS[c]}), c],
                    id={"type": "chip", "cat": c}, n_clicks=0, className="chip",
                    title=f"Show only {c} (click again to remove)")
        for c in CATEGORIES]),
    html.P("Click a category to filter all three views (click several to compare). "
           "\"other\" = every product category outside the top 6 by revenue, plus products with no category.",
           className="sub note"),
    html.Div(id="summary", className="summary"),
    panel("1. Monthly revenue by category",
          "Drag horizontally to brush a month range. The other views filter to it.",
          "v1", "hero",
          extra=dcc.RadioItems(id="yscale", options=[{"label": "Linear", "value": "linear"},
                                                     {"label": "Log", "value": "log"}],
                               value="linear", inline=True, className="toggle")),
    html.Div(className="row", children=[
        panel("2. What drives review scores?",
              "One bubble per category and state (5+ orders). Size = orders. Drag to select.",
              "v2", "half",
              extra=dcc.RadioItems(id="xmode", options=[{"label": "Delivery time", "value": "days"},
                                                        {"label": "Item price", "value": "price"}],
                                   value="days", inline=True, className="toggle")),
        panel("3. Revenue by customer state",
              "Darker = more revenue (log scale). Click a state to select it, click again to unselect; drag a box for several.",
              "v3", "half", bottom=html.Div(id="rank", className="rank")),
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
    Output("sel", "data"), Output("v3", "clickData"),
    Input("v1", "selectedData"), Input("v2", "selectedData"), Input("v3", "selectedData"),
    Input("v3", "clickData"), Input({"type": "chip", "cat": ALL}, "n_clicks"),
    Input("reset", "n_clicks"), State("sel", "data"),
    prevent_initial_call=True,
)
def update_selection(s1, s2, s3, click3, _chips, _reset, current):
    """Record what the user just did; reset clears everything."""
    prop = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
    if prop == "reset.n_clicks":
        return EMPTY_SEL, None
    sel = dict(current)
    if prop == "v1.selectedData":
        sel["months"] = _points(s1, "x")
    elif prop == "v2.selectedData":
        sel["pairs"] = _points(s2, "pair")
    elif prop == "v3.selectedData":
        sel["states"] = _points(s3, "location")
    elif prop == "v3.clickData":
        # A click toggles one state on/off. clickData is then cleared so that clicking the
        # same state again still fires the callback.
        if not click3 or not click3.get("points"):
            return no_update, no_update
        code = click3["points"][0]["location"]
        sel["states"] = ([s for s in sel["states"] if s != code] if code in sel["states"]
                         else sel["states"] + [code])
        return sel, None
    elif prop.startswith("{"):                      # a category chip: toggle that category
        cat = ctx.triggered_id["cat"]
        sel["cats"] = ([c for c in sel["cats"] if c != cat] if cat in sel["cats"]
                       else sel["cats"] + [cat])
    return sel, no_update


def summarize(sel):
    """One-line facts for whatever is currently shown (all active filters applied)."""
    d = apply_filters(df, sel["months"], sel["pairs"], sel["states"], sel["cats"])
    if d.empty:
        return "No orders match the current selection."
    orders = d.drop_duplicates("order_id")
    return (f"Showing {orders['order_id'].nunique():,} orders  |  R$ {d['price'].sum():,.0f} revenue  |  "
            f"avg review {orders['review_score'].mean():.2f} / 5  |  "
            f"avg delivery {orders['delivery_days'].mean():.1f} days")


def ranked_states(sel, n=5):
    """Ranked list of the top states by revenue under the current filters (fixes map area bias)."""
    d = apply_filters(df, sel["months"], sel["pairs"], None, sel["cats"])
    rev = d.groupby("customer_state")["price"].sum().sort_values(ascending=False)
    if rev.empty:
        return ""
    total = rev.sum()
    items = [html.Span(className="rank-item" + (" on" if s in sel["states"] else ""),
                       children=f"{i}. {s} {v / total:.0%}")
             for i, (s, v) in enumerate(rev.head(n).items(), 1)]
    return [html.Span("Top states by revenue share:", className="rank-label")] + items


@app.callback(
    Output("v1", "figure"), Output("v2", "figure"), Output("v3", "figure"),
    Output("status", "children"), Output({"type": "chip", "cat": ALL}, "className"),
    Output("summary", "children"), Output("rank", "children"),
    Input("sel", "data"), Input("yscale", "value"), Input("xmode", "value"),
)
def render(sel, yscale, xmode):
    """Redraw all views from the shared selection state."""
    n = [len(sel["months"]), len(sel["pairs"]), len(sel["states"]), len(sel["cats"])]
    status = ("No selection - click or drag on a chart to filter the others" if not any(n) else
              f"Selected: {n[3]} categories, {n[0]} months, {n[1]} category-state points, {n[2]} states")
    chips = ["chip" + (" on" if c in sel["cats"] else " off" if sel["cats"] else "") for c in CATEGORIES]
    return (figure_trend(sel, yscale == "log"), figure_scatter(sel, xmode), figure_states(sel),
            status, chips, summarize(sel), ranked_states(sel))


if __name__ == "__main__":
    app.run(debug=False, port=8050)
