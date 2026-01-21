import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from streamlit_gsheets import GSheetsConnection
from datetime import timedelta, datetime
import ssl
import os

# --- 0. SSL & ENVIRONMENT FIX ---
# Forces Python to ignore local certificate verification issues
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# --- 1. CONFIGURATION & CONSTANTS ---
# Using the clean URL structure to avoid 400 errors
URL_LINK = "https://docs.google.com/spreadsheets/d/1RmdsVRdN8Es6d9rAZVt8mUOLQyuz0tnHd8rkiXKVlTM/edit"
SHEET_NAME = "Data"
FORM_TITLE = "Digital Printing Production Data Entry (2026)"

ALL_COLUMNS = [
    'ProductionDate', 'NoOfJobs', 'NoOfTrials', 'DailyProductionTotal',
    'WeeklyProductionTotal', 'MonthlyProductionTotal', 'YearlyProductionTotal',
    'YTD_Jobs_Total', 'CleanMachineAm', 'CleanMachinePm', 'CleanMachineTotal',
    'IssueResolutionTotal', 'ProductionIssues_1', 'ProductionIssues_2',
    'ProductionIssues_3', 'ProductionIssues_4', 'ProductionIssues_5',
    'ProductionIssues_6', 'ProductionIssues_7', 'ProductionIssues_8',
    'ProductionIssues_9', 'ProductionIssues_10',
    'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'
]

ISSUE_CATEGORIES = ["NoIssue", "Adjust voltage", "Air pipe burst", "Barcode scans", "Clean rollers", "L/Shedding", "UV lamp issues", "Web tension error"]

# --- 2. INITIALIZE PAGE & SESSION STATE ---
st.set_page_config(layout="wide", page_title=FORM_TITLE)

if 'form_version' not in st.session_state:
    st.session_state.form_version = 0
if 'accumulated_downtime' not in st.session_state:
    st.session_state.accumulated_downtime = timedelta(0)
if 'timer_start_time' not in st.session_state:
    st.session_state.timer_start_time = None
if 'is_timer_running' not in st.session_state:
    st.session_state.is_timer_running = False

# --- 3. DATA HELPERS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_gsheets_data():
    try:
        # We use the SQL query approach to avoid the "400 Bad Request" error 
        # that sometimes happens with direct worksheet naming
        query = f'SELECT * FROM "{SHEET_NAME}"'
        data = conn.read(spreadsheet=URL_LINK, query=query, ttl=0)
        
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
        st.info("Check: Is the sheet set to 'Anyone with the link can EDIT'?")
        return pd.DataFrame(columns=ALL_COLUMNS)

def calculate_ytd_metrics(selected_date, historical_df):
    if historical_df.empty:
        return 0, 0
    sel_dt = pd.to_datetime(selected_date).normalize()
    year_start = pd.to_datetime(f"{sel_dt.year}-01-01")
    ytd_mask = (historical_df['ProductionDate'] >= year_start) & (historical_df['ProductionDate'] < sel_dt)
    return int(historical_df.loc[ytd_mask, 'DailyProductionTotal'].sum()), int(historical_df.loc[ytd_mask, 'NoOfJobs'].sum())

# Load data
df_main = load_gsheets_data()

# --- 4. UI: TITLE & TIMER ---
st.title(FORM_TITLE)
st.subheader("⏱️ Issue Downtime Tracker")
t_col1, t_col2, t_col3 = st.columns([1, 1, 2])

if not st.session_state.is_timer_running:
    if t_col1.button("▶️ Start Issue Timer"):
        st.session_state.timer_start_time = datetime.now()
        st.session_state.is_timer_running = True
        st.rerun()
else:
    if t_col1.button("⏹️ Stop Issue Timer"):
        duration = datetime.now() - st.session_state.timer_start_time
        st.session_state.accumulated_downtime += duration
        st.session_state.is_timer_running = False
        st.session_state.timer_start_time = None
        st.rerun()

if t_col2.button("🔄 Reset Timer"):
    st.session_state.accumulated_downtime = timedelta(0)
    st.rerun()

current_session = (datetime.now() - st.session_state.timer_start_time) if st.session_state.is_timer_running else timedelta(0)
total_downtime_val = st.session_state.accumulated_downtime + current_session
formatted_downtime = str(total_downtime_val).split('.')[0]
t_col3.metric("Accumulated Downtime Total", formatted_downtime)

# --- 5. ENTRY FORM ---
st.write("---")
st.subheader("📊 2026 Production Data Entry")
v = st.session_state.form_version
prod_date = st.date_input("Production Date", value=datetime.now().date(), key=f"date_{v}")
target_dt = pd.to_datetime(prod_date).normalize()

prev_ytd_prod, prev_ytd_jobs = calculate_ytd_metrics(prod_date, df_main)
date_exists = target_dt in df_main['ProductionDate'].values if not df_main.empty else False

if date_exists:
    st.warning(f"⚠️ A record for {prod_date} already exists.")

with st.form("main_form", clear_on_submit=True):
    m1, m2, m3 = st.columns(3)
    jobs_today = m1.number_input("Number of Jobs (Today)", min_value=0, step=1, key=f"jobs_{v}")
    prod_today = m2.number_input("Daily Production Total", min_value=0, step=100, key=f"prod_{v}")
    trials_today = m1.number_input("Number of Trials", min_value=0, step=1, key=f"trials_{v}")
    
    curr_ytd_prod = prev_ytd_prod + prod_today
    curr_ytd_jobs = prev_ytd_jobs + jobs_today
    
    m3.metric("2026 Production (YTD)", f"{curr_ytd_prod:,}")
    m3.metric("2026 Jobs (YTD)", f"{curr_ytd_jobs:,}")
    
    st.write("---")
    c1, c2 = st.columns(2)
    am_mins = c1.number_input("AM Clean (Mins)", value=45, key=f"am_{v}")
    pm_mins = c1.number_input("PM Clean (Mins)", value=45, key=f"pm_{v}")
    selected_issues = c2.multiselect("Select Issues:", options=ISSUE_CATEGORIES, default=["NoIssue"], key=f"issues_{v}")
    
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
        prod_date.strftime('%A'): 1
    })
    for i in range(1, 11):
        entry[f'ProductionIssues_{i}'] = selected_issues[i-1] if i <= len(selected_issues) else "NoIssue"

    try:
        new_row = pd.DataFrame([entry])
        updated_df = pd.concat([df_main, new_row], ignore_index=True)
        conn.update(spreadsheet=URL_LINK, worksheet=SHEET_NAME, data=updated_df)
        
        st.session_state.form_version += 1
        st.session_state.accumulated_downtime = timedelta(0)
        st.success("✅ Entry Saved to Google Sheets!")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Error Saving: {e}")

# --- 6. ANALYTICS ---
if not df_main.empty:
    st.write("---")
    st.subheader("📈 2026 Performance Tracking")
    df_2026 = df_main[df_main['ProductionDate'].dt.year == 2026].sort_values('ProductionDate')
    
    if not df_2026.empty:
        fig_d, ax_d = plt.subplots(figsize=(14, 5))
        ax_d.bar(df_2026['ProductionDate'].dt.strftime('%d-%b'), df_2026['DailyProductionTotal'], color='#27AE60')
        plt.xticks(rotation=45)
        st.pyplot(fig_d)

# --- 7. DELETE TOOL ---
st.write("---")
st.subheader("🗑️ Record Management")
if not df_main.empty:
    with st.expander("Delete an Entry"):
        dates = sorted(df_main['ProductionDate'].dt.date.unique(), reverse=True)
        to_del = st.selectbox("Select Date to Delete", options=dates)
        if st.button("Confirm DELETE", type="primary"):
            updated = df_main[df_main['ProductionDate'].dt.date != to_del]
            conn.update(spreadsheet=URL_LINK, worksheet=SHEET_NAME, data=updated)
            st.success(f"Deleted {to_del}")
            st.rerun()