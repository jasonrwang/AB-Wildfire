"""Update data/CA/NBACByProvince.csv from NRCan's National Burned Area Composite (NBAC).

NBAC is satellite-mapped burned area, published as one polygon per fire. It has no
province column (only national parks are tagged), so each fire is split across
provinces by its overlap with Statistics Canada's 2021 province boundaries.
CA-Wildfire.ipynb uses the result to fill gaps in the National Fire Database and to
supply years the Fire Database doesn't cover yet.

NBAC adds the previous fire season each spring. To add it (or recompute any years):

    uv run --group nbac python tools/update_nbac.py 2026

Each year downloads ~100-350 MB of polygons, processed one year at a time. Rows for the
given years are replaced; other years are kept.
"""
import argparse
import json
import tempfile
from pathlib import Path

import pandas as pd
import requests
from shapely.geometry import shape
from shapely.strtree import STRtree
from shapely.validation import make_valid as _make_valid

OUT = Path(__file__).resolve().parent.parent / 'data' / 'CA' / 'NBACByProvince.csv'
NBAC_WFS = 'https://geoserver.cwfif.nrcan.gc.ca/geoserver/ows'
PROVINCES = ('https://geo.statcan.gc.ca/geo_wa/rest/services/2021/'
             'Digital_boundary_files/MapServer/0/query')
ABBR = {'Newfoundland and Labrador': 'NL', 'Prince Edward Island': 'PE', 'Nova Scotia': 'NS',
        'New Brunswick': 'NB', 'Quebec': 'QC', 'Ontario': 'ON', 'Manitoba': 'MB',
        'Saskatchewan': 'SK', 'Alberta': 'AB', 'British Columbia': 'BC', 'Yukon': 'YT',
        'Northwest Territories': 'NWT', 'Nunavut': 'NU'}
MIN_HA = 200  # same cutoff as the National Fire Database's large-fires data


def make_valid(geom):
    try:
        return _make_valid(geom)
    except Exception:  # a few NBAC polygons trip GEOS's repair; buffer(0) handles them
        return geom.buffer(0)


def fetch_json(url, params, path):
    # requests (certifi) rather than urllib: Python's default trust store doesn't have the
    # root StatCan's certificate chains to. Streamed to disk since a year can be ~350 MB.
    with requests.get(url, params=params, stream=True, timeout=600) as resp:
        resp.raise_for_status()
        with open(path, 'wb') as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
    with open(path) as fh:
        return json.load(fh)


def load_provinces(tmp):
    data = fetch_json(PROVINCES, {'where': '1=1', 'outFields': 'PRENAME', 'outSR': 4326,
                                  'maxAllowableOffset': 0.002, 'f': 'geojson'},
                      tmp / 'provinces.geojson')
    return [(ABBR[f['properties']['PRENAME']], make_valid(shape(f['geometry'])))
            for f in data['features']]


def year_totals(year, provinces, tree, tmp):
    path = tmp / f'nbac{year}.geojson'
    feats = fetch_json(NBAC_WFS, {
        'service': 'WFS', 'version': '2.0.0', 'request': 'GetFeature',
        'typeName': 'public:nbac', 'outputFormat': 'json', 'srsName': 'EPSG:4326',
        'CQL_FILTER': f'year = {year}', 'count': 10000,
        'propertyName': 'year,adj_ha,prescribed,geometry'}, path)['features']
    path.unlink()
    if len(feats) >= 10000:
        raise RuntimeError(f'{year}: hit the 10,000-feature page limit; add paging')
    area, fires = {}, {}
    for f in feats:
        p = f['properties']
        ha = p.get('adj_ha') or 0
        if p.get('prescribed') in (True, 'true', 'True') or ha < MIN_HA:
            continue
        geom = make_valid(shape(f['geometry']))
        parts = [(provinces[i][0], geom.intersection(provinces[i][1]).area)
                 for i in tree.query(geom)]
        parts = [(prov, a) for prov, a in parts if a > 0]
        total = sum(a for _, a in parts)
        for prov, a in parts:
            area[prov] = area.get(prov, 0) + ha * a / total
            fires[prov] = fires.get(prov, 0) + 1
    return pd.DataFrame({'Province': list(area), 'Year': year,
                         'Area': [round(v, 2) for v in area.values()],
                         'Fires': [fires[p] for p in area]})


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('years', nargs='+', type=int)
    years = parser.parse_args().years
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        provinces = load_provinces(tmp)
        tree = STRtree([g for _, g in provinces])
        new = []
        for year in years:
            df = year_totals(year, provinces, tree, tmp)
            print(f'{year}: {df.Area.sum():,.0f} ha across {len(df)} provinces/territories', flush=True)
            new.append(df)
    old = pd.read_csv(OUT) if OUT.exists() else pd.DataFrame()
    if len(old):
        old = old[~old['Year'].isin(years)]
    out = pd.concat([old, *new], ignore_index=True).sort_values(['Year', 'Province'], kind='stable')
    out.to_csv(OUT, index=False)
    print(f'Wrote {OUT} ({out.Year.min()}-{out.Year.max()})')


if __name__ == '__main__':
    main()
