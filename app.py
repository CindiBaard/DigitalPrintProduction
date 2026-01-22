import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from streamlit_gsheets import GSheetsConnection
from datetime import timedelta, datetime
import ssl

# --- 0. SSL BYPASS ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass

# --- 1. CONFIGURATION ---
# Replace this URL with your actual Google Sheet URL if different
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1RmdsVRdN8Es6d9rAZVt8mUOLQyuz0tnHd8rkiXKVlTM/"
SHEET_NAME = "Data" 
FORM_TITLE = "Digital Printing Production Data Entry (2026)"

# Columns exactly matching your CSV
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

ISSUE_CATEGORIES = ["NoIssue", "Adjust voltage", "Air pipe burst", "Barcode scans", "Clean rollers", "L/Shedding", "UV lamp issues", "Web tension error"]

# --- 2. INITIALIZE ---
st.set_page_config(layout="wide", page_title=FORM_TITLE)

if 'form_version' not in st.session_state:
    st.session_state.form_version = 0
if 'accumulated_downtime' not in st.session_state:
    st.session_state.accumulated_downtime = timedelta(0)
if 'timer_start_time' not in st.session_state:
    st.session_state.timer_start_time = None
if 'is_timer_running' not in st.session_state:
    st.session_state.is_timer_running = False

# Standard connection initialization
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. DATA HELPERS ---
def load_gsheets_data():
    try:
        # We pass the spreadsheet URL here to fix the "Spreadsheet must be specified" error
        data = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, ttl=0)
        if data is not None and not data.empty:
            data['ProductionDate'] = pd.to_datetime(data['ProductionDate']).dt.normalize()
            numeric_cols = ['NoOfJobs', 'DailyProductionTotal', 'YearlyProductionTotal', 'YTD_Jobs_Total']
            for col in numeric_cols:
                if col in data.columns:
                    data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)
            return data
        return pd.DataFrame(columns=ALL_COLUMNS)
    except Exception as e:
        st.error(f"🚨 Connection Failed: {e}")
        st.info("Tip: Ensure your Service Account email is added as an 'Editor' on the Google Sheet.")
        return pd.DataFrame(columns=ALL_COLUMNS)

def calculate_ytd_metrics(selected_date, historical_df):
    if historical_df.empty: return 0, 0
    sel_dt = pd.to_datetime(selected_date).normalize()
    year_start = pd.to_datetime(f"{sel_dt.year}-01-01")
    ytd_mask = (historical_df['ProductionDate'] >= year_start) & (historical_df['ProductionDate'] < sel_dt)
    return int(historical_df.loc[ytd_mask, 'DailyProductionTotal'].sum()), int(historical_df.loc[ytd_mask, 'NoOfJobs'].sum())

df_main = load_gsheets_data()

# --- 4. TIMER UI ---
st.title(FORM_TITLE)
st.subheader("⏱️ Issue Downtime Tracker")
t_col1, t_col2, t_col3 = st.columns([1, 1, 2])

if not st.session_state.is_timer_running:
    if t_col1.button("▶️ Start Timer"):
        st.session_state.timer_start_time = datetime.now()
        st.session_state.is_timer_running = True
        st.rerun()
else:
    if t_col1.button("⏹️ Stop Timer"):
        duration = datetime.now() - st.session_state.timer_start_time
        st.session_state.accumulated_downtime += duration
        st.session_state.is_timer_running = False
        st.rerun()

current_session = (datetime.now() - st.session_state.timer_start_time) if st.session_state.is_timer_running else timedelta(0)
total_downtime_val = st.session_state.accumulated_downtime + current_session
formatted_downtime = str(total_downtime_val).split('.')[0]
t_col3.metric("Total Downtime", formatted_downtime)

# --- 5. ENTRY FORM ---
st.write("---")
v = st.session_state.form_version
prod_date = st.date_input("Production Date", value=datetime.now().date(), key=f"date_{v}")
target_dt = pd.to_datetime(prod_date).normalize()

prev_ytd_prod, prev_ytd_jobs = calculate_ytd_metrics(prod_date, df_main)
date_exists = target_dt in df_main['ProductionDate'].values if not df_main.empty else False

with st.form("main_form", clear_on_submit=True):
    m1, m2, m3 = st.columns(3)
    jobs_today = m1.number_input("Jobs Today", min_value=0, step=1, key=f"jobs_{v}")
    prod_today = m2.number_input("Production Total", min_value=0, step=100, key=f"prod_{v}")
    trials_today = m3.number_input("Trials", min_value=0, step=1, key=f"trials_{v}")
    
    curr_ytd_prod = prev_ytd_prod + prod_today
    curr_ytd_jobs = prev_ytd_jobs + jobs_today
    
    st.write("---")
    c1, c2 = st.columns(2)
    am_mins = c1.number_input("AM Clean (Mins)", value=45, key=f"am_{v}")
    pm_mins = c1.number_input("PM Clean (Mins)", value=45, key=f"pm_{v}")
    selected_issues = c2.multiselect("Issues:", options=ISSUE_CATEGORIES, default=["NoIssue"], key=f"issues_{v}")
    
    submitted = st.form_submit_button("Submit Data", disabled=date_exists)

if submitted and not date_exists:
    entry = {col: 0 for col in ALL_COLUMNS}
    entry.update({
        'ProductionDate': prod_date.isoformat(),
        'NoOfJobs': jobs_today, 'NoOfTrials': trials_today,
        'DailyProductionTotal': prod_today,
        'YearlyProductionTotal': curr_ytd_prod, 'YTD_Jobs_Total': curr_ytd_jobs,
        'CleanMachineAm': str(timedelta(minutes=am_mins)),
        'CleanMachinePm': str(timedelta(minutes=pm_mins)),
        'CleanMachineTotal': str(timedelta(minutes=am_mins+pm_mins)),
        'IssueResolutionTotal': formatted_downtime,
        'TempDate': prod_date.isoformat(),
        prod_date.strftime('%A'): 1
    })
    for i in range(1, 11):
        entry[f'ProductionIssues_{i}'] = selected_issues[i-1] if i <= len(selected_issues) else "NoIssue"

    try:
        updated_df = pd.concat([df_main, pd.DataFrame([entry])], ignore_index=True)
        # We must also provide the spreadsheet URL here for updating
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, data=updated_df)
        st.success("✅ Saved!")
        st.session_state.form_version += 1
        st.rerun()
    except Exception as e:
        st.error(f"❌ Save Error: {e}")
