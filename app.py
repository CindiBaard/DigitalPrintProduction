import streamlit as st
import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import calendar
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
import streamlit as st
from streamlit_gsheets import GSheetsConnection
from datetime import timedelta, datetime


# --- 1. CONFIGURATION & CONSTANTS ---
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(spreadsheet=url, ttl=3600)

# Using the clean URL without extra 'gid' parameters
df = conn.read(
    spreadsheet="https://docs.google.com/spreadsheets/d/1RmdsVRdN8Es6d9rAZVt8mUOLQyuz0tnHd8rkiXKVlTM/edit?gid=650172488#gid=650172488",
    worksheet="DigitalPrintingQuantities_FULLY_PREPARED"
 
)


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

# --- 2. SESSION STATE INITIALIZATION ---
if 'form_version' not in st.session_state:
    st.session_state.form_version = 0
if 'accumulated_downtime' not in st.session_state:
    st.session_state.accumulated_downtime = timedelta(0)
if 'timer_start_time' not in st.session_state:
    st.session_state.timer_start_time = None
if 'is_timer_running' not in st.session_state:
    st.session_state.is_timer_running = False

# --- 3. DATA HELPER FUNCTIONS ---
@st.cache_data
def load_data(path):
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path, sep=';', dtype=str)
        df['ProductionDate'] = pd.to_datetime(df['ProductionDate'], errors='coerce').dt.normalize()
        df = df.dropna(subset=['ProductionDate'])
        
        numeric_cols = ['NoOfJobs', 'DailyProductionTotal', 'YearlyProductionTotal', 'YTD_Jobs_Total']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"⚠️ Error loading CSV: {e}")
        return None

def calculate_ytd_metrics(selected_date, historical_df):
    if historical_df is None or historical_df.empty:
        return 0, 0
    sel_dt = pd.to_datetime(selected_date).normalize()
    year_start = pd.to_datetime(f"{sel_dt.year}-01-01")
    ytd_mask = (historical_df['ProductionDate'] >= year_start) & (historical_df['ProductionDate'] < sel_dt)
    return int(historical_df.loc[ytd_mask, 'DailyProductionTotal'].sum()), int(historical_df.loc[ytd_mask, 'NoOfJobs'].sum())

# --- 4. PAGE SETUP ---
st.set_page_config(layout="wide", page_title=FORM_TITLE)
st.title(FORM_TITLE)

df_main = load_data(FILE_PATH)

# --- 5. DOWNTIME TIMER UI ---
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

# --- 6. ENTRY FORM ---
st.write("---")
st.subheader("📊 2026 Production Data Entry")
v = st.session_state.form_version
prod_date = st.date_input("Production Date", value=datetime.now().date(), key=f"date_{v}")
target_dt = pd.to_datetime(prod_date).normalize()

prev_ytd_prod, prev_ytd_jobs = calculate_ytd_metrics(prod_date, df_main)
date_exists = False
if df_main is not None and not df_main.empty:
    date_exists = target_dt in df_main['ProductionDate'].values

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
        new_row = pd.DataFrame([entry])[ALL_COLUMNS]
        new_row.to_csv(FILE_PATH, mode='a', index=False, sep=';', header=not os.path.exists(FILE_PATH))
        st.session_state.form_version += 1
        st.session_state.accumulated_downtime = timedelta(0)
        st.session_state.is_timer_running = False
        st.cache_data.clear()
        st.success("✅ 2026 Entry Saved!")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Error: {e}")

# --- 7. ANALYTICS ---
if df_main is not None and not df_main.empty:
    df_plot = df_main.copy()
    df_plot['Year'] = df_plot['ProductionDate'].dt.year
    df_plot['Month'] = df_plot['ProductionDate'].dt.month

    # --- 7A. LOCKED HISTORICAL COMPARISON (2024 vs 2025) ---
    st.write("---")
    st.subheader("📈 Historical Benchmarks (2024 vs 2025)")
    
    stats_list = []
    for year in [2024, 2025]:
        mask = (df_plot['Year'] == year)
        stats_list.append({
            'Year': year,
            'Production': df_plot.loc[mask, 'DailyProductionTotal'].sum(),
            'Jobs': df_plot.loc[mask, 'NoOfJobs'].sum()
        })
    y_df = pd.DataFrame(stats_list)

    col_graphs, col_table = st.columns([3, 1])
    with col_graphs:
        fig_y, (ay1, ay2) = plt.subplots(1, 2, figsize=(12, 4))
        ay1.bar(y_df['Year'].astype(str), y_df['Production'], color=['#5DADE2', '#EC7063'])
        ay1.set_title("Total Production")
        ay2.bar(y_df['Year'].astype(str), y_df['Jobs'], color=['#5DADE2', '#EC7063'])
        ay2.set_title("Total Jobs")
        st.pyplot(fig_y)

    with col_table:
        p24, p25 = y_df.loc[y_df['Year']==2024, 'Production'].iloc[0], y_df.loc[y_df['Year']==2025, 'Production'].iloc[0]
        j24, j25 = y_df.loc[y_df['Year']==2024, 'Jobs'].iloc[0], y_df.loc[y_df['Year']==2025, 'Jobs'].iloc[0]
        st.table(pd.DataFrame({
            "Metric": ["Prod", "Jobs"],
            "2024": [f"{p24:,.0f}", f"{j24:,.0f}"],
            "2025": [f"{p25:,.0f}", f"{j25:,.0f}"],
            "Growth": [f"{((p25-p24)/p24*100):.1f}%" if p24 > 0 else "N/A", f"{((j25-j24)/j24*100):.1f}%" if j24 > 0 else "N/A"]
        }))

    # --- 7B. UPDATED: 2026 DAILY PRODUCTION TRACKER ---
    st.write("---")
    st.subheader("📅 2026 Daily Production Totals")
    
    df_2026 = df_plot[df_plot['Year'] == 2026].sort_values('ProductionDate')
    
    if not df_2026.empty:
        c1, c2, c3 = st.columns(3)
        total_26 = df_2026['DailyProductionTotal'].sum()
        avg_26 = df_2026['DailyProductionTotal'].mean()
        
        # Projection Logic
        days_passed = (datetime.now() - datetime(2026, 1, 1)).days + 1
        projected = (total_26 / days_passed) * 365
        
        c1.metric("2026 YTD Total", f"{total_26:,.0f}")
        c2.metric("2026 Daily Average", f"{avg_26:,.0f}")
        c3.metric("2026 Projection", f"{projected:,.0f}", delta=f"{projected - p25:,.0f} vs 2025")

        # Daily Bar Chart
        fig_d, ax_d = plt.subplots(figsize=(14, 5))
        bars = ax_d.bar(df_2026['ProductionDate'].dt.strftime('%d-%b'), df_2026['DailyProductionTotal'], color='#27AE60')
        ax_d.bar_label(bars, fmt='{:,.0f}', padding=3, fontsize=8, rotation=90)
        ax_d.set_title("2026 Production by Day")
        ax_d.set_ylabel("Quantity")
        plt.xticks(rotation=45)
        st.pyplot(fig_d)
    else:
        st.info("No data entries for 2026 yet.")

    # --- 7C. MONTHLY TREND (2024 vs 2025) ---
    st.write("---")
    st.subheader("📅 Monthly Comparison (Historical)")
    m_names = [calendar.month_name[m][:3] for m in range(1, 13)]
    df_m = df_plot[df_plot['Year'].isin([2024, 2025])].groupby(['Year', 'Month']).agg({'DailyProductionTotal': 'sum', 'NoOfJobs': 'sum'}).reset_index()

    def get_mv(year, col):
        data = df_m[df_m['Year'] == year]
        return [data[data['Month'] == m][col].sum() if m in data['Month'].values else 0 for m in range(1, 13)]

    p24_m, p25_m = get_mv(2024, 'DailyProductionTotal'), get_mv(2025, 'DailyProductionTotal')
    fig_m, ax_m = plt.subplots(figsize=(14, 4))
    idx = np.arange(12)
    ax_m.bar(idx - 0.17, p24_m, 0.35, label='2024', color='#5DADE2')
    ax_m.bar(idx + 0.17, p25_m, 0.35, label='2025', color='#EC7063')
    ax_m.set_xticks(idx); ax_m.set_xticklabels(m_names); ax_m.legend(); ax_m.set_title("Monthly Production (24 vs 25)")
    st.pyplot(fig_m)

# --- 8. DELETE TOOL ---
st.write("---")
st.subheader("🗑️ Record Management")
if df_main is not None and not df_main.empty:
    with st.expander("Delete an Entry"):
        dates = sorted(df_main['ProductionDate'].dt.date.unique(), reverse=True)
        to_del = st.selectbox("Select Date to Delete", options=dates, key=f"del_sel_{v}")
        if st.button("Confirm DELETE", type="primary"):
            updated = df_main[df_main['ProductionDate'].dt.date != to_del]
            updated.to_csv(FILE_PATH, index=False, sep=';')
            st.cache_data.clear()
            st.success(f"Record for {to_del} removed.")
            st.rerun()

# --- 9. VIEW DATA ---
st.write("---")
if df_main is not None:
    st.dataframe(df_main.sort_values(by='ProductionDate', ascending=False).head(10))
