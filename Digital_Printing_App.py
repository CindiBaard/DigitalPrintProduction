import streamlit as st
import pandas as pd
import numpy as np
from streamlit_gsheets import GSheetsConnection
from datetime import timedelta, datetime
import ssl
import urllib.parse  # Added for WhatsApp URL encoding

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
        except (ValueError, TypeError):
            continue
    return total_td

# Annual Totals
total_2024, total_2025, ytd_2026, ytd_trials_2026 = 0, 0, 0, 0
ytd_downtime_2026 = timedelta(0)

if not df_main.empty:
    total_2024 = pd.to_numeric(df_main[df_main['ProductionDate_Parsed'].dt.year == 2024]['DailyProductionTotal'], errors='coerce').sum()
    total_2025 = pd.to_numeric(df_main[df_main['ProductionDate_Parsed'].dt.year == 2025]['DailyProductionTotal'], errors='coerce').sum()
    ytd_2026 = pd.to_numeric(df_main[df_main['ProductionDate_Parsed'].dt.year == 2026]['DailyProductionTotal'], errors='coerce').sum()
    ytd_trials_2026 = pd.to_numeric(df_main[df_main['ProductionDate_Parsed'].dt.year == 2026]['NoOfTrials'], errors='coerce').sum()
    ytd_downtime_2026 = calculate_ytd_downtime(df_main)

# --- 7. UI: HEADER & METRICS ---
st.title(FORM_TITLE)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("📊 2024 Total", f"{total_2024:,.0f}")
col2.metric("📊 2025 Total", f"{total_2025:,.0f}")

progress = (ytd_2026 / ANNUAL_TARGET) * 100 if ANNUAL_TARGET > 0 else 0
col3.metric("📈 2026 YTD Production", f"{ytd_2026:,.0f}", delta=f"{progress:.1f}% Target")
col4.metric("🧪 2026 YTD Trials", f"{int(ytd_trials_2026)}")

total_seconds = int(ytd_downtime_2026.total_seconds())
hours, minutes = total_seconds // 3600, (total_seconds % 3600) // 60
col5.metric("⏱️ 2026 YTD Downtime", f"{hours}h {minutes}m")

# --- NEW: 2026 PRODUCTION CHART ---
st.write("---")
if PLOTLY_AVAILABLE and not df_main.empty:
    chart_df = df_main[df_main['ProductionDate_Parsed'].dt.year == 2026].copy()
    chart_df['DailyProductionTotal'] = pd.to_numeric(chart_df['DailyProductionTotal'], errors='coerce').fillna(0)
    chart_df = chart_df.sort_values('ProductionDate_Parsed')

    if not chart_df.empty:
        fig = px.line(
            chart_df, 
            x='ProductionDate_Parsed', 
            y='DailyProductionTotal',
            title='2026 Daily Production Performance',
            labels={'ProductionDate_Parsed': 'Date', 'DailyProductionTotal': 'Meters Produced'},
            markers=True
        )
        fig.update_traces(line_color='#0083B8')
        fig.add_hline(y=ANNUAL_TARGET/365, line_dash="dash", line_color="red", annotation_text="Daily Avg Target")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No 2026 data available yet to display chart.")
else:
    st.info("Chart will appear here once 2026 data is recorded.")

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
        st.session_state.accumulated_downtime += (datetime.now() - st.session_state.timer_start_time)
        st.session_state.is_timer_running = False
        st.rerun()

current_session = (datetime.now() - st.session_state.timer_start_time) if st.session_state.is_timer_running else timedelta(0)
total_downtime_val = st.session_state.accumulated_downtime + current_session
formatted_downtime = str(total_downtime_val).split('.')[0]
t_col3.metric("Current Session", formatted_downtime)

# --- 9. ENTRY FORM ---
st.write("---")
v = st.session_state.form_version
prod_date = st.date_input("Production Date", value=datetime.now().date(), key=f"date_{v}")

# CHECK FOR DUPLICATES
is_duplicate = False
if not df_main.empty:
    is_duplicate = (df_main['ProductionDate_Parsed'].dt.date == prod_date).any()

if is_duplicate:
    st.error(f"⚠️ An entry for {prod_date} already exists. Use the 'Edit/Delete' section below to modify it.")

prev_ytd_prod, prev_ytd_jobs, prev_ytd_trials = calculate_ytd_metrics(prod_date, df_main)

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
    
    # Disable button if duplicate exists
    submitted = st.form_submit_button("Submit Data", disabled=is_duplicate)

if submitted and not is_duplicate:
    try:
        entry = {col: 0 if "Total" in col or "NoOf" in col else "" for col in ALL_COLUMNS}
        issues_to_save = selected_issues if selected_issues else ["NoIssue"]
        issue_dict = {f'ProductionIssues_{i+1}': issues_to_save[i] if i < len(issues_to_save) else "NoIssue" for i in range(10)}

        entry.update({
            'ProductionDate': prod_date.strftime('%m/%d/%Y'),
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
        save_df = pd.concat([df_main.drop(columns=['ProductionDate_Parsed'], errors='ignore'), new_row_df], ignore_index=True).fillna("")
        
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, data=save_df)
        st.success("✅ Data saved successfully!")
        st.session_state.form_version += 1
        st.session_state.accumulated_downtime = timedelta(0) 
        st.rerun()
    except Exception as e:
        st.error(f"❌ Save Error: {e}")

# --- 10. EDIT & DELETE MANAGEMENT ---
st.write("---")
st.subheader("🛠️ Edit or Delete Entries")
with st.expander("Click here to modify historical records"):
    st.info("💡 Double-click cells to edit. Select a row and press 'Delete' on your keyboard to remove it.")
    clean_df = df_main.drop(columns=['ProductionDate_Parsed'], errors='ignore')
    edited_data = st.data_editor(
        clean_df, 
        num_rows="dynamic", 
        use_container_width=True,
        key="data_editor_main"
    )
    save_changes = st.button("💾 Save Changes to Google Sheets")
    if save_changes:
        try:
            conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, data=edited_data.fillna(""))
            st.success("✅ Spreadsheet updated successfully!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Update Error: {e}")

# --- 11. RECENT VIEW ---
st.write("---")
st.subheader("📋 Recent Records (Read Only)")
if not df_main.empty:
    st.dataframe(df_main.sort_values('ProductionDate_Parsed', ascending=False).head(10), use_container_width=True)

# --- 12. EXPORT & SHARE ---
st.write("---")
st.subheader("📤 Export & Share Report")
col_share1, col_share2 = st.columns(2)

with col_share1:
    whatsapp_phone = st.text_input("Colleague's WhatsApp Number (include country code, e.g., 27...)", placeholder="27123456789")
    share_message = f"Hi, here is the Production Report for {datetime.now().strftime('%Y-%m-%d')}. Total Production: {ytd_2026:,.0f} meters."
    
    # Create WhatsApp link
    encoded_msg = urllib.parse.quote(share_message)
    wa_link = f"https://wa.me/{whatsapp_phone}?text={encoded_msg}"
    
    if st.button("🖨️ Step 1: Save Page as PDF"):
        # This triggers the browser's print dialog. User must select 'Save as PDF'.
        st.components.v1.html("<script>window.print();</script>", height=0)
        st.info("Please select 'Save as PDF' in the print dialog that just appeared.")

with col_share2:
    st.write("Click below after saving your PDF to notify your colleague:")
    if whatsapp_phone:
        # Corrected: Removed 'unsafe_allow_media_types' which caused the TypeError
        st.markdown(f'''
            <a href="{wa_link}" target="_blank">
                <button style="
                    background-color: #25D366;
                    color: white;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    font-weight: bold;">
                    📲 Step 2: Send WhatsApp Notification
                </button>
            </a>
            ''', unsafe_allow_html=True)
    else:
        st.warning("Enter a phone number to enable WhatsApp sharing.")