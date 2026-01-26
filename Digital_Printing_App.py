import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from streamlit_gsheets import GSheetsConnection
from datetime import timedelta, datetime
import ssl

# --- 1. PAGE CONFIG (MUST BE FIRST) ---
st.set_page_config(layout="wide", page_title="Digital Printing Production 2026")

# --- 2. INITIALIZE ---
st.set_page_config(layout="wide", page_title=FORM_TITLE)

# Initialize session states... (Keep your existing session state logic here)

# Robust Connection Initialization
# By passing the connection name, we ensure it looks at [connections.gsheets] in secrets
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. DATA HELPERS ---
def load_gsheets_data():
    try:
        # Explicitly pass URL and worksheet name here
        data = conn.read(
            spreadsheet=SPREADSHEET_URL, 
            worksheet=SHEET_NAME, 
            ttl=0
        )
        if data is not None and not data.empty:
            # Drop any completely empty rows that Google Sheets sometimes adds
            data = data.dropna(how='all')
            
            # Ensure ProductionDate is datetime objects for math, then strings for display
            data['ProductionDate'] = pd.to_datetime(data['ProductionDate'], errors='coerce')
            
            numeric_cols = ['NoOfJobs', 'DailyProductionTotal', 'YearlyProductionTotal', 'YTD_Jobs_Total']
            for col in numeric_cols:
                if col in data.columns:
                    data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)
            return data
        return pd.DataFrame(columns=ALL_COLUMNS)
    except Exception as e:
        # This is where your PEM error is being caught and displayed
        st.error(f"🚨 Connection Failed: {e}")
        return pd.DataFrame(columns=ALL_COLUMNS)

def calculate_ytd_metrics(selected_date, historical_df):
    if historical_df.empty: return 0, 0
    sel_dt = pd.to_datetime(selected_date).normalize()
    year_start = pd.to_datetime(f"{sel_dt.year}-01-01")
    ytd_mask = (historical_df['ProductionDate'] >= year_start) & (historical_df['ProductionDate'] < sel_dt)
    return int(historical_df.loc[ytd_mask, 'DailyProductionTotal'].sum()), int(historical_df.loc[ytd_mask, 'NoOfJobs'].sum())

df_main = load_gsheets_data()

# --- 6. TIMER UI ---
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
t_col3.metric("Total Downtime Recorded", formatted_downtime)

if st.button("♻️ Reset Timer"):
    st.session_state.accumulated_downtime = timedelta(0)
    st.session_state.timer_start_time = None
    st.session_state.is_timer_running = False
    st.rerun()

# --- 7. ENTRY FORM ---
st.write("---")
v = st.session_state.form_version
prod_date = st.date_input("Production Date", value=datetime.now().date(), key=f"date_{v}")
target_dt = pd.to_datetime(prod_date).normalize()

prev_ytd_prod, prev_ytd_jobs = calculate_ytd_metrics(prod_date, df_main)
date_exists = target_dt in df_main['ProductionDate'].values if not df_main.empty else False

if date_exists:
    st.warning(f"⚠️ Data for {prod_date} already exists in the sheet.")

with st.form("main_form", clear_on_submit=True):
    m1, m2, m3 = st.columns(3)
    jobs_today = m1.number_input("Jobs Today", min_value=0, step=1, key=f"jobs_{v}")
    prod_today = m2.number_input("Production Total", min_value=0, step=100, key=f"prod_{v}")
    trials_today = m3.number_input("Trials", min_value=0, step=1, key=f"trials_{v}")
    
    st.write("---")
    c1, c2 = st.columns(2)
    am_mins = c1.number_input("AM Clean (Mins)", value=45, key=f"am_{v}")
    pm_mins = c1.number_input("PM Clean (Mins)", value=45, key=f"pm_{v}")
    selected_issues = c2.multiselect("Issues:", options=ISSUE_CATEGORIES, default=["NoIssue"], key=f"issues_{v}")
    
    submitted = st.form_submit_button("Submit Data", disabled=date_exists)

if submitted:
    # Logic for calculations
    curr_ytd_prod = prev_ytd_prod + prod_today
    curr_ytd_jobs = prev_ytd_jobs + jobs_today
    
    entry = {col: "" for col in ALL_COLUMNS} # Initialize with empty strings
    entry.update({
        'ProductionDate': prod_date.strftime('%Y-%m-%d'),
        'NoOfJobs': jobs_today, 
        'NoOfTrials': trials_today,
        'DailyProductionTotal': prod_today,
        'YearlyProductionTotal': curr_ytd_prod, 
        'YTD_Jobs_Total': curr_ytd_jobs,
        'CleanMachineAm': f"{am_mins} mins",
        'CleanMachinePm': f"{pm_mins} mins",
        'CleanMachineTotal': f"{am_mins+pm_mins} mins",
        'IssueResolutionTotal': formatted_downtime,
        'TempDate': prod_date.strftime('%Y-%m-%d'),
        prod_date.strftime('%A'): 1
    })
    
    # Fill Issue slots
    for i in range(1, 11):
        entry[f'ProductionIssues_{i}'] = selected_issues[i-1] if i <= len(selected_issues) else "NoIssue"

    try:
        # Append and Update
        new_entry_df = pd.DataFrame([entry])
        updated_df = pd.concat([df_main, new_entry_df], ignore_index=True)
        
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, data=updated_df)
        
        st.success("✅ Saved Successfully!")
        st.balloons()
        # Reset form and downtime after successful save
        st.session_state.form_version += 1
        st.session_state.accumulated_downtime = timedelta(0)
        st.rerun()
    except Exception as e:
        st.error(f"❌ Save Error: {e}")

# --- 8. VIEW RECENT DATA ---
st.write("---")
st.subheader("Recent Entries")
if not df_main.empty:
    st.dataframe(df_main.tail(5), use_container_width=True)