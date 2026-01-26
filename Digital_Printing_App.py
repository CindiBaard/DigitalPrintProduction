import streamlit as st
import pandas as pd
import numpy as np
from streamlit_gsheets import GSheetsConnection
from datetime import timedelta, datetime
import ssl

# --- 1. CONFIGURATION (Must be defined before Page Config) ---
FORM_TITLE = "Digital Printing Production Data Entry (2026)"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1RmdsVRdN8Es6d9rAZVt8mUOLQyuz0tnHd8rkiXKVlTM/"
SHEET_NAME = "Data" 

# --- 2. PAGE CONFIG (THE ABSOLUTE FIRST STREAMLIT COMMAND) ---
st.set_page_config(layout="wide", page_title=FORM_TITLE)

# --- 3. SSL BYPASS & SESSION INITIALIZATION ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass

if 'form_version' not in st.session_state:
    st.session_state.form_version = 0
if 'accumulated_downtime' not in st.session_state:
    st.session_state.accumulated_downtime = timedelta(0)
if 'timer_start_time' not in st.session_state:
    st.session_state.timer_start_time = None
if 'is_timer_running' not in st.session_state:
    st.session_state.is_timer_running = False

# --- 4. DATA CONSTANTS ---
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

# --- 5. INITIALIZE CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 6. HELPER FUNCTIONS ---
def load_gsheets_data():
    try:
        data = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, ttl=0)
        if data is not None and not data.empty:
            # Clean empty rows and normalize dates
            data = data.dropna(how='all')
            data['ProductionDate'] = pd.to_datetime(data['ProductionDate']).dt.normalize()
            # Ensure numbers are treated as numbers
            num_cols = ['NoOfJobs', 'DailyProductionTotal', 'YearlyProductionTotal', 'YTD_Jobs_Total']
            for col in num_cols:
                if col in data.columns:
                    data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)
            return data
        return pd.DataFrame(columns=ALL_COLUMNS)
    except Exception as e:
        st.error(f"🚨 Connection Failed: {e}")
        return pd.DataFrame(columns=ALL_COLUMNS)

def calculate_ytd_metrics(selected_date, historical_df):
    if historical_df.empty: return 0, 0
    sel_dt = pd.to_datetime(selected_date).normalize()
    year_start = pd.to_datetime(f"{sel_dt.year}-01-01")
    ytd_mask = (historical_df['ProductionDate'] >= year_start) & (historical_df['ProductionDate'] < sel_dt)
    return int(historical_df.loc[ytd_mask, 'DailyProductionTotal'].sum()), int(historical_df.loc[ytd_mask, 'NoOfJobs'].sum())

# Load data initially
df_main = load_gsheets_data()

# --- 7. TIMER UI ---
st.title(f"🔍 {FORM_TITLE}")
st.subheader("⏱️ Issue Downtime Tracker")
t_col1, t_col2, t_col3, t_col4 = st.columns([1, 1, 1, 2])

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

if t_col2.button("♻️ Reset Timer"):
    st.session_state.accumulated_downtime = timedelta(0)
    st.session_state.timer_start_time = None
    st.session_state.is_timer_running = False
    st.rerun()

current_session = (datetime.now() - st.session_state.timer_start_time) if st.session_state.is_timer_running else timedelta(0)
total_downtime_val = st.session_state.accumulated_downtime + current_session
formatted_downtime = str(total_downtime_val).split('.')[0] # Format as HH:MM:SS
t_col4.metric("Total Downtime Recorded", formatted_downtime)

# --- 8. ENTRY FORM ---
st.write("---")
v = st.session_state.form_version
prod_date = st.date_input("Production Date", value=datetime.now().date(), key=f"date_{v}")
target_dt = pd.to_datetime(prod_date).normalize()

# Check if date already exists
date_exists = False
if not df_main.empty:
    date_exists = target_dt in df_main['ProductionDate'].values

if date_exists:
    st.warning(f"⚠️ An entry for {prod_date} already exists. Submission is disabled to prevent duplicates.")

with st.form("main_form", clear_on_submit=True):
    m1, m2, m3 = st.columns(3)
    jobs_today = m1.number_input("Jobs Today", min_value=0, step=1, key=f"jobs_{v}")
    prod_today = m2.number_input("Production Total (Impressions/Metres)", min_value=0, step=100, key=f"prod_{v}")
    trials_today = m3.number_input("Trials", min_value=0, step=1, key=f"trials_{v}")
    
    st.write("---")
    c1, c2 = st.columns(2)
    am_mins = c1.number_input("AM Clean (Minutes)", value=45, key=f"am_{v}")
    pm_mins = c1.number_input("PM Clean (Minutes)", value=45, key=f"pm_{v}")
    selected_issues = c2.multiselect("Production Issues encountered:", options=ISSUE_CATEGORIES, default=["NoIssue"], key=f"issues_{v}")
    
    submitted = st.form_submit_button("🚀 Submit Daily Production Data", disabled=date_exists)

if submitted:
    # Calculations
    prev_ytd_prod, prev_ytd_jobs = calculate_ytd_metrics(prod_date, df_main)
    curr_ytd_prod = prev_ytd_prod + prod_today
    curr_ytd_jobs = prev_ytd_jobs + jobs_today
    
    # Map dictionary to columns
    entry = {col: "" for col in ALL_COLUMNS}
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
        prod_date.strftime('%A'): 1 # Marks the day of the week column
    })
    
    # Fill issue columns (up to 10)
    for i in range(1, 11):
        entry[f'ProductionIssues_{i}'] = selected_issues[i-1] if i <= len(selected_issues) else "NoIssue"

    try:
        # Append to existing data and update sheet
        new_row_df = pd.DataFrame([entry])
        updated_df = pd.concat([df_main, new_row_df], ignore_index=True)
        
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, data=updated_df)
        
        st.success("✅ Data saved successfully to Google Sheets!")
        st.balloons()
        
        # Reset state for next entry
        st.session_state.form_version += 1
        st.session_state.accumulated_downtime = timedelta(0)
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Error during save: {e}")

# --- 9. VIEW RECENT DATA ---
st.write("---")
st.subheader("📊 Recent Production Log (Last 5 Entries)")
if not df_main.empty:
    # Display the latest entries at the top of the table for easy viewing
    st.dataframe(df_main.sort_values(by='ProductionDate', ascending=False).head(5), use_container_width=True)
else:
    st.info("No data found in the spreadsheet.")