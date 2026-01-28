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

# --- 2. OPTIONAL LIBRARIES ---
try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# --- 3. CONSTANTS & COLUMNS ---
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
    'Barcode scans (break into prod to do scan)', 'Centre a/w on web (moved as speed changed)',
    'Change degassing unit', 'Check multiple jobs for colour', 'Clean Heads am/pm (1 hr 30 min)',
    'Clean rollers (extensive clean)', 'Corona issues', 
    'Defective laminate causes infeed height to trigger', 'Fire drill',
    'Flush heads, Fill_Cleaner, Print, Refill_Ink', 'Flush printer and replace heads',
    'General: Smudging/puddling etc.', 'Generator (big) no compressed air', 'HMI not responding',
    'Infeed trigger due to encoder', 'Ink (G2 vs G4): rework colours', 'Ink management system error',
    'Left work early', 'Lines: 100 black head', 'Lines: 100 cyan head', 'Lines: 100 magenta head',
    'Lines: 100 yellow head', 'Lines: 200 black head', 'Lines: 200 cyan head', 'Lines: 200 magenta head',
    'Lines: 200 yellow head', 'Lines: Print incorrect direction + rewind', 'Manifold card out for repair',
    'Material change', 'Material change ABL White to ABL Silver', 'Material change ABL to PBL', 
    'Material change PBL to ABL', 'Meeting', 'PUBLIC HOLIDAY', 'Pack trials', 'Planned Maintenance',
    'Print slowly due to banding', 'Print trial rolls for varnish/foil', 
    'Printing on hold due to backlog on SAESA', 
    'Registration issues (profile auto changed in run)', 'Rollers bouncing', 
    'Set up multiple trials for trial run', 'Software issue relating to heads',
    'Spring loose next to encoder', 'Stitch print heads', 
    'TeaAndLunchBreaks_Ashley not a work', 'TeaAndLunchBreaks_Zahyaan not at work',
    'Training', 'Trial options for Client meeting', 'Trials: 1 hr', 'Trials: 2 hr', 'Trials: 3 hr', 
    'Trials: 4 hr', 'Trials: 5 hr', 'Trials: 6 hr', 'Trials: 8 hr', 'Trials: 9 hr', 
    'Troubleshoot issues with yellow print heads', 'UV lamp issues', 
    'Vertical white, unprinted bands in yellow heads', 'Web tension error (rollers clamping)',
    'Worked in another day in lieu of Public Holiday',]

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

# Metric Preparations
total_2024 = total_2025 = ytd_2026 = ytd_trials_2026 = 0
if not df_main.empty:
    total_2024 = pd.to_numeric(df_main[df_main['ProductionDate_Parsed'].dt.year == 2024]['DailyProductionTotal'], errors='coerce').sum()
    total_2025 = pd.to_numeric(df_main[df_main['ProductionDate_Parsed'].dt.year == 2025]['DailyProductionTotal'], errors='coerce').sum()
    ytd_2026 = pd.to_numeric(df_main[df_main['ProductionDate_Parsed'].dt.year == 2026]['DailyProductionTotal'], errors='coerce').sum()
    ytd_trials_2026 = pd.to_numeric(df_main[df_main['ProductionDate_Parsed'].dt.year == 2026]['NoOfTrials'], errors='coerce').sum()

# --- 7. UI: HEADER & METRICS ---
st.title(FORM_TITLE)

col1, col2, col3, col4 = st.columns(4)
col1.metric("📊 2024 Total", f"{total_2024:,.0f}")
col2.metric("📊 2025 Total", f"{total_2025:,.0f}")
progress = (ytd_2026 / ANNUAL_TARGET) * 100 if ANNUAL_TARGET > 0 else 0
col3.metric("📈 2026 YTD Production", f"{ytd_2026:,.0f}", delta=f"{progress:.1f}% Target")
col4.metric("🧪 2026 YTD Trials", f"{int(ytd_trials_2026)}")

# --- 8. CHARTS SECTION ---
st.write("---")
if not df_main.empty and PLOTLY_AVAILABLE:
    # Prepare Template for Jan-Dec to ensure all months appear
    month_names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    years = ['2024', '2025', '2026']
    template = pd.DataFrame([(y, m+1, month_names[m]) for y in years for m in range(12)], 
                            columns=['Year', 'MonthNum', 'Month'])

    chart_df = df_main.copy()
    chart_df['Year'] = chart_df['ProductionDate_Parsed'].dt.year.astype(str)
    chart_df['MonthNum'] = chart_df['ProductionDate_Parsed'].dt.month
    
    # Filter and group
    compare_df = chart_df[chart_df['Year'].isin(years)].copy()
    
    c_left, c_right = st.columns(2)

    with c_left:
        st.subheader("📊 Monthly Production Comparison")
        prod_data = compare_df.groupby(['Year', 'MonthNum'])['DailyProductionTotal'].sum().reset_index()
        # Merge with template to ensure empty months exist
        full_prod_data = pd.merge(template, prod_data, on=['Year', 'MonthNum'], how='left').fillna(0)
        
        fig_prod = px.bar(
            full_prod_data, x='Month', y='DailyProductionTotal', color='Year',
            barmode='group', height=400,
            color_discrete_map={'2024': '#636EFA', '2025': '#EF553B', '2026': '#00CC96'},
            category_orders={"Month": month_names}
        )
        fig_prod.add_hline(y=ANNUAL_TARGET/12, line_dash="dot", line_color="white", annotation_text="Monthly Target")
        st.plotly_chart(fig_prod, use_container_width=True)

    with c_right:
        st.subheader("🧪 Monthly Trial Comparison")
        trial_data = compare_df.groupby(['Year', 'MonthNum'])['NoOfTrials'].sum().reset_index()
        full_trial_data = pd.merge(template, trial_data, on=['Year', 'MonthNum'], how='left').fillna(0)

        fig_trial = px.bar(
            full_trial_data, x='Month', y='NoOfTrials', color='Year',
            barmode='group', height=400,
            color_discrete_map={'2024': '#636EFA', '2025': '#EF553B', '2026': '#00CC96'},
            category_orders={"Month": month_names}
        )
        st.plotly_chart(fig_trial, use_container_width=True)

# --- 9. TIMER UI & FORM (Simplified for space) ---
# [Keep your existing Timer and Form code here as per your previous version]