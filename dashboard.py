import re
from collections import Counter

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(page_title="Disaster Pulse Dashboard", layout="wide")
st.title("Disaster Pulse Dashboard")
st.caption("Interactive media intelligence on ReliefWeb disaster reporting")


@st.cache_data
def load_data():
    media = pd.read_csv("data/Used/reliefweb_updates_media.csv")
    enriched = pd.read_csv("data/Used/reliefweb_enriched_results.csv")
    results = pd.read_csv("data/Used/reliefweb_results.csv")

    media["published_date"] = pd.to_datetime(media["published_date"], errors="coerce", utc=True).dt.tz_convert(None)
    media["posted_date"] = pd.to_datetime(media["posted_date"], errors="coerce", utc=True).dt.tz_convert(None)

    event_meta = enriched[["url", "title", "country", "disaster_type_code"]].rename(
        columns={
            "url": "disaster_url",
            "title": "event_title",
            "country": "event_country",
            "disaster_type_code": "event_type_code",
        }
    )

    media = media.merge(event_meta, on="disaster_url", how="left")
    media["event_label"] = media["event_title"].fillna(media["disaster_url"])
    media["lag_days"] = (media["posted_date"] - media["published_date"]).dt.days

    return media, enriched, results


media_df, enriched_df, results_df = load_data()

if media_df.empty:
    st.error("No rows found in media CSV.")
    st.stop()


# -------------------------------
# Sidebar filters
# -------------------------------
st.sidebar.header("Filters")

all_events = sorted(media_df["event_label"].dropna().unique().tolist())
all_sources = sorted(media_df["source"].dropna().unique().tolist())
all_formats = sorted(media_df["format"].dropna().unique().tolist())

selected_events = st.sidebar.multiselect("Events", all_events, default=all_events)
selected_sources = st.sidebar.multiselect("Sources", all_sources, default=all_sources)
selected_formats = st.sidebar.multiselect("Formats", all_formats, default=all_formats)

min_date = media_df["published_date"].min()
max_date = media_df["published_date"].max()

if pd.notna(min_date) and pd.notna(max_date):
    selected_dates = st.sidebar.date_input(
        "Published date range",
        value=(min_date.date(), max_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date(),
    )
else:
    selected_dates = None

filtered = media_df.copy()
filtered = filtered[filtered["event_label"].isin(selected_events)]
filtered = filtered[filtered["source"].isin(selected_sources)]
filtered = filtered[filtered["format"].isin(selected_formats)]

if selected_dates is not None and isinstance(selected_dates, tuple) and len(selected_dates) == 2:
    start_date, end_date = selected_dates
    filtered = filtered[
        (filtered["published_date"].dt.date >= start_date)
        & (filtered["published_date"].dt.date <= end_date)
    ]

if filtered.empty:
    st.warning("No data after filters. Adjust sidebar filters to continue.")
    st.stop()


# -------------------------------
# KPIs
# -------------------------------
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Articles", f"{len(filtered):,}")
kpi2.metric("Events", f"{filtered['event_label'].nunique()}")
kpi3.metric("Sources", f"{filtered['source'].nunique()}")
kpi4.metric("Formats", f"{filtered['format'].nunique()}")


# -------------------------------
# Original core views: Dual-Timeline + Resilience Radar
# -------------------------------
st.header("Original Core Views")

event_options = sorted(filtered["event_label"].dropna().unique().tolist())

if len(event_options) >= 1:
    core_col1, core_col2 = st.columns(2)
    with core_col1:
        event_a_label = st.selectbox("Select Event A", event_options, key="core_event_a")
    with core_col2:
        default_idx = 1 if len(event_options) > 1 else 0
        event_b_label = st.selectbox("Select Event B", event_options, index=default_idx, key="core_event_b")

    def get_event_url_from_label(event_label):
        url_candidates = (
            filtered.loc[filtered["event_label"] == event_label, "disaster_url"]
            .dropna()
            .value_counts()
        )
        if url_candidates.empty:
            return None
        return url_candidates.index[0]

    def get_event_timeline(event_label):
        event_df = filtered[filtered["event_label"] == event_label].copy()
        event_df = event_df.dropna(subset=["published_date"])
        if event_df.empty:
            return pd.DataFrame(columns=["published_date", "cumulative_news"])

        timeline = (
            event_df.groupby("published_date")
            .size()
            .sort_index()
            .cumsum()
            .reset_index(name="cumulative_news")
        )
        return timeline

    timeline_a = get_event_timeline(event_a_label)
    timeline_b = get_event_timeline(event_b_label)

    st.subheader("Dual-Timeline: News Volume Growth")
    fig_core_timeline = go.Figure()
    fig_core_timeline.add_trace(
        go.Scatter(
            x=timeline_a["published_date"],
            y=timeline_a["cumulative_news"],
            mode="lines+markers",
            name=event_a_label,
        )
    )
    fig_core_timeline.add_trace(
        go.Scatter(
            x=timeline_b["published_date"],
            y=timeline_b["cumulative_news"],
            mode="lines+markers",
            name=event_b_label,
        )
    )
    fig_core_timeline.update_layout(
        title="Cumulative News Volume Over Time",
        xaxis_title="Date",
        yaxis_title="Cumulative News Updates",
    )
    st.plotly_chart(fig_core_timeline, width="stretch", key="original_dual_timeline")

    st.subheader("Resilience Radar")

    def get_radar_metrics(event_url):
        if not event_url:
            return [1, 1, 1, 1]

        enriched_row = enriched_df[enriched_df["url"] == event_url]
        media_coverage = media_df[media_df["disaster_url"] == event_url].shape[0]

        if enriched_row.empty:
            return [1, 1, max(media_coverage, 1), 1]

        description = str(enriched_row.iloc[0].get("disaster_description", "") or "")
        description_lower = description.lower()

        magnitude = description_lower.count("severe") + description_lower.count("extreme") + 1

        raw_numbers = re.findall(r"\b\d{1,3}(?:,\d{3})*\b", description)
        cleaned_numbers = [int(num.replace(",", "")) for num in raw_numbers if num]
        exposure = max(cleaned_numbers) if cleaned_numbers else 0

        vulnerability_keywords = [
            "refugee", "malnutrition", "displacement", "poverty", "camp",
            "food insecurity", "child", "women", "health", "cholera", "conflict"
        ]
        vulnerability = sum(description_lower.count(word) for word in vulnerability_keywords)

        return [
            max(magnitude, 1),
            max(exposure, 1),
            max(media_coverage, 1),
            max(vulnerability, 1),
        ]

    radar_event_labels = st.multiselect(
        "Events to include in radar",
        options=event_options,
        default=event_options,
        key="radar_event_selector",
    )

    categories = ["Magnitude", "Population Exposure", "Media Coverage", "Vulnerability"]

    radar_fig = go.Figure()
    for event_label in radar_event_labels:
        event_url = get_event_url_from_label(event_label)
        metrics = get_radar_metrics(event_url)
        radar_fig.add_trace(
            go.Scatterpolar(
                r=metrics,
                theta=categories,
                fill="toself",
                name=event_label,
            )
        )

    radar_fig.update_layout(
        polar=dict(radialaxis=dict(visible=True)),
        showlegend=True,
        title="Resilience Radar",
    )
    if radar_event_labels:
        st.plotly_chart(radar_fig, width="stretch", key="original_resilience_radar")
    else:
        st.info("Select at least one event to display the radar chart.")


# -------------------------------
# 1) Source concentration by event
# Question: Which organizations dominate coverage for each event?
# -------------------------------
st.header("1) Source Concentration by Event")
source_event_counts = (
    filtered.groupby(["event_label", "source"])
    .size()
    .reset_index(name="article_count")
)

top_source_event = (
    source_event_counts.sort_values("article_count", ascending=False)
    .groupby("event_label")
    .head(5)
)

fig_source_event = px.bar(
    top_source_event,
    x="event_label",
    y="article_count",
    color="source",
    title="Top 5 Sources per Event",
    barmode="stack",
)
fig_source_event.update_layout(xaxis_title="Event", yaxis_title="Articles", legend_title="Source")
st.plotly_chart(fig_source_event, width="stretch", key="source_concentration_event")


# -------------------------------
# 2) Publishing timeline + peak detector
# Question: When did media attention peak for a selected event?
# -------------------------------
st.header("2) Publishing Timeline and Peak Detection")

focus_event = st.selectbox(
    "Pick one event for timeline analysis",
    sorted(filtered["event_label"].dropna().unique().tolist()),
)

freq_choice = st.radio("Time granularity", options=["Daily", "Weekly", "Monthly"], horizontal=True)
freq_map = {"Daily": "D", "Weekly": "W", "Monthly": "MS"}

event_timeline = filtered[filtered["event_label"] == focus_event].copy()
event_timeline = event_timeline.dropna(subset=["published_date"])

time_series = (
    event_timeline
    .set_index("published_date")
    .resample(freq_map[freq_choice])
    .size()
    .reset_index(name="article_count")
)

if not time_series.empty:
    peak_row = time_series.loc[time_series["article_count"].idxmax()]
    fig_timeline = px.bar(
        time_series,
        x="published_date",
        y="article_count",
        title=f"{focus_event} — {freq_choice} publishing volume",
    )
    fig_timeline.add_trace(
        go.Scatter(
            x=[peak_row["published_date"]],
            y=[peak_row["article_count"]],
            mode="markers+text",
            text=["Peak"],
            textposition="top center",
            marker=dict(size=13, color="red", symbol="diamond"),
            name="Peak",
        )
    )
    fig_timeline.update_layout(xaxis_title="Date", yaxis_title="Articles")
    st.plotly_chart(fig_timeline, width="stretch", key="timeline_peak")

    peak_col1, peak_col2 = st.columns(2)
    peak_col1.metric("Peak Volume", f"{int(peak_row['article_count'])} articles")
    peak_col2.metric("Peak Date", peak_row["published_date"].strftime("%Y-%m-%d"))
else:
    st.info("No publish dates available for this event after filters.")


# -------------------------------
# 3) Source mix evolution over time
# Question: How did source dominance change over time for an event?
# -------------------------------
st.header("3) Source Mix Evolution")

mix_event = st.selectbox(
    "Pick event for source-mix trend",
    sorted(filtered["event_label"].dropna().unique().tolist()),
    key="mix_event_select",
)

event_mix = filtered[filtered["event_label"] == mix_event].copy()
event_mix = event_mix.dropna(subset=["published_date", "source"])

if not event_mix.empty:
    top_n_sources = st.slider("Number of top sources", min_value=3, max_value=10, value=6)
    top_sources = event_mix["source"].value_counts().head(top_n_sources).index
    event_mix["source_grouped"] = event_mix["source"].where(event_mix["source"].isin(top_sources), "Other")

    source_mix_ts = (
        event_mix
        .assign(month=event_mix["published_date"].dt.to_period("M").dt.to_timestamp())
        .groupby(["month", "source_grouped"])
        .size()
        .reset_index(name="article_count")
    )

    fig_mix = px.area(
        source_mix_ts,
        x="month",
        y="article_count",
        color="source_grouped",
        title=f"Monthly Source Composition — {mix_event}",
    )
    fig_mix.update_layout(xaxis_title="Month", yaxis_title="Articles", legend_title="Source")
    st.plotly_chart(fig_mix, width="stretch", key="source_mix_evolution")
else:
    st.info("No data to plot source mix for this event.")


# -------------------------------
# 4) Format x Source heatmap
# Question: Which source specializes in which content format?
# -------------------------------
st.header("4) Source-Format Specialization")

heatmap_data = (
    filtered.groupby(["source", "format"])\
    .size()\
    .reset_index(name="article_count")
)

if not heatmap_data.empty:
    source_limit = st.slider("Heatmap source limit", min_value=5, max_value=20, value=12)
    top_heat_sources = (
        heatmap_data.groupby("source")["article_count"]
        .sum()
        .sort_values(ascending=False)
        .head(source_limit)
        .index
    )
    heatmap_view = heatmap_data[heatmap_data["source"].isin(top_heat_sources)]

    fig_heat = px.density_heatmap(
        heatmap_view,
        x="format",
        y="source",
        z="article_count",
        histfunc="sum",
        color_continuous_scale="Blues",
        title="Source vs Format Intensity",
    )
    fig_heat.update_layout(xaxis_title="Format", yaxis_title="Source")
    st.plotly_chart(fig_heat, width="stretch", key="source_format_heatmap")
else:
    st.info("No data for source-format heatmap.")


# -------------------------------
# 5) Headline theme explorer
# Question: What themes dominate headlines for each event/source slice?
# -------------------------------
st.header("5) Headline Theme Explorer")

STOPWORDS = {
    "flood", "floods", "yemen", "bangladesh", "cyclone", "report", "update",
    "situation", "humanitarian", "oct", "aug", "may", "january", "february",
    "march", "april", "june", "july", "september", "november", "december",
    "2023", "2024", "2025", "2026", "daily"
}

theme_event = st.selectbox(
    "Pick event for headline themes",
    sorted(filtered["event_label"].dropna().unique().tolist()),
    key="theme_event_select",
)

theme_source = st.selectbox(
    "Optional source focus",
    options=["All Sources"] + sorted(filtered["source"].dropna().unique().tolist()),
)

theme_df = filtered[filtered["event_label"] == theme_event].copy()
if theme_source != "All Sources":
    theme_df = theme_df[theme_df["source"] == theme_source]

text_blob = " ".join(theme_df["title"].dropna().astype(str).tolist()).lower()
words = re.findall(r"[a-z]{4,}", text_blob)
words = [word for word in words if word not in STOPWORDS]
word_counts = Counter(words).most_common(15)

if word_counts:
    theme_frame = pd.DataFrame(word_counts, columns=["keyword", "count"])
    fig_theme = px.bar(
        theme_frame.sort_values("count", ascending=True),
        x="count",
        y="keyword",
        orientation="h",
        title="Top Headline Keywords",
    )
    fig_theme.update_layout(xaxis_title="Mentions", yaxis_title="Keyword")
    st.plotly_chart(fig_theme, width="stretch", key="headline_themes")
else:
    st.info("Not enough title text to extract themes for this slice.")


st.markdown("---")
st.caption("Data source: ReliefWeb CSV exports in data/Used")
