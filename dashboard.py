
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.title("Disaster Pulse Dashboard")

# --- News Volume per Event ---
st.header("News Volume per Event")
media_df = pd.read_csv('data/Used/reliefweb_updates_media.csv')
news_volume = media_df.groupby('disaster_url').size().reset_index(name='news_count')
bar_fig = px.bar(news_volume, x='disaster_url', y='news_count', title='News Volume by Event')
st.plotly_chart(bar_fig, key="news_volume_bar_1")
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


# --- Disaster Type Distribution ---
st.header("Disaster Type Distribution")
enriched_df = pd.read_csv('data/Used/reliefweb_enriched_results.csv')
if 'disaster_type' in enriched_df.columns:
    type_counts = enriched_df['disaster_type'].value_counts().reset_index()
    type_counts.columns = ['disaster_type', 'count']
    pie_fig = px.pie(type_counts, names='disaster_type', values='count', title='Disaster Type Distribution')
    st.plotly_chart(pie_fig, key="disaster_type_pie")

# Dual-Timeline: News Volume Growth for Event A vs Event B
st.header("Dual-Timeline: News Volume Growth")
media_df = pd.read_csv('data/Used/reliefweb_updates_media.csv')
# Select two events
event_ids = media_df['disaster_url'].unique()
event_a = st.selectbox("Select Event A", event_ids)
event_b = st.selectbox("Select Event B", event_ids, index=1 if len(event_ids) > 1 else 0)

def get_event_timeline(event_id):
    df = pd.read_csv('data/Used/reliefweb_updates_media.csv')
    event_df = df[df['disaster_url'] == event_id]
    event_df['published_date'] = pd.to_datetime(event_df['published_date'], errors='coerce')
    timeline = event_df.groupby('published_date').size().cumsum().reset_index(name='cumulative_news')
    return timeline

timeline_a = get_event_timeline(event_a)
timeline_b = get_event_timeline(event_b)

fig = go.Figure()
fig.add_trace(go.Scatter(x=timeline_a['published_date'], y=timeline_a['cumulative_news'],
                         mode='lines+markers', name='Event A'))
fig.add_trace(go.Scatter(x=timeline_b['published_date'], y=timeline_b['cumulative_news'],
                         mode='lines+markers', name='Event B'))
fig.update_layout(title="Cumulative News Volume Over Time",
                  xaxis_title="Date", yaxis_title="Cumulative News Updates")
st.plotly_chart(fig, key="timeline_chart")

# Resilience Radar Chart
st.header("Resilience Radar")
import re
def get_radar_metrics(event_id):
    enriched_df = pd.read_csv('data/Used/reliefweb_enriched_results.csv')
    media_df = pd.read_csv('data/Used/reliefweb_updates_media.csv')
    enriched_row = enriched_df[enriched_df['url'] == event_id]
    if not enriched_row.empty:
        description = str(enriched_row.iloc[0]['disaster_description'])
        magnitude = description.lower().count('severe') + description.lower().count('extreme') + 1
        numbers = [int(s.replace(',', '')) for s in re.findall(r'\b\d{3,}\b', description.replace(',', ''))]
        exposure = max(numbers) if numbers else 0
        media_coverage = media_df[media_df['disaster_url'] == event_id].shape[0]
        vulnerability_keywords = ['refugee', 'malnutrition', 'displacement', 'poverty', 'camp', 'food insecurity', 'child', 'women', 'health', 'cholera', 'conflict']
        vulnerability = sum([description.lower().count(word) for word in vulnerability_keywords])
    else:
        magnitude = 1
        exposure = 0
        media_coverage = media_df[media_df['disaster_url'] == event_id].shape[0]
        vulnerability = 0
    metrics = [max(magnitude, 1), max(exposure, 1), max(media_coverage, 1), max(vulnerability, 1)]
    return metrics

metrics_a = get_radar_metrics(event_a)
metrics_b = get_radar_metrics(event_b)
categories = ['Magnitude', 'Population Exposure', 'Media Coverage', 'Vulnerability']

radar_fig = go.Figure()
radar_fig.add_trace(go.Scatterpolar(
    r=metrics_a,
    theta=categories,
    fill='toself',
    name='Event A'
))
radar_fig.add_trace(go.Scatterpolar(
    r=metrics_b,
    theta=categories,
    fill='toself',
    name='Event B'
))
radar_fig.update_layout(
    polar=dict(radialaxis=dict(visible=True)),
    showlegend=True,
    title="Resilience Radar"
)
st.plotly_chart(radar_fig, key="radar_chart")
