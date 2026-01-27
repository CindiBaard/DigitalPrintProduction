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

# SSL Bypass for specific environments
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

ISSUE_CATEGORIES = ["NoIssue", "Adjust voltage", "Air pipe burst", "Barcode scans", "Clean rollers", "L/Shedding", "UV lamp issues", "Web tension error"]

# --- 4. SESSION STATE INITIALIZATION ---
if 'form_version' not in st.session_state:
    st.session_state.form_version = 0
if 'accumulated_downtime' not in st.session_state:
    st.session_state.accumulated_downtime = timedelta(0)
if 'timer_start_time' not in st.session_state:
    st.session_state.timer_start_time = None
if 'is_timer_running' not in st.session_state:
    st.session_state.is_timer_running = False

# --- 5. DATA LOADING & CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        data = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, ttl=0)
        if data is not None and not data.empty:
            data['ProductionDate'] = pd.to_datetime(data['ProductionDate'], errors='coerce')
            numeric_cols = ['NoOfJobs', 'DailyProductionTotal', 'YearlyProductionTotal', 'YTD_Jobs_Total']
            for col in numeric_cols:
                if col in data.columns:
                    data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)
            return data.dropna(subset=['ProductionDate'])
        return pd.DataFrame(columns=ALL_COLUMNS)
    except Exception as e:
        st.error(f"🚨 Connection Failed: {e}")
        return pd.DataFrame(columns=ALL_COLUMNS)

df_main = load_data()

# --- 6. CALCULATIONS & METRICS ---
def calculate_ytd_metrics(selected_date, historical_df):
    if historical_df.empty: return 0, 0
    sel_dt = pd.to_datetime(selected_date).normalize()
    year_start = pd.to_datetime(f"{sel_dt.year}-01-01")
    ytd_mask = (historical_df['ProductionDate'] >= year_start) & (historical_df['ProductionDate'] < sel_dt)
    return int(historical_df.loc[ytd_mask, 'DailyProductionTotal'].sum()), int(historical_df.loc[ytd_mask, 'NoOfJobs'].sum())

current_year = datetime.now().year
ytd_val = df_main[df_main['ProductionDate'].dt.year == current_year]['DailyProductionTotal'].sum() if not df_main.empty else 0

# --- 7. UI: HEADER & COMPARATIVE GRAPHS ---
st.title(FORM_TITLE)
st.metric(f"📈 {current_year} Year-to-Date Total", f"{ytd_val:,.0f}")

st.write("---")
st.subheader("📊 Monthly Production Comparison: 2024, 2025 & 2026")

if not df_main.empty and PLOTLY_AVAILABLE:
    df_chart = df_main.copy()
    df_chart['Year'] = df_chart['ProductionDate'].dt.year.astype(str)
    df_chart['MonthNum'] = df_chart['ProductionDate'].dt.month
    df_chart['Month'] = df_chart['ProductionDate'].dt.strftime('%b')

    compare_df = df_chart[df_chart['Year'].isin(['2024', '2025', '2026'])]
    
    if not compare_df.empty:
        monthly_data = compare_df.groupby(['Year', 'MonthNum', 'Month'])['DailyProductionTotal'].sum().reset_index()
        monthly_data = monthly_data.sort_values('MonthNum')
        fig = px.line(monthly_data, x='Month', y='DailyProductionTotal', color='Year', markers=True)
        st.plotly_chart(fig, use_container_width=True)

# --- 8. TIMER UI ---
st.write("---")
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
t_col3.metric("Current Downtime Session", formatted_downtime)

# --- 9. ENTRY FORM ---
st.write("---")
v = st.session_state.form_version
prod_date = st.date_input("Production Date", value=datetime.now().date(), key=f"date_{v}")

prev_ytd_prod, prev_ytd_jobs = calculate_ytd_metrics(prod_date, df_main)
date_exists = pd.to_datetime(prod_date).normalize() in df_main['ProductionDate'].values if not df_main.empty else False

with st.form("main_form", clear_on_submit=True):
    st.subheader("📝 New Daily Entry Details")
    m1, m2, m3 = st.columns(3)
    jobs_today = m1.number_input("Jobs Today", min_value=0, step=1, key=f"jobs_{v}")
    prod_today = m2.number_input("Production Total", min_value=0, step=100, key=f"prod_{v}")
    trials_today = m3.number_input("Trials Today", min_value=0, step=1, key=f"trials_{v}")
    
    st.write("---")
    c1, c2 = st.columns(2)
    am_mins = c1.number_input("AM Clean (Mins)", value=45, key=f"am_{v}")
    pm_mins = c1.number_input("PM Clean (Mins)", value=45, key=f"pm_{v}")
    selected_issues = c2.multiselect("Production Issues:", options=ISSUE_CATEGORIES, default=["NoIssue"], key=f"issues_{v}")
    
    submitted = st.form_submit_button("Submit Data", disabled=date_exists)

if submitted and not date_exists:
    try:
        entry = {col: "" for col in ALL_COLUMNS}
        issues_to_save = selected_issues if selected_issues else ["NoIssue"]
        issue_dict = {f'ProductionIssues_{i+1}': issues_to_save[i] if i < len(issues_to_save) else "NoIssue" for i in range(10)}

        entry.update({
            'ProductionDate': prod_date.strftime('%Y-%m-%d'),
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
        updated_df = pd.concat([df_main, new_row_df], ignore_index=True)
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, data=updated_df)
        
        st.success("✅ Data saved successfully!")
        st.session_state.form_version += 1
        st.session_state.accumulated_downtime = timedelta(0) 
        st.rerun()
    except Exception as e:
        st.error(f"❌ Save Error: {e}")

# --- 10. MANAGEMENT & DELETE ---
st.write("---")
st.subheader("📋 Recent Records")
if not df_main.empty:
    st.dataframe(df_main.sort_values('ProductionDate', ascending=False).head(10), use_container_width=True)
    
    if st.button("🗑️ Delete Last Entry"):
        # Correctly removing the last record and syncing with GSheets
        updated_df = df_main.iloc[:-1]
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, data=updated_df)
        st.warning("Last row deleted successfully.")
        st.rerun()