"""
Gurgaon Schools Dataset + Catchment Analysis
--------------------------------------------
Extracts school locations from OpenStreetMap (Overpass API), cleans and
de-duplicates them, calculates distance from a reference point and flags
catchment coverage (1 / 3 / 5 km).

Usage:
    python scrape_schools.py
    python scrape_schools.py --lat 28.4146 --lon 77.0425 --radii 1 2 5
"""
import argparse
import math
import time

import pandas as pd
import requests

# Gurgaon bounding box: south, west, north, east
BBOX = (28.35, 76.85, 28.55, 77.15)

# Reference point: approx. Spaze I-Tech Park, Sohna Road, Sector 49
# (approximate - verify on Google Maps and override with --lat / --lon)
DEFAULT_LAT, DEFAULT_LON = 28.4146, 77.0425

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
HEADERS = {"User-Agent": "gurgaon-schools-scraper/1.0 (student project)"}


def build_query(bbox):
    s, w, n, e = bbox
    return f"""
    [out:json][timeout:90];
    (
      node["amenity"="school"]({s},{w},{n},{e});
      way["amenity"="school"]({s},{w},{n},{e});
      relation["amenity"="school"]({s},{w},{n},{e});
    );
    out center tags;
    """


def fetch_elements(query, retries=3):
    """POST the query to Overpass; retry and fall back to a mirror on failure."""
    last_err = None
    for url in OVERPASS_MIRRORS:
        for attempt in range(1, retries + 1):
            try:
                r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=120)
                r.raise_for_status()
                return r.json()["elements"]
            except (requests.RequestException, ValueError, KeyError) as err:
                last_err = err
                print(f"[warn] {url} attempt {attempt}/{retries} failed: {err}")
                time.sleep(3 * attempt)
    raise RuntimeError(f"All Overpass mirrors failed: {last_err}")


def parse_elements(elements):
    rows = []
    for e in elements:
        t = e.get("tags", {})
        center = e.get("center", {})
        address = ", ".join(
            x for x in (t.get("addr:housenumber"), t.get("addr:street"),
                        t.get("addr:suburb"), t.get("addr:city")) if x
        ) or t.get("addr:full")
        rows.append({
            "osm_id": f'{e.get("type")}/{e.get("id")}',
            "name": t.get("name"),
            "address": address,
            "operator": t.get("operator"),
            "website": t.get("website") or t.get("contact:website"),
            "phone": t.get("phone") or t.get("contact:phone"),
            "lat": e.get("lat", center.get("lat")),
            "lon": e.get("lon", center.get("lon")),
        })
    return pd.DataFrame(rows)


def clean(df):
    """Drop unusable rows, standardise text, remove duplicates. Returns (df, report)."""
    report = {"raw_rows": len(df)}

    df = df.dropna(subset=["lat", "lon"])
    df = df[df["name"].notna() & (df["name"].str.strip() != "")]
    report["after_dropping_missing_name_or_coords"] = len(df)

    df = df.copy()
    df["name"] = df["name"].str.strip().str.replace(r"\s+", " ", regex=True).str.title()
    for col in ("address", "operator", "website", "phone"):
        df[col] = df[col].astype("string").str.strip()

    # Same school mapped twice (e.g. node + building way): match on name + ~11 m grid
    df["_key"] = df["name"].str.lower() + "|" + df["lat"].round(4).astype(str) + "|" + df["lon"].round(4).astype(str)
    df = df.drop_duplicates(subset="_key").drop(columns="_key")
    report["after_deduplication"] = len(df)

    # Sanity check: everything must lie inside the bounding box
    s, w, n, e = BBOX
    df = df[df["lat"].between(s, n) & df["lon"].between(w, e)]
    report["after_bbox_validation"] = len(df)

    return df.reset_index(drop=True), report


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def add_catchment(df, ref_lat, ref_lon, radii):
    df = df.copy()
    df["distance_km"] = [round(haversine_km(ref_lat, ref_lon, la, lo), 2)
                         for la, lo in zip(df["lat"], df["lon"])]
    for km in radii:
        df[f"within_{km}km"] = df["distance_km"] <= km
    return df.sort_values("distance_km").reset_index(drop=True)


def make_chart(df, radii, path="catchment_chart.png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    counts = [int(df[f"within_{km}km"].sum()) for km in radii]
    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar([f"{km} km" for km in radii], counts, color="#2a6f97")
    ax.bar_label(bars)
    ax.set_title("Schools within catchment radius of reference point")
    ax.set_ylabel("Number of schools")
    ax.set_xlabel("Radius")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lat", type=float, default=DEFAULT_LAT)
    ap.add_argument("--lon", type=float, default=DEFAULT_LON)
    ap.add_argument("--radii", type=float, nargs="+", default=[1, 3, 5])
    ap.add_argument("--out", default="gurgaon_schools.csv")
    args = ap.parse_args()
    radii = [int(r) if float(r).is_integer() else r for r in args.radii]

    print("Fetching schools from OpenStreetMap...")
    raw = parse_elements(fetch_elements(build_query(BBOX)))
    df, report = clean(raw)
    df = add_catchment(df, args.lat, args.lon, radii)

    df.to_csv(args.out, index=False)
    make_chart(df, radii)

    print("\n--- Data quality report ---")
    for k, v in report.items():
        print(f"{k}: {v}")
    print(f"schools with website: {int(df['website'].notna().sum())}")
    print("\n--- Catchment coverage ---")
    for km in radii:
        print(f"within {km} km: {int(df[f'within_{km}km'].sum())}")
    print(f"\nSaved {args.out} and catchment_chart.png")


if __name__ == "__main__":
    main()
