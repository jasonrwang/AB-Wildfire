"""Build the static GitHub Pages dashboard into _site/.

Run from the repo root (after the AB/BC/CA notebooks have refreshed data/*.csv):

    uv run python -m dashboard.build
"""
import json
import shutil
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import altair as alt

from dashboard import charts

SITE_DIR = Path(__file__).resolve().parent.parent / '_site'
REPO_URL = 'https://github.com/jasonrwang/AB-Wildfire'

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Canadian Wildfire Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/vega@{vega}"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-lite@{vegalite}"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-embed@{vegaembed}"></script>
<style>
  body {{ font-family: system-ui, -apple-system, sans-serif; max-width: 960px; margin: 0 auto;
         padding: 16px; color: #1f2328; background: #fff; line-height: 1.5; }}
  header p, footer p {{ color: #57606a; }}
  section {{ margin: 40px 0; }}
  .chart {{ overflow-x: auto; }}
  .download {{ font-size: 0.9em; }}
  a {{ color: #0969da; }}
</style>
</head>
<body>
<header>
  <h1>Alberta, British Columbia &amp; Canada Wildfire Area Burned</h1>
  <p>Compiled from Alberta, BC, and Natural Resources Canada government data.
     The current season is year-to-date, not final.
     Data as of {data_as_of}; rebuilt {built} UTC.
     Source and methodology: <a href="{repo}">{repo}</a>.</p>
</header>
{sections}
<footer>
  <p>Data sources:
    <a href="https://open.alberta.ca/opendata/wildfire-data">Alberta Wildfire</a>,
    <a href="https://catalogue.data.gov.bc.ca/dataset/bc-wildfire-fire-perimeters-historical">BC Wildfire Service</a>,
    <a href="https://cwfis.cfs.nrcan.gc.ca/datamart">CWFIS National Fire Database</a>.
  </p>
</footer>
<script>
{embeds}
</script>
</body>
</html>
"""

SECTION = """<section>
  <h2>{title}</h2>
  <p>{blurb}</p>
  <div class="chart" id="{div_id}"></div>
  {download}
</section>"""


def _download_link(region, description):
    name = charts.DATA_FILES[region].name
    return (f'<p class="download"><a href="data/{name}" download>Download CSV</a> '
            f'({escape(description)})</p>')


def build():
    data = charts.load_data()
    ab_yearly = charts.yearly_totals(data['AB'])
    bc_yearly = charts.yearly_totals(data['BC'])

    panels = [
        ('ab', 'Alberta, 1918–present', charts.ab_chart(ab_yearly),
         'Drag across the small chart below to zoom into a range of years. '
         'The orange line is the trailing 5-year average; the latest year is in red.',
         _download_link('AB', 'individual fire records, Year and Area in hectares')),
        ('ab-bc', 'Alberta vs. British Columbia', charts.ab_bc_chart(ab_yearly, bc_yearly),
         'Click a province in the legend to isolate it.',
         _download_link('BC', 'BC yearly totals in hectares')),
        ('ca', 'Canada-wide by province', charts.ca_chart(data['CA']),
         'Fires of 200 ha or more only. Use the radio buttons to switch between raw area '
         'and share of provincial land area; click the legend to isolate a province.',
         _download_link('CA', 'yearly area and normalized area by province')),
        ('decade', 'Alberta by decade', charts.decade_chart(ab_yearly),
         'Total, mean, and maximum single-year area burned per decade.',
         ''),
    ]

    sections, embeds = [], []
    for div_id, title, chart, blurb, download in panels:
        sections.append(SECTION.format(title=escape(title), blurb=escape(blurb),
                                       div_id=div_id, download=download))
        # Keep '</script>' sequences in string values from closing the script tag.
        spec = json.dumps(chart.to_dict()).replace('</', '<\\/')
        embeds.append(f'vegaEmbed("#{div_id}", {spec}, {{"actions": false}});')

    latest = {region: int(df['Year'].max()) for region, df in data.items()}
    data_as_of = ', '.join(f'{region} {year}' for region, year in latest.items())

    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    (SITE_DIR / 'data').mkdir(parents=True)
    for path in charts.DATA_FILES.values():
        shutil.copy2(path, SITE_DIR / 'data' / path.name)

    html = PAGE.format(
        vega=alt.VEGA_VERSION, vegalite=alt.VEGALITE_VERSION, vegaembed=alt.VEGAEMBED_VERSION,
        data_as_of=data_as_of,
        built=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M'),
        repo=REPO_URL,
        sections='\n'.join(sections),
        embeds='\n'.join(embeds),
    )
    (SITE_DIR / 'index.html').write_text(html, encoding='utf-8')
    print(f'Wrote {SITE_DIR / "index.html"} ({data_as_of})')


if __name__ == '__main__':
    build()
