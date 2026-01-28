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

# --- 8. ANALYTICS CHARTS (STACKED VERTICALLY) ---
st.write("---")
if not df_main.empty and PLOTLY_AVAILABLE:
    month_names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    years = ['2024', '2025', '2026']
    template = pd.DataFrame([(y, m+1, month_names[m]) for y in years for m in range(12)], 
                            columns=['Year', 'MonthNum', 'Month'])

    chart_df = df_main.copy()
    chart_df['Year'] = chart_df['ProductionDate_Parsed'].dt.year.astype(str)
    chart_df['MonthNum'] = chart_df['ProductionDate_Parsed'].dt.month
    compare_df = chart_df[chart_df['Year'].isin(years)].copy()
    
    # Chart 1: Production Comparison (TOP)
    st.subheader("📊 Monthly Production Comparison")
    prod_data = compare_df.groupby(['Year', 'MonthNum'])['DailyProductionTotal'].sum().reset_index()
    full_prod_data = pd.merge(template, prod_data, on=['Year', 'MonthNum'], how='left').fillna(0)
    
    fig_prod = px.bar(
        full_prod_data, x='Month', y='DailyProductionTotal', color='Year',
        barmode='group', height=500, text_auto='.3s',
        color_discrete_map={'2024': '#636EFA', '2025': '#EF553B', '2026': '#00CC96'},
        category_orders={"Month": month_names}
    )
    fig_prod.add_hline(y=ANNUAL_TARGET/12, line_dash="dot", line_color="white", annotation_text="Target Pace")
    fig_prod.update_traces(textposition='outside')
    st.plotly_chart(fig_prod, use_container_width=True)

    # Chart 2: Trial Comparison (UNDERNEATH)
    st.subheader("🧪 Monthly Trial Comparison")
    trial_data = compare_df.groupby(['Year', 'MonthNum'])['NoOfTrials'].sum().reset_index()
    full_trial_data = pd.merge(template, trial_data, on=['Year', 'MonthNum'], how='left').fillna(0)
    
    fig_trial = px.bar(
        full_trial_data, x='Month', y='NoOfTrials', color='Year',
        barmode='group', height=400, text_auto=True,
        color_discrete_map={'2024': '#636EFA', '2025': '#EF553B', '2026': '#00CC96'},
        category_orders={"Month": month_names}
    )
    fig_trial.update_traces(textposition='outside')
    st.plotly_chart(fig_trial, use_container_width=True)

# --- 9. TIMER & ENTRY FORM ---
st.write("---")
t_col, f_col = st.columns([1, 2])

with t_col:
    st.subheader("⏱️ Downtime Tracker")
    if not st.session_state.is_timer_running:
        if st.button("▶️ Start Timer"):
            st.session_state.timer_start_time = datetime.now()
            st.session_state.is_timer_running = True
            st.rerun()
    else:
        if st.button("⏹️ Stop Timer"):
            st.session_state.accumulated_downtime += (datetime.now() - st.session_state.timer_start_time)
            st.session_state.is_timer_running = False
            st.rerun()
    
    current_session = (datetime.now() - st.session_state.timer_start_time) if st.session_state.is_timer_running else timedelta(0)
    total_downtime_val = st.session_state.accumulated_downtime + current_session
    formatted_downtime = str(total_downtime_val).split('.')[0]
    st.metric("Total Session Downtime", formatted_downtime)

with f_col:
    v = st.session_state.form_version
    prod_date = st.date_input("Production Date", value=datetime.now().date(), key=f"date_{v}")
    
    is_duplicate = False
    if not df_main.empty:
        is_duplicate = (df_main['ProductionDate_Parsed'].dt.date == prod_date).any()
    
    if is_duplicate:
        st.warning(f"Note: Entry for {prod_date} already exists.")

    with st.form("main_form", clear_on_submit=True):
        st.subheader("📝 Daily Entry")
        m1, m2, m3 = st.columns(3)
        jobs_today = m1.number_input("Jobs Today", min_value=0, step=1)
        prod_today = m2.number_input("Production Total", min_value=0, step=100)
        trials_today = m3.number_input("Trials Today", min_value=0, step=1)
        
        selected_issues = st.multiselect("Issues:", options=ISSUE_CATEGORIES, default=["NoIssue"])
        submitted = st.form_submit_button("Submit Data", disabled=is_duplicate)

if submitted and not is_duplicate:
    try:
        # Preparation for GSHEETS update
        entry = {col: 0 if "Total" in col or "NoOf" in col else "" for col in ALL_COLUMNS}
        issues_to_save = selected_issues if selected_issues else ["NoIssue"]
        issue_dict = {f'ProductionIssues_{i+1}': issues_to_save[i] if i < len(issues_to_save) else "NoIssue" for i in range(10)}
        entry.update({
            'ProductionDate': prod_date.strftime('%m/%d/%Y'),
            'NoOfJobs': jobs_today, 'NoOfTrials': trials_today,
            'DailyProductionTotal': prod_today,
            'YearlyProductionTotal': prev_ytd_prod + prod_today, 
            'YTD_Jobs_Total': prev_ytd_jobs + jobs_today,
            'CleanMachineTotal': "90 mins",
            'IssueResolutionTotal': formatted_downtime,
            'TempDate': prod_date.strftime('%Y-%m-%d'),
            prod_date.strftime('%A'): 1
        })
        entry.update(issue_dict)
        new_row_df = pd.DataFrame([entry])[ALL_COLUMNS]
        final_df = pd.concat([df_main.drop(columns=['ProductionDate_Parsed'], errors='ignore'), new_row_df], ignore_index=True).fillna("")
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, data=final_df)
        st.success("✅ Data saved!")
        st.session_state.form_version += 1
        st.session_state.accumulated_downtime = timedelta(0) 
        st.rerun()
    except Exception as e:
        st.error(f"❌ Save Error: {e}")

# --- 10. HISTORY ---
st.write("---")
st.subheader("📋 Recent Records")
if not df_main.empty:
    st.dataframe(df_main.sort_values('ProductionDate_Parsed', ascending=False).head(5), use_container_width=True)