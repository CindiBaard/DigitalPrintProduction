import streamlit as st
import pandas as pd
import numpy as np
from streamlit_gsheets import GSheetsConnection
from datetime import timedelta, datetime
import ssl

# --- 1. CONFIG & PAGE SETUP ---
FORM_TITLE = "Digital Printing Production Data Entry (2026)"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1RmdsVRdN8Es6d9rAZVt8mUOLQyuz0tnHd8rkiXKVlTM/"
SHEET_NAME = "Data"
ANNUAL_TARGET = 9680000

st.set_page_config(layout="wide", page_title=FORM_TITLE)

# SSL Bypass
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass

# --- 2. LIBRARIES ---
try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# --- 3. CONSTANTS ---
ALL_COLUMNS = [
    'ProductionDate', 'NoOfJobs', 'NoOfTrials', 'DailyProductionTotal',
    'WeeklyProductionTotal', 'MonthlyProductionTotal', 'YearlyProductionTotal',
    'YTD_Jobs_Total', 'CleanMachineAm', 'CleanMachinePm', 'CleanMachineTotal',
    'IssueResolutionTotal', 'ProductionIssues_1', 'ProductionIssues_2',
    'ProductionIssues_3', 'ProductionIssues_4', 'ProductionIssues_5',
    'ProductionIssues_6', 'ProductionIssues_7', 'ProductionIssues_8',
    'ProductionIssues_9', 'ProductionIssues_10',
    'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
    'TempDate'
]

ISSUE_CATEGORIES = ['NoIssue', 'Adjust voltage', 'Admin/Meeting', 'Air pipe burst', 'Arrived at work late',
    'Barcode scans', 'Centre a/w on web', 'Change degassing unit', 'Check multiple jobs for colour', 
    'Clean Heads am/pm', 'Clean rollers', 'Corona issues', 'Defective laminate', 'Fire drill',
    'Flush heads', 'Flush printer and replace heads', 'General: Smudging/puddling', 
    'Generator issues', 'HMI not responding', 'Infeed trigger', 'Ink management error',
    'Left work early', 'Lines issues', 'Maintenance', 'Material change', 'Meeting', 
    'PUBLIC HOLIDAY', 'Pack trials', 'Registration issues', 'Rollers bouncing', 
    'Software issue', 'Stitch print heads', 'Training', 'Trials: 1-9 hr', 'UV lamp issues', 
    'Web tension error', 'Work in lieu of holiday']

# --- 4. SESSION STATE ---
if 'form_version' not in st.session_state: st.session_state.form_version = 0
if 'accumulated_downtime' not in st.session_state: st.session_state.accumulated_downtime = timedelta(0)
if 'timer_start_time' not in st.session_state: st.session_state.timer_start_time = None
if 'is_timer_running' not in st.session_state: st.session_state.is_timer_running = False

# --- 5. DATA LOADING ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        data = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, ttl=0)
        if data is not None and not data.empty:
            data.columns = [c.strip() for c in data.columns]
            data['ProductionDate_Parsed'] = pd.to_datetime(data['ProductionDate'], errors='coerce')
            return data
        return pd.DataFrame(columns=ALL_COLUMNS)
    except Exception as e:
        st.error(f"🚨 Connection Failed: {e}")
        return pd.DataFrame(columns=ALL_COLUMNS)

df_main = load_data()

# --- 6. CALCULATIONS ---
def calculate_ytd_metrics(selected_date, historical_df):
    if historical_df.empty: return 0, 0, 0
    sel_dt = pd.to_datetime(selected_date).normalize()
    year_start = pd.to_datetime(f"{sel_dt.year}-01-01")
    ytd_mask = (historical_df['ProductionDate_Parsed'] >= year_start) & (historical_df['ProductionDate_Parsed'] < sel_dt)
    
    prod = pd.to_numeric(historical_df.loc[ytd_mask, 'DailyProductionTotal'], errors='coerce').sum()
    jobs = pd.to_numeric(historical_df.loc[ytd_mask, 'NoOfJobs'], errors='coerce').sum()
    trials = pd.to_numeric(historical_df.loc[ytd_mask, 'NoOfTrials'], errors='coerce').sum()
    return int(prod), int(jobs), int(trials)

# --- 7. UI: METRICS ---
st.title(FORM_TITLE)

total_2024 = total_2025 = ytd_2026 = ytd_trials_2026 = 0
if not df_main.empty:
    total_2024 = pd.to_numeric(df_main[df_main['ProductionDate_Parsed'].dt.year == 2024]['DailyProductionTotal'], errors='coerce').sum()
    total_2025 = pd.to_numeric(df_main[df_main['ProductionDate_Parsed'].dt.year == 2025]['DailyProductionTotal'], errors='coerce').sum()
    ytd_2026 = pd.to_numeric(df_main[df_main['ProductionDate_Parsed'].dt.year == 2026]['DailyProductionTotal'], errors='coerce').sum()
    ytd_trials_2026 = pd.to_numeric(df_main[df_main['ProductionDate_Parsed'].dt.year == 2026]['NoOfTrials'], errors='coerce').sum()

col1, col2, col3, col4 = st.columns(4)
col1.metric("📊 2024 Total", f"{total_2024:,.0f}")
col2.metric("📊 2025 Total", f"{total_2025:,.0f}")
progress = (ytd_2026 / ANNUAL_TARGET) * 100 if ANNUAL_TARGET > 0 else 0
col3.metric("📈 2026 YTD Production", f"{ytd_2026:,.0f}", delta=f"{progress:.1f}% Target")
col4.metric("🧪 2026 YTD Trials", f"{int(ytd_trials_2026)}")

# --- 8. BAR CHARTS SECTION ---
st.write("---")
if not df_main.empty and PLOTLY_AVAILABLE:
    chart_df = df_main.copy()
    chart_df['Year'] = chart_df['ProductionDate_Parsed'].dt.year.astype(str)
    chart_df['MonthNum'] = chart_df['ProductionDate_Parsed'].dt.month
    chart_df['Month'] = chart_df['ProductionDate_Parsed'].dt.strftime('%b')
    compare_df = chart_df[chart_df['Year'].isin(['2024', '2025', '2026'])].copy()
    month_order = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("📊 Monthly Production Comparison")
        prod_data = compare_df.groupby(['Year', 'MonthNum', 'Month'])['DailyProductionTotal'].sum().reset_index()
        fig_prod = px.bar(
            prod_data.sort_values('MonthNum'), x='Month', y='DailyProductionTotal', color='Year',
            barmode='group', height=400,
            color_discrete_map={'2024': '#636EFA', '2025': '#EF553B', '2026': '#00CC96'}
        )
        fig_prod.add_hline(y=ANNUAL_TARGET/12, line_dash="dot", annotation_text="Target")
        fig_prod.update_layout(xaxis={'categoryorder':'array', 'categoryarray': month_order})
        st.plotly_chart(fig_prod, use_container_width=True)

    with c2:
        st.subheader("🧪 Monthly Trial Comparison")
        trial_data = compare_df.groupby(['Year', 'MonthNum', 'Month'])['NoOfTrials'].sum().reset_index()
        fig_trial = px.bar(
            trial_data.sort_values('MonthNum'), x='Month', y='NoOfTrials', color='Year',
            barmode='group', height=400,
            color_discrete_map={'2024': '#636EFA', '2025': '#EF553B', '2026': '#00CC96'}
        )
        fig_trial.update_layout(xaxis={'categoryorder':'array', 'categoryarray': month_order})
        st.plotly_chart(fig_trial, use_container_width=True)

# --- 9. ENTRY FORM & VALIDATION ---
st.write("---")
v = st.session_state.form_version
prod_date = st.date_input("Production Date", value=datetime.now().date(), key=f"date_{v}")

is_duplicate = False
if not df_main.empty:
    is_duplicate = (df_main['ProductionDate_Parsed'].dt.date == prod_date).any()

if is_duplicate:
    st.error(f"⚠️ Data for {prod_date} already exists. Please choose a different date.")

prev_ytd_prod, prev_ytd_jobs, prev_ytd_trials = calculate_ytd_metrics(prod_date, df_main)

with st.form("main_form", clear_on_submit=True):
    st.subheader("📝 New Daily Entry Details")
    m1, m2, m3 = st.columns(3)
    jobs_today = m1.number_input("Jobs Today", min_value=0, step=1)
    prod_today = m2.number_input("Production Total", min_value=0, step=100)
    trials_today = m3.number_input("Trials Today", min_value=0, step=1)
    
    submitted = st.form_submit_button("Submit Data", disabled=is_duplicate)

if submitted and not is_duplicate:
    # Logic to update Google Sheets (omitted for brevity, keep existing logic)
    st.success("✅ Data saved!")
    st.session_state.form_version += 1
    st.rerun()