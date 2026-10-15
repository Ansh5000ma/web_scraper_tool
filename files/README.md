# Gurgaon Schools Dataset + Catchment Analysis

A Python workflow that automatically collects school locations in Gurgaon from
OpenStreetMap, cleans and validates the data, and calculates distance and
catchment coverage from any reference point. Built as a sample of the kind of
location-study data automation used in market research.

## What it does
1. **Extract** - queries the OpenStreetMap Overpass API for all `amenity=school`
   nodes, ways and relations inside a Gurgaon bounding box (with retries and a mirror fallback).
2. **Clean** - drops rows with no name or coordinates, normalises whitespace and
   casing, removes duplicates (same name within ~11 m, e.g. a school mapped as both
   a point and a building).
3. **Validate** - checks every record lies inside the bounding box and prints a
   data-quality report (rows at each stage, how many have websites).
4. **Geocode / distance** - computes haversine distance (km) from a reference point.
5. **Catchment** - flags schools within 1, 3 and 5 km (configurable) and saves a bar chart.

## Run it
```bash
pip install -r requirements.txt
python scrape_schools.py
# custom reference point and radii:
python scrape_schools.py --lat 28.4595 --lon 77.0266 --radii 2 4 6
```
Outputs: `gurgaon_schools.csv` and `catchment_chart.png`.

## Output columns
`osm_id, name, address, operator, website, phone, lat, lon, distance_km, within_1km, within_3km, within_5km`

## Data source and ethics
OpenStreetMap data (c) OpenStreetMap contributors, ODbL licence. I used the open
Overpass API instead of scraping Google Maps, which its terms of service do not allow.

## Limitations
- OSM coverage is crowd-sourced, so some schools may be missing or have incomplete
  addresses/websites. For a client study, cross-check against government (UDISE+) or
  school-website data.
- Distance is straight-line (haversine), not road distance or drive time.
- The default reference point is approximate; set your own with `--lat` / `--lon`.

## Possible extensions
- Add road-distance / drive-time catchments using a routing API (OSRM)
- Enrich records by scraping school websites for fees and board affiliation
- Dashboard in Power BI / Google Looker Studio

## Data checks done before sharing
Duplicate and blank-name checks are automated in the script; I also spot-checked
sample coordinates against Google Maps after running.
