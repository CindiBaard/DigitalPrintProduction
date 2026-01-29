Python
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

# --- 2. PLOTLY CHECK ---
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
            # Ensure production values are numeric for plotting
            data['DailyProductionTotal'] = pd.to_numeric(data['DailyProductionTotal'], errors='coerce').fillna(0)
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
    
    prod = historical_df.loc[ytd_mask, 'DailyProductionTotal'].sum()
    jobs = pd.to_numeric(historical_df.loc[ytd_mask, 'NoOfJobs'], errors='coerce').sum()
    trials = pd.to_numeric(historical_df.loc[ytd_mask, 'NoOfTrials'], errors='coerce').sum()
    return int(prod), int(jobs), int(trials)

def calculate_ytd_downtime(historical_df):
    if historical_df.empty: return timedelta(0)
    ytd_mask = historical_df['ProductionDate_Parsed'].dt.year == 2026
    downtime_series = historical_df.loc[ytd_mask, 'IssueResolutionTotal']
    total_td = timedelta(0)
    for val in downtime_series.dropna():
        try:
            time_parts = str(val).split(':')
            if len(time_parts) == 3:
                h, m, s = map(int, time_parts)
                total_td += timedelta(hours=h, minutes=m, seconds=s)
            elif len(time_parts) == 2:
                m, s = map(int, time_parts)
                total_td += timedelta(minutes=m, seconds=s)
        except (ValueError, TypeError): continue
    return total_td

# --- 7. UI: HEADER & METRICS ---
st.title(FORM_TITLE)

if not df_main.empty:
    ytd_2026 = df_main[df_main['ProductionDate_Parsed'].dt.year == 2026]['DailyProductionTotal'].sum()
    ytd_trials_2026 = pd.to_numeric(df_main[df_main['ProductionDate_Parsed'].dt.year == 2026]['NoOfTrials'], errors='coerce').sum()
    ytd_downtime_2026 = calculate_ytd_downtime(df_main)
    
    col1, col2, col3, col4 = st.columns(4)
    progress = (ytd_2026 / ANNUAL_TARGET) * 100 if ANNUAL_TARGET > 0 else 0
    col1.metric("📈 2026 YTD Production", f"{ytd_2026:,.0f}")
    col2.metric("🎯 Target Progress", f"{progress:.1f}%")
    col3.metric("🧪 YTD Trials", f"{int(ytd_trials_2026)}")
    
    td_sec = int(ytd_downtime_2026.total_seconds())
    col4.metric("⏱️ YTD Downtime", f"{td_sec // 3600}h {(td_sec % 3600) // 60}m")

# --- 8. VISUALIZATION (THE PLOT) ---
st.write("---")
st.subheader("📊 Production Trends")
if PLOTLY_AVAILABLE and not df_main.empty:
    # Filter for 2026 data and sort by date
    plot_df = df_main[df_main['ProductionDate_Parsed'].dt.year == 2026].sort_values('ProductionDate_Parsed')
    
    if not plot_df.empty:
        fig = px.line(plot_df, x='ProductionDate_Parsed', y='DailyProductionTotal',
                      title='Daily Production Total (2026)',
                      labels={'ProductionDate_Parsed': 'Date', 'DailyProductionTotal': 'Total Printed'},
                      markers=True, line_shape='spline')
        fig.update_traces(line_color='#00CC96', marker_size=8)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available for 2026 yet to plot.")
else:
    st.warning("Plotly not installed or data empty.")

# --- 9. TIMER & ENTRY FORM ---
st.write("---")
# (Timer code remains same as your snippet)
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

st.write("---")
v = st.session_state.form_version
prod_date = st.date_input("Production Date", value=datetime.now().date(), key=f"date_{v}")

is_duplicate = False
if not df_main.empty:
    is_duplicate = (df_main['ProductionDate_Parsed'].dt.date == prod_date).any()

if is_duplicate:
    st.error(f"⚠️ An entry for {prod_date} already exists.")

prev_ytd_prod, prev_ytd_jobs, prev_ytd_trials = calculate_ytd_metrics(prod_date, df_main)

with st.form("main_form", clear_on_submit=True):
    st.subheader("📝 New Daily Entry")
    m1, m2, m3 = st.columns(3)
    jobs_today = m1.number_input("Jobs Today", min_value=0, step=1, key=f"jobs_{v}")
    prod_today = m2.number_input("Production Total", min_value=0, step=100, key=f"prod_{v}")
    trials_today = m3.number_input("Trials Today", min_value=0, step=1, key=f"trials_{v}")
    
    c1, c2 = st.columns(2)
    am_mins = c1.number_input("AM Clean (Mins)", value=45)
    pm_mins = c1.number_input("PM Clean (Mins)", value=45)
    selected_issues = c2.multiselect("Production Issues:", options=ISSUE_CATEGORIES, default=["NoIssue"])
    
    submitted = st.form_submit_button("Submit Data", disabled=is_duplicate)

if submitted and not is_duplicate:
    try:
        entry = {col: 0 if "Total" in col or "NoOf" in col else "" for col in ALL_COLUMNS}
        issues_to_save = selected_issues if selected_issues else ["NoIssue"]
        issue_dict = {f'ProductionIssues_{i+1}': issues_to_save[i] if i < len(issues_to_save) else "NoIssue" for i in range(10)}

        entry.update({
            'ProductionDate': prod_date.strftime('%m/%d/%Y'),
            'NoOfJobs': jobs_today, 'NoOfTrials': trials_today,
            'DailyProductionTotal': prod_today,
            'YearlyProductionTotal': prev_ytd_prod + prod_today, 
            'YTD_Jobs_Total': prev_ytd_jobs + jobs_today,
            'CleanMachineAm': f"{am_mins} mins", 'CleanMachinePm': f"{pm_mins} mins",
            'CleanMachineTotal': f"{am_mins + pm_mins} mins",
            'IssueResolutionTotal': formatted_downtime,
            'TempDate': prod_date.strftime('%Y-%m-%d'),
            prod_date.strftime('%A'): 1
        })
        entry.update(issue_dict)
        final_df = pd.concat([df_main.drop(columns=['ProductionDate_Parsed'], errors='ignore'), pd.DataFrame([entry])[ALL_COLUMNS]], ignore_index=True).fillna("")
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, data=final_df)
        st.success("✅ Saved!")
        st.session_state.form_version += 1
        st.session_state.accumulated_downtime = timedelta(0) 
        st.rerun()
    except Exception as e: st.error(f"❌ Error: {e}")

# --- 10. EDIT & DELETE MANAGEMENT ---
st.write("---")
st.subheader("🛠️ Edit or Delete Entries")
with st.expander("Modify Historical Records"):
    if not df_main.empty:
        clean_df = df_main.drop(columns=['ProductionDate_Parsed'], errors='ignore')
        edited_data = st.data_editor(clean_df, num_rows="dynamic", use_container_width=True, key="main_editor")
        
        if st.button("💾 Save All Changes"):
            try:
                conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, data=edited_data.fillna(""))
                st.success("Spreadsheet updated!")
                st.rerun()
            except Exception as e: st.error(f"Update Failed: {e}")