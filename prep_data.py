"""
prep_data.py - Build the cleaned, joined Olist dataset used by the dashboard.

Input : the raw Olist CSVs (https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
        placed in data/raw/
Output: data/olist_clean.csv  (one row per order item)

Usage : python prep_data.py [path/to/raw_dir]

Cleaning decisions (each is also printed when the script runs):
  1. Keep only DELIVERED orders that have a delivery date, because delivery
     time is one of the encoded variables.
  2. 547 orders have more than one review -> keep the most recent review.
  3. Category names are translated to English; products with no category
     become "unknown"; two categories missing from the translation file keep
     their Portuguese name.
  4. Only the top N categories by revenue keep their name; everything else is
     "other", so the colour legend stays at 7 items or fewer.
  5. Months outside 2017-01..2018-08 are dropped: 2016 and late 2018 hold only
     a handful of orders and would distort the monthly trend.
"""
import sys
from pathlib import Path

import pandas as pd

RAW_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw")
OUT_FILE = Path("data/olist_clean.csv")

TOP_N_CATEGORIES = 6                      # + "other" = 7 legend items
FIRST_MONTH, LAST_MONTH = "2017-01", "2018-08"


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(RAW_DIR / name)


def main() -> None:
    orders = read("olist_orders_dataset.csv")
    items = read("olist_order_items_dataset.csv")
    products = read("olist_products_dataset.csv")
    customers = read("olist_customers_dataset.csv")
    reviews = read("olist_order_reviews_dataset.csv")
    translation = read("product_category_name_translation.csv")

    # 1. delivered orders with a delivery date; compute delivery time in days
    n0 = len(orders)
    orders = orders[orders["order_status"] == "delivered"].dropna(
        subset=["order_delivered_customer_date"]
    ).copy()
    print(f"[1] orders: {n0:,} -> {len(orders):,} (delivered, with delivery date)")
    purchased = pd.to_datetime(orders["order_purchase_timestamp"])
    delivered = pd.to_datetime(orders["order_delivered_customer_date"])
    orders["order_month"] = purchased.dt.strftime("%Y-%m")
    orders["delivery_days"] = (delivered - purchased).dt.total_seconds() / 86400

    # 2. one review per order (latest answer timestamp wins)
    reviews = (
        reviews.sort_values("review_answer_timestamp")
        .drop_duplicates("order_id", keep="last")[["order_id", "review_score"]]
    )
    print(f"[2] reviews reduced to one per order: {len(reviews):,}")

    # 3. English category names
    products = products.merge(translation, on="product_category_name", how="left")
    products["category"] = (
        products["product_category_name_english"]
        .fillna(products["product_category_name"])
        .fillna("unknown")
    )

    # join everything at order-item grain
    df = (
        items[["order_id", "product_id", "price", "freight_value"]]
        .merge(orders[["order_id", "customer_id", "order_month", "delivery_days"]], on="order_id")
        .merge(products[["product_id", "category"]], on="product_id", how="left")
        .merge(customers[["customer_id", "customer_state"]], on="customer_id", how="left")
        .merge(reviews, on="order_id", how="left")
    )
    df["category"] = df["category"].fillna("unknown")
    missing_reviews = df["review_score"].isna().sum()
    df = df.dropna(subset=["review_score"])
    df["review_score"] = df["review_score"].astype(int)
    print(f"[2] item rows dropped for missing review: {missing_reviews:,}")

    # 4. top-N categories by revenue, rest -> "other" ("unknown" counts as other)
    top = (
        df[df["category"] != "unknown"].groupby("category")["price"].sum()
        .nlargest(TOP_N_CATEGORIES).index
    )
    df["category_group"] = df["category"].where(df["category"].isin(top), "other")
    print(f"[4] top {TOP_N_CATEGORIES} categories: {list(top)}")

    # 5. complete months only
    before = len(df)
    df = df[(df["order_month"] >= FIRST_MONTH) & (df["order_month"] <= LAST_MONTH)]
    print(f"[5] item rows: {before:,} -> {len(df):,} (months {FIRST_MONTH}..{LAST_MONTH})")

    df = df[
        ["order_id", "order_month", "category_group", "customer_state",
         "price", "freight_value", "delivery_days", "review_score"]
    ].round({"delivery_days": 2})
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_FILE, index=False)

    print(f"\nWrote {OUT_FILE}: {len(df):,} rows, {df['order_id'].nunique():,} orders")
    print("Missing values per column:", df.isna().sum().to_dict())
    print(df.describe(include="all").T[["count", "unique", "min", "max"]].to_string())


if __name__ == "__main__":
    main()
