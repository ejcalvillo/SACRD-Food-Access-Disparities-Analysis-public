from multiprocessing.dummy import Process
import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
import plotly.express as px
from streamlit_folium import st_folium
import base64
import datetime
import sys
import os
import plotly.graph_objects as go

# Add the SACRD root directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Cleaning_Processing.GetGapScore import gap_scores_with_time, avg_gap_scores
from Cleaning_Processing.CleaningPrograms import cleaned_programs

# --- Page Config ---
st.set_page_config(layout="wide")

# --- Header ---
with open("../Dashboard_Final/logo.png", "rb") as _logo_file:
    _logo_b64 = base64.b64encode(_logo_file.read()).decode()

st.markdown(
    f"""
    <div style="display:flex; align-items:center; gap:12px;">
        <img src="data:image/png;base64,{_logo_b64}" width="70">
        <h1 style="margin:0;">SACRD Food Access Dashboard - (Synthetic Data)</h1>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- Load Program Data ---
@st.cache_data
def load_data():

    df = cleaned_programs.copy()
    df["zipcode"] = df["zipcode"].astype(str)

    # optional clean‑up if some rows already look like “78207.0”
    df["zipcode"] = (
        df["zipcode"]
        .str.replace(r"\.0$", "", regex=True)  # strip any .0 suffix
        .str.zfill(5)                          # pad to 5 digits if needed
        .str.strip()
    )

    gdf = gpd.read_file("../Dashboard_Final/simplified.geojson")
    return df, gdf

program_df, zip_geo = load_data()

# --- Gap Score Data ---
gap_df = gap_scores_with_time.copy()
gap_df["month"] = pd.to_datetime(gap_df["month"])

# Remove NaNs
gap_df = gap_df[gap_df["zipcode"].notna()]

# Convert ZIP to int, then string
gap_df["zipcode"] = gap_df["zipcode"].astype(float).astype(int).astype(str)


min_month = gap_df["month"].min().to_pydatetime()
max_month = gap_df["month"].max().to_pydatetime()

unique_gap_zips = sorted(gap_df["zipcode"].dropna().unique())
default_selection = ["78207"] if "78207" in unique_gap_zips else unique_gap_zips[:1]


def select_ranked_zips(df, metric_col, key_prefix, default_n=5):
    """ZIP-code picker: highest/lowest by `metric_col`, or a manual pick."""
    mode = st.segmented_control(
        "Which ZIP codes?",
        ["Highest need", "Lowest need", "Choose my own"],
        default="Highest need",
        key=f"{key_prefix}_mode",
    ) or "Highest need"

    if mode == "Choose my own":
        return st.multiselect(
            "Select ZIP codes:",
            options=unique_gap_zips,
            default=default_selection,
            key=f"{key_prefix}_manual",
        )

    n = st.slider("How many ZIP codes?", 3, 15, default_n, key=f"{key_prefix}_n")
    ranked = df.groupby("zipcode")[metric_col].mean().sort_values(ascending=False)
    return (ranked.head(n) if mode == "Highest need" else ranked.tail(n)).index.tolist()


def select_time_grouping(key_prefix):
    """Monthly/Quarterly toggle, replacing the old dropdown."""
    return st.segmented_control(
        "Time grouping:",
        ["Monthly", "Quarterly"],
        default="Monthly",
        key=f"{key_prefix}_period_mode",
    ) or "Monthly"


def select_month_range(key_prefix):
    """Two-calendar date range picker, replacing the old slider."""
    default_start = max(min_month, max_month - datetime.timedelta(days=180))
    picked = st.date_input(
        "Date range:",
        value=(default_start, max_month),
        min_value=min_month,
        max_value=max_month,
        key=f"{key_prefix}_date_range",
    )
    if isinstance(picked, (tuple, list)) and len(picked) == 2:
        return pd.Timestamp(picked[0]), pd.Timestamp(picked[1])
    # User has only picked one endpoint so far; fall back to the default range.
    return pd.Timestamp(default_start), pd.Timestamp(max_month)


# --- Layout Rows ---
row1_col1, row1_col2 = st.columns(2)
row2_col1, row2_col2 = st.columns(2)

# --- Plot 1: Scatter Map (Plotly) ---
with row1_col1:
    st.subheader("Food Program Locations")
    st.caption("Where food-related programs are located, based on the address they list.")

    zip_options = sorted(program_df["zipcode"].dropna().unique())
    selected_zips = st.multiselect(
        "Filter by ZIP Code:",
        options=zip_options,
        default=[],
        key="program_zip_filter"
    )

    filtered_df = program_df.copy()
    if selected_zips:
        filtered_df = filtered_df[filtered_df["zipcode"].isin(selected_zips)]

    def plot_scatter_program_map(df):
        map_df = df[["lat", "lng", "name", "service_address"]].copy()
        map_df["lat"] = pd.to_numeric(map_df["lat"], errors="coerce")
        map_df["lon"] = pd.to_numeric(map_df["lng"], errors="coerce")
        map_df = map_df.dropna(subset=["lat", "lon"])
        map_df = map_df[(map_df["lat"] != 0) & (map_df["lon"] != 0)]

        if map_df.empty:
            st.info("No valid coordinates available for plotting.")
            return

        fig = px.scatter_map(
            map_df,
            lat="lat",
            lon="lon",
            hover_name="name",
            hover_data={"service_address": True, "lat": False, "lon": False},
            zoom=9,
            height=500,
            color_discrete_sequence=["red"]
        )
        fig.update_layout(map_style="open-street-map", margin={"r": 0, "t": 0, "l": 0, "b": 0})
        st.plotly_chart(fig, use_container_width=True)

    plot_scatter_program_map(filtered_df)

# --- Plot 2: Choropleth Map ---
with row1_col2:
    st.subheader("Need & Resources by ZIP Code")
    st.caption("Compare Gap Score, program count, demand, or population across ZIP codes.")


    # ZIP-level metrics from filtered data
    zip_counts = program_df["zipcode"].value_counts().reset_index()

    zip_counts.columns = ["ZIP", "program_count"]

    gap_metrics = avg_gap_scores.copy()
    gap_metrics_latest = gap_metrics.drop_duplicates("zipcode", keep="last")
    gap_metrics_latest = gap_metrics_latest[["zipcode", "gap_score", "raw_demand", "population"]]
    gap_metrics_latest["zipcode"] = gap_metrics_latest["zipcode"].astype(str)

    combined_metrics = zip_geo.copy()
    combined_metrics = combined_metrics.merge(zip_counts, on="ZIP", how="left")
    combined_metrics = combined_metrics.merge(gap_metrics_latest, left_on="ZIP", right_on="zipcode", how="left")
    combined_metrics["program_count"] = combined_metrics["program_count"].fillna(0)
    combined_metrics = combined_metrics.fillna(0)

    metric = st.selectbox(
        "Select metric to display:",
        options=["gap_score", "program_count", "raw_demand", "population"]
    )
    metric_pretty = {
        "gap_score": "Gap Score",
        "program_count": "Program Count",
        "raw_demand": "Raw Demand",
        "population": "Population"
    }[metric]

    m = folium.Map(location=[29.4241, -98.4936], zoom_start=9)

    folium.Choropleth(
        geo_data=combined_metrics,
        data=combined_metrics,
        columns=["ZIP", metric],
        key_on="feature.properties.ZIP",
        fill_color="YlOrRd",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name=f"{metric_pretty} by ZIP Code",
        nan_fill_color="white"
    ).add_to(m)

    folium.GeoJson(
        combined_metrics,
        style_function=lambda feature: {'fillOpacity': 0, 'color': 'black', 'weight': 1.2},
        tooltip=folium.GeoJsonTooltip(
            fields=["ZIP", metric],
            aliases=["ZIP Code:", metric_pretty]
        )
    ).add_to(m)

    st_folium(m, height=500, use_container_width=True)

# --- Plot 3: Gap Score Trends (Line Chart) ---
with row2_col1:
    st.subheader("Gap Score Trends by ZIP Code")
    st.caption("Gap Score highlights ZIP codes where the need for food help outpaces nearby programs.")

    ranked_zips = select_ranked_zips(gap_df, "gap_score", key_prefix="gap")
    show_avg_gap = select_time_grouping(key_prefix="gap")

    if show_avg_gap == "Quarterly":
        available_quarters = gap_df["month"].dt.to_period("Q").astype(str).unique()
        selected_quarters = st.multiselect(
            "Select Quarters:",
            options=sorted(available_quarters),
            default=sorted(available_quarters),
            key="quarter_gap_selector"
        )
    else:
        start_month, end_month = select_month_range(key_prefix="gap")

    def plot_gap_scores(df):
        if show_avg_gap == "Quarterly":
            df["quarter"] = df["month"].dt.to_period("Q").astype(str)
            df_filtered = df[
                (df["zipcode"].isin(ranked_zips)) &
                (df["quarter"].isin(selected_quarters))
            ].copy()

            if df_filtered.empty:
                st.warning("No data available for the selected ZIP codes and quarters.")
                return

            all_quarter_df = df[df["quarter"].isin(selected_quarters)].copy()

            avg_score = round(all_quarter_df["gap_score"].mean(), 2)
            max_score = round(all_quarter_df["gap_score"].max(), 2)
            min_score = round(all_quarter_df["gap_score"].min(), 2)

            st.markdown("### Summary Metrics over 1000 population")
            col1, col2, col3 = st.columns(3)
            col1.metric("Average Gap Score", avg_score)
            col2.metric("Max Gap Score", max_score)
            col3.metric("Min Gap Score", min_score)

            grouped = df_filtered.groupby(["zipcode", "quarter"], as_index=False)["gap_score"].mean()
            avg_city = all_quarter_df.groupby("quarter", as_index=False)["gap_score"].mean()
            avg_city["zipcode"] = "Citywide Average"

            combined = pd.concat([grouped, avg_city], ignore_index=True)

            # Order ZIPs for display
            combined["zipcode"] = pd.Categorical(combined["zipcode"], categories=ranked_zips + ["Citywide Average"], ordered=True)
            combined = combined.sort_values(["zipcode", "quarter"])

            fig = px.line(
                combined,
                x="quarter",
                y="gap_score",
                color="zipcode",
                markers=True,
                title="Quarterly Gap Score by ZIP Code with Citywide Average"
            )
            fig.update_traces(
                selector=lambda t: t.name == "Citywide Average",
                line=dict(width=4, color="black")
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
            return

        # Monthly average view
        df_filtered = df[
            (df["zipcode"].isin(ranked_zips)) &
            (df["month"] >= start_month) &
            (df["month"] <= end_month)
        ].copy()

        if df_filtered.empty:
            st.warning("No data available for the selected ZIP codes and date range.")
            return

        date_filtered_all = df[
            (df["month"] >= start_month) &
            (df["month"] <= end_month)
        ]

        avg_score = round(date_filtered_all["gap_score"].mean(), 2)
        max_score = round(date_filtered_all["gap_score"].max(), 2)
        min_score = round(date_filtered_all["gap_score"].min(), 2)

        st.markdown("### Summary Metrics over 1000 population")
        col1, col2, col3 = st.columns(3)
        col1.metric("Average Gap Score", avg_score)
        col2.metric("Max Gap Score", max_score)
        col3.metric("Min Gap Score", min_score)

        df_combined = df_filtered.copy()

        if show_avg_gap == "Monthly":
            avg_df = date_filtered_all.groupby("month", as_index=False)["gap_score"].mean()
            avg_df["zipcode"] = "Average (All Zipcodes)"
            df_combined = pd.concat([df_combined, avg_df], ignore_index=True)

        df_combined["zipcode"] = pd.Categorical(df_combined["zipcode"], categories=ranked_zips + ["Average (All Zipcodes)"], ordered=True)
        df_combined = df_combined.sort_values(["zipcode", "month"])

        fig = px.line(
            df_combined,
            x="month",
            y="gap_score",
            color="zipcode",
            markers=True,
            title="Gap Score Over Time by Zipcode",
            labels={"month": "Month", "gap_score": "Gap Score"}
        )
        for trace in fig.data:
            if trace.name == "Average (All Zipcodes)":
                trace.line.color = "black"
                trace.line.width = 4
                trace.line.dash = "solid"
        fig.update_layout(xaxis_tickformat="%Y-%m", xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    plot_gap_scores(gap_df)


# --- Plot 4: Demand Score Trends ---
with row2_col2:
    st.subheader("Demand Trends by ZIP Code")
    st.caption("Demand Score reflects how much need there is for food help, adjusted for population.")

    selected_zips_4 = select_ranked_zips(gap_df, "demand_score", key_prefix="demand")
    show_avg_demand = select_time_grouping(key_prefix="demand")

    if show_avg_demand == "Quarterly":
        available_quarters = gap_df["month"].dt.to_period("Q").astype(str).unique()
        selected_quarters_demand = st.multiselect(
            "Select Quarters:",
            options=sorted(available_quarters),
            default=sorted(available_quarters),
            key="quarter_demand_selector"
        )
    else:
        date_range_4 = select_month_range(key_prefix="demand")

    def display_demand_score_trend(df):
        if not selected_zips_4:
            st.warning("Please select at least one Zipcode.")
            return

        if show_avg_demand == "Quarterly":
            df["quarter"] = df["month"].dt.to_period("Q").astype(str)
            df_filtered = df[
                (df["quarter"].isin(selected_quarters_demand)) &
                (df["zipcode"].isin(selected_zips_4))
            ].copy()

            if df_filtered.empty:
                st.warning("No data available for the selected ZIP codes and quarters.")
                return

            all_quarters = df["month"].dt.to_period("Q").astype(str)
            df["quarter"] = all_quarters

            all_quarter_df = df[df["quarter"].isin(selected_quarters_demand)].copy()

            avg_score = round(all_quarter_df["demand_score"].mean(), 2)
            max_score = round(all_quarter_df["demand_score"].max(), 2)
            min_score = round(all_quarter_df["demand_score"].min(), 2)

            st.markdown("### Summary Metrics over 1000 population")
            col1, col2, col3 = st.columns(3)
            col1.metric("Average Demand Score", avg_score)
            col2.metric("Max Demand Score", max_score)
            col3.metric("Min Demand Score", min_score)

            grouped = df_filtered.groupby(["zipcode", "quarter"], as_index=False)["demand_score"].mean()
            avg_all = df[df["quarter"].isin(selected_quarters_demand)].copy()
            avg_city = avg_all.groupby("quarter", as_index=False)["demand_score"].mean()
            avg_city["zipcode"] = "Citywide Average"
            combined = pd.concat([grouped, avg_city], ignore_index=True)

            fig = px.line(
                combined,
                x="quarter",
                y="demand_score",
                color="zipcode",
                markers=True,
                title="Quarterly Demand Score by ZIP Code with Citywide Average"
            )
            fig.update_traces(
                selector=lambda t: t.name == "Citywide Average",
                line=dict(width=4, color="black")
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
            return

        # Monthly or Yearly
        df_filtered = df[
            (df["zipcode"].isin(selected_zips_4)) &
            (df["month"] >= date_range_4[0]) &
            (df["month"] <= date_range_4[1])
        ].copy()

        if df_filtered.empty:
            st.warning("No data available for the selected criteria.")
            return

        date_filtered_all = df[
            (df["month"] >= date_range_4[0]) & (df["month"] <= date_range_4[1])
        ]

        avg_score = round(date_filtered_all["demand_score"].mean(), 2)
        max_score = round(date_filtered_all["demand_score"].max(), 2)
        min_score = round(date_filtered_all["demand_score"].min(), 2)

        st.markdown("### Summary Metrics over 1000 population")
        col1, col2, col3 = st.columns(3)
        col1.metric("Average Demand Score", avg_score)
        col2.metric("Max Demand Score", max_score)
        col3.metric("Min Demand Score", min_score)

        df_combined = df_filtered.copy()

        if show_avg_demand == "Monthly":
            avg_df = df[
                (df["month"] >= date_range_4[0]) & (df["month"] <= date_range_4[1])
            ].groupby("month", as_index=False)["demand_score"].mean()
            avg_df["zipcode"] = "Average (All Zipcodes)"
            df_combined = pd.concat([df_combined, avg_df], ignore_index=True)

        fig = px.line(
            df_combined.sort_values(["zipcode", "month"]),
            x="month",
            y="demand_score",
            color="zipcode",
            markers=True,
            title="Demand Score Over Time by Zipcode",
            labels={"month": "Month", "demand_score": "Demand Score"},
            template="plotly_white"
        )
        for trace in fig.data:
            if trace.name == "Average (All Zipcodes)":
                trace.line.color = "black"
                trace.line.width = 4
                trace.line.dash = "solid"
        fig.update_layout(
            xaxis_tickformat="%Y-%m",
            xaxis_tickangle=-45,
            xaxis=dict(tickformat="%Y-%m", dtick="M1"),
            hovermode="x unified",
            margin=dict(l=20, r=20, t=50, b=30),
            legend_title_text="Zipcode"
        )
        st.plotly_chart(fig, use_container_width=True)

    display_demand_score_trend(gap_df)


#--- Plot 5: Zipcodes Ranking ------
st.header("ZIP Code Rankings")
st.caption("The 15 ZIP codes with the highest value for the metric you pick below.")

@st.cache_data
def load_gap_ranking_data():
    df = avg_gap_scores.copy()
    df = df[df["zipcode"].notna()]
    df["zipcode"] = df["zipcode"].astype(float).astype(int).astype(str)
    return df

df_ranking = load_gap_ranking_data()

metric_options = {
    "Gap Score": "gap_score",
    "Population": "population",
    "Program Count": "program_count"
}

selected_metric_pretty = st.segmented_control(
    "Rank by:", list(metric_options.keys()), default="Gap Score", key="rank_metric"
) or "Gap Score"
selected_metric = metric_options[selected_metric_pretty]

num_zipcodes = 15
df_sorted = df_ranking.sort_values(by=selected_metric, ascending=False).head(num_zipcodes)
df_sorted = df_sorted.sort_values(by=selected_metric, ascending=True)

fig = px.bar(
    df_sorted,
    x=selected_metric,
    y="zipcode",
    orientation="h",
    text=selected_metric,
    title=f"Top {num_zipcodes} ZIP Codes Ranked by {selected_metric_pretty}",
    color_discrete_sequence=["#ffb6c1"]
)
fig.update_layout(
    title_font_size=30
)

fig.update_traces(texttemplate='%{x:.2f}', textposition='outside')
fig.update_layout(
    xaxis_title=selected_metric_pretty,
    yaxis_title="ZIP Code",
    yaxis=dict(type="category", categoryorder="total ascending"),
    height=700
)

st.plotly_chart(fig, use_container_width=True)

import plotly.graph_objects as go
import pandas as pd

# ---- Plot 6: Full ZIP Gap Score Trend ----
st.subheader("Citywide Gap Score Trend")
st.caption("The 7 ZIP codes with the highest Gap Score (red), against the citywide average (dashed) and the typical range for all ZIP codes (shaded).")

# Ensure datetime format
subset = gap_scores_with_time[gap_scores_with_time["zipcode"].isin(avg_gap_scores["zipcode"])].copy()
subset["month_dt"] = pd.to_datetime(subset["month"])

# Top 7 ZIPs by average gap score
top7 = (
    avg_gap_scores
    .sort_values(by="gap_score", ascending=False)
    .head(7)["zipcode"]
    .tolist()
)

# Overall monthly average gap score
monthly_avg = (
    gap_scores_with_time
    .copy()
    .assign(month_dt=lambda df: pd.to_datetime(df["month"]))
    .groupby("month_dt")["gap_score"]
    .mean()
    .reset_index()
)

# IQR (25th–75th percentile range) for shaded region
monthly_bounds = (
    subset
    .groupby("month_dt")["gap_score"]
    .quantile([0.25, 0.75])
    .unstack()
    .rename(columns={0.25: "q25", 0.75: "q75"})
    .reset_index()
)

# Create figure
fig6 = go.Figure()

# Add IQR shaded region
fig6.add_trace(go.Scatter(
    x=monthly_bounds["month_dt"],
    y=monthly_bounds["q25"],
    line=dict(width=0),
    hoverinfo='skip',
    showlegend=False,
    name="25th Percentile",
))
fig6.add_trace(go.Scatter(
    x=monthly_bounds["month_dt"],
    y=monthly_bounds["q75"],
    fill='tonexty',
    fillcolor='rgba(128,128,128,0.3)',
    line=dict(width=0),
    hoverinfo='skip',
    name="25–75% Range",
    showlegend=True
))

# Add gray lines for all other ZIPs
for zip_code in subset["zipcode"].unique():
    zip_df = subset[subset["zipcode"] == zip_code]
    if zip_code not in top7:
        fig6.add_trace(go.Scatter(
            x=zip_df["month_dt"],
            y=zip_df["gap_score"],
            mode='lines',
            line=dict(color='gray', width=1),
            opacity=0.2,
            name=zip_code,
            showlegend=False
        ))

# Add red lines for Top 7 ZIPs
for i, zip_code in enumerate(top7):
    zip_df = subset[subset["zipcode"] == zip_code]
    fig6.add_trace(go.Scatter(
        x=zip_df["month_dt"],
        y=zip_df["gap_score"],
        mode='lines+markers',
        line=dict(color='red', width=2),
        name="Top 7 ZIP Codes" if i == 0 else zip_code,
        showlegend=(i == 0)
    ))

# Add black dashed average line
fig6.add_trace(go.Scatter(
    x=monthly_avg["month_dt"],
    y=monthly_avg["gap_score"],
    mode='lines',
    line=dict(color='black', width=2, dash='dash'),
    name="Monthly Avg"
))

# Layout settings
fig6.update_layout(
    xaxis_title="Month",
    yaxis_title="Gap Score",
    legend_title="Legend",
    template="plotly_white",
    height=600,
    margin=dict(t=60, l=40, r=20, b=40)
)

# Render in Streamlit with a unique key
st.plotly_chart(fig6, use_container_width=True, key="plot_6_gap_trend")

# --- Disclaimer ---
st.divider()
st.caption(
    "**Note:** this dashboard is running on synthetic sample data — fictional organizations, "
    "addresses, and interaction counts generated for demonstration purposes only (see "
    "`Data/sample_data/generate_sample_data.py`). It does not reflect real SACRD program data "
    "or real food-access conditions in San Antonio."
)

