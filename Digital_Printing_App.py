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

st.set_page_config(layout="wide", page_title=FORM_TITLE)

# SSL Bypass
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass

# --- 2. CONSTANTS & COLUMNS ---
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

# --- 3. SESSION STATE ---
if 'form_version' not in st.session_state: st.session_state.form_version = 0
if 'accumulated_downtime' not in st.session_state: st.session_state.accumulated_downtime = timedelta(0)
if 'timer_start_time' not in st.session_state: st.session_state.timer_start_time = None
if 'is_timer_running' not in st.session_state: st.session_state.is_timer_running = False

# --- 4. DATA LOADING ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # We read the raw data without dropping NA yet to maintain the full sheet structure
        data = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, ttl=0)
        if data is not None and not data.empty:
            data.columns = [c.strip() for c in data.columns]
            # Ensure the date column is usable for calculations
            data['ProductionDate_Parsed'] = pd.to_datetime(data['ProductionDate'], errors='coerce')
            return data
        return pd.DataFrame(columns=ALL_COLUMNS)
    except Exception as e:
        st.error(f"🚨 Connection Failed: {e}")
        return pd.DataFrame(columns=ALL_COLUMNS)

df_main = load_data()

# --- 5. CALCULATIONS ---
def calculate_ytd_metrics(selected_date, historical_df):
    if historical_df.empty: return 0, 0
    sel_dt = pd.to_datetime(selected_date).normalize()
    year_start = pd.to_datetime(f"{sel_dt.year}-01-01")
    # Use the parsed date column for filtering
    ytd_mask = (historical_df['ProductionDate_Parsed'] >= year_start) & (historical_df['ProductionDate_Parsed'] < sel_dt)
    prod = pd.to_numeric(historical_df.loc[ytd_mask, 'DailyProductionTotal'], errors='coerce').sum()
    jobs = pd.to_numeric(historical_df.loc[ytd_mask, 'NoOfJobs'], errors='coerce').sum()
    return int(prod), int(jobs)

# --- 6. TIMER LOGIC ---
st.subheader("⏱️ Issue Downtime Tracker")
t_col1, t_col2, t_col3 = st.columns([1, 1, 2])
if not st.session_state.is_timer_running:
    if t_col1.button("▶️ Start Timer"):
        st.session_state.timer_start_time = datetime.now()
        st.session_state.is_timer_running = True
        st.rerun()
else:
    if t_col1.button("⏹️ Stop Timer"):
        st.session_state.accumulated_downtime += (datetime.now() - st.session_state.timer_start_time)
        st.session_state.is_timer_running = False
        st.rerun()
current_session = (datetime.now() - st.session_state.timer_start_time) if st.session_state.is_timer_running else timedelta(0)
total_downtime_val = st.session_state.accumulated_downtime + current_session
formatted_downtime = str(total_downtime_val).split('.')[0]
t_col3.metric("Current Session", formatted_downtime)

# --- 7. ENTRY FORM ---
st.write("---")
v = st.session_state.form_version
prod_date = st.date_input("Production Date", value=datetime.now().date(), key=f"date_{v}")

prev_ytd_prod, prev_ytd_jobs = calculate_ytd_metrics(prod_date, df_main)

with st.form("main_form", clear_on_submit=True):
    st.subheader("📝 New Daily Entry Details")
    m1, m2, m3 = st.columns(3)
    jobs_today = m1.number_input("Jobs Today", min_value=0, step=1, key=f"jobs_{v}")
    prod_today = m2.number_input("Production Total", min_value=0, step=100, key=f"prod_{v}")
    trials_today = m3.number_input("Trials Today", min_value=0, step=1, key=f"trials_{v}")
    
    c1, c2 = st.columns(2)
    am_mins = c1.number_input("AM Clean (Mins)", value=45)
    pm_mins = c1.number_input("PM Clean (Mins)", value=45)
    selected_issues = c2.multiselect("Production Issues:", options=ISSUE_CATEGORIES, default=["NoIssue"])
    
    submitted = st.form_submit_button("Submit Data")

if submitted:
    try:
        # Create a dictionary with 0s or empty strings for ALL columns to avoid upload errors
        entry = {col: 0 if "Total" in col or "NoOf" in col else "" for col in ALL_COLUMNS}
        
        issues_to_save = selected_issues if selected_issues else ["NoIssue"]
        issue_dict = {f'ProductionIssues_{i+1}': issues_to_save[i] if i < len(issues_to_save) else "NoIssue" for i in range(10)}

        entry.update({
            'ProductionDate': prod_date.strftime('%m/%d/%Y'), # Matching your CSV format
            'NoOfJobs': jobs_today, 
            'NoOfTrials': trials_today,
            'DailyProductionTotal': prod_today,
            'YearlyProductionTotal': prev_ytd_prod + prod_today, 
            'YTD_Jobs_Total': prev_ytd_jobs + jobs_today,
            'CleanMachineAm': f"{am_mins} mins",
            'CleanMachinePm': f"{pm_mins} mins",
            'CleanMachineTotal': f"{am_mins + pm_mins} mins",
            'IssueResolutionTotal': formatted_downtime,
            'TempDate': prod_date.strftime('%Y-%m-%d'),
            prod_date.strftime('%A'): 1
        })
        entry.update(issue_dict)

        new_row_df = pd.DataFrame([entry])[ALL_COLUMNS]
        # Important: Fill NaN with appropriate values before sending to Google
        final_df = pd.concat([df_main.drop(columns=['ProductionDate_Parsed'], errors='ignore'), new_row_df], ignore_index=True).fillna("")
        
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, data=final_df)
        st.success("✅ Data saved successfully!")
        st.session_state.form_version += 1
        st.session_state.accumulated_downtime = timedelta(0) 
        st.rerun()
    except Exception as e:
        st.error(f"❌ Save Error: {e}")

# --- 8. MANAGEMENT & DELETE ---
st.write("---")
st.subheader("📋 Data Management")

if not df_main.empty:
    # Display newest first in the UI only
    st.dataframe(df_main.sort_values('ProductionDate_Parsed', ascending=False).head(10), use_container_width=True)
    
    m_col1, m_col2 = st.columns(2)
    
    # Download Backup
    csv = df_main.to_csv(index=False).encode('utf-8')
    m_col1.download_button("📥 Download CSV Backup", data=csv, file_name="backup.csv", mime='text/csv')
    
    with m_col2.expander("🗑️ Delete Recent Entry"):
        # Identify the most recent entry by the actual Date, not the list position
        latest_idx = df_main['ProductionDate_Parsed'].idxmax()
        latest_date = df_main.loc[latest_idx, 'ProductionDate']
        
        st.warning(f"This will delete the entry for: {latest_date}")
        confirm = st.checkbox("Confirm deletion of this specific row")
        
        if st.button("Execute Delete", disabled=not confirm):
            # Drop the specific row we found earlier
            updated_df = df_main.drop(index=latest_idx).drop(columns=['ProductionDate_Parsed'], errors='ignore').fillna("")
            conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, data=updated_df)
            st.success("Entry removed!")
            st.rerun()