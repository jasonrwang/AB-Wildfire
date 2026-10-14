"""Altair chart builders shared by Visualizations.ipynb and the GitHub Pages build.

Each builder takes already-loaded DataFrames and returns a chart, so the notebook and
`dashboard/build.py` render exactly the same specs.
"""
from pathlib import Path

import altair as alt
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'
DATA_FILES = {
    'AB': DATA_DIR / 'ABWildfires.csv',
    'BC': DATA_DIR / 'BCWildfires.csv',
    'CA': DATA_DIR / 'CAWildfires.csv',
}


def load_data():
    """Read the three compiled CSVs produced by the AB/BC/CA notebooks."""
    return {region: pd.read_csv(path) for region, path in DATA_FILES.items()}


def yearly_totals(df):
    """Sum per-fire (AB) or already-yearly (BC) records into one row per year."""
    return df.groupby('Year', as_index=False)['Area'].sum().sort_values('Year')


def ab_chart(df_ab_yearly):
    df_ab_yearly = df_ab_yearly.copy()
    df_ab_yearly['avg_5yr'] = df_ab_yearly['Area'].rolling(window=5).mean()

    brush = alt.selection_interval(encodings=['x'])
    ab_last_year = int(df_ab_yearly['Year'].max())
    ab_first_year = int(df_ab_yearly['Year'].min())

    bars = alt.Chart(df_ab_yearly).mark_bar().encode(
        x=alt.X('Year:O', title='Year', scale=alt.Scale(domain=brush)),
        y=alt.Y('Area:Q', title='Area Burned (ha)', axis=alt.Axis(format=',.0f')),
        color=alt.condition(alt.datum.Year == ab_last_year, alt.value('#fc1920'), alt.value('#0e3692')),
        tooltip=['Year:O', alt.Tooltip('Area:Q', title='Area (ha)', format=',.0f')]
    )

    avg_line = alt.Chart(df_ab_yearly).mark_line(color='#f5a623', strokeWidth=2).encode(
        x=alt.X('Year:O', scale=alt.Scale(domain=brush)),
        y='avg_5yr:Q'
    )

    detail = (bars + avg_line).properties(
        width=700, height=320,
        title=f'Albertan Forest Area Burned by Wildfire, {ab_first_year}–{ab_last_year}'
    )

    overview = alt.Chart(df_ab_yearly).mark_bar(color='#0e3692').encode(
        x=alt.X('Year:O', title=None, axis=alt.Axis(labels=False, ticks=False)),
        y=alt.Y('Area:Q', title=None, axis=None)
    ).properties(width=700, height=60).add_params(brush)

    return detail & overview


def ab_bc_chart(df_ab_yearly, df_bc_yearly):
    combined = pd.concat([
        df_ab_yearly.assign(Province='AB')[['Year', 'Area', 'Province']],
        df_bc_yearly.assign(Province='BC')[['Year', 'Area', 'Province']],
    ])

    legend_select_ab_bc = alt.selection_point(fields=['Province'], bind='legend')

    return alt.Chart(combined).mark_bar().encode(
        x=alt.X('Year:O', title='Year'),
        y=alt.Y('Area:Q', title='Area Burned (ha)', stack='zero', axis=alt.Axis(format=',.0f')),
        color=alt.Color('Province:N', scale=alt.Scale(domain=['AB', 'BC'], range=['#0e3692', '#ffcd00'])),
        opacity=alt.condition(legend_select_ab_bc, alt.value(1), alt.value(0.15)),
        tooltip=['Province:N', 'Year:O', alt.Tooltip('Area:Q', title='Area (ha)', format=',.0f')]
    ).add_params(legend_select_ab_bc).properties(
        width=700, height=350,
        title='Alberta vs. British Columbia: Forest Area Burned by Wildfire'
    )


def ca_chart(df_ca):
    metric_param = alt.param(
        name='metric',
        value='Area',
        bind=alt.binding_radio(
            options=['Area', 'Area_Norm'],
            labels=['Raw area burned (ha)', 'Normalized (share of province area)'],
            name='Metric:  '
        )
    )

    legend_select_ca = alt.selection_point(fields=['Province'], bind='legend')

    return alt.Chart(df_ca).transform_calculate(
        metric_value='datum[metric]'
    ).mark_bar().encode(
        x=alt.X('Year:O', title='Year'),
        y=alt.Y('metric_value:Q', title='Area Burned', stack='zero'),
        color=alt.Color('Province:N', scale=alt.Scale(scheme='tableau20'), title='Province'),
        opacity=alt.condition(legend_select_ca, alt.value(1), alt.value(0.08)),
        tooltip=['Province:N', 'Year:O', alt.Tooltip('metric_value:Q', title='Value', format=',.4f')]
    ).add_params(metric_param, legend_select_ca).properties(
        width=700, height=400,
        title=f'Canadian Wildfire Area Burned by Province, {int(df_ca["Year"].min())}–{int(df_ca["Year"].max())}'
    )


def decade_chart(df_ab_yearly):
    df_decade = df_ab_yearly.copy()
    df_decade['Decade'] = (df_decade['Year'] // 10) * 10
    decade_stats = (
        df_decade.groupby('Decade', as_index=False)['Area']
        .agg(Total='sum', Mean='mean', Max='max')
    )
    decade_long = decade_stats.melt(id_vars='Decade', var_name='Statistic', value_name='Area')

    return alt.Chart(decade_long).mark_bar().encode(
        x=alt.X('Decade:O', title='Decade'),
        y=alt.Y('Area:Q', title='Area Burned (ha)', axis=alt.Axis(format=',.0f')),
        color=alt.Color('Statistic:N', scale=alt.Scale(scheme='set2')),
        column=alt.Column('Statistic:N', title=None),
        tooltip=['Decade:O', 'Statistic:N', alt.Tooltip('Area:Q', format=',.0f')]
    ).properties(width=180, height=300, title='Alberta: Area Burned by Decade')
