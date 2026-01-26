import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# 1. Page Config
st.set_page_config(layout="wide", page_title="Digital Printing Production 2026")

# --- CONFIGURATION ---
# Use the full URL of your Google Sheet
SHEET_URL = "https://docs.google.com/spreadsheets/d/1RmdsVRdN8Es6d9rAZVt8mUOLQyuz0tnHd8rkiXKVlTM/edit#gid=0"
TAB_NAME = "Data"
FORM_TITLE = "Digital Printing Production Data Entry (2026)"

ALL_COLUMNS = [
    'ProductionDate', 'NoOfJobs', 'NoOfTrials', 'DailyProductionTotal',
    'WeeklyProductionTotal', 'MonthlyProductionTotal', 'YearlyProductionTotal',
    'YTD_Jobs_Total', 'CleanMachineAm', 'CleanMachinePm', 'CleanMachineTotal',
    'IssueResolutionTotal', 'ProductionIssues_1', 'ProductionIssues_2',
    'ProductionIssues_3', 'ProductionIssues_4', 'ProductionIssues_5',
    'ProductionIssues_6', 'ProductionIssues_7', 'ProductionIssues_8',
    'ProductionIssues_9', 'ProductionIssues_10'
]

ISSUE_CATEGORIES = [
    "NoIssue", "Adjust voltage", "Air pipe burst", "Barcode scans", 
    "Clean rollers", "L/Shedding", "UV lamp issues", "Web tension error"
]

# --- 2. INITIALIZE CONNECTION ---
# This looks for secrets in .streamlit/secrets.toml (local) 
# or the Secrets settings (Streamlit Cloud)
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. HELPER FUNCTIONS ---
def load_data():
    try:
        return conn.read(spreadsheet=SHEET_URL, worksheet=TAB_NAME, ttl=0)
    except Exception:
        return pd.DataFrame(columns=ALL_COLUMNS)

# --- 4. UI LOGIC ---
st.title(f"🔍 {FORM_TITLE}")

df_main = load_data()

# Optional: simple password protection if you're worried about public access
# password = st.sidebar.text_input("Enter Access Password", type="password")
# if password == "YourPassword123": # Change this to your desired password

with st.form("entry_form", clear_on_submit=True):
    st.subheader("Daily Production Metrics")
    col1, col2 = st.columns(2)
    
    with col1:
        prod_date = st.date_input("Production Date", datetime.now())
        jobs = st.number_input("Number of Jobs", min_value=0, step=1)
        trials = st.number_input("Number of Trials", min_value=0, step=1)
    
    with col2:
        clean_am = st.checkbox("Machine Cleaned (AM)")
        clean_pm = st.checkbox("Machine Cleaned (PM)")
        issue = st.selectbox("Primary Production Issue", ISSUE_CATEGORIES)

    submit = st.form_submit_button("Submit Data to Google Sheets")

    if submit:
        new_row_dict = {col: "" for col in ALL_COLUMNS}
        new_row_dict.update({
            'ProductionDate': prod_date.strftime('%Y-%m-%d'),
            'NoOfJobs': jobs,
            'NoOfTrials': trials,
            'CleanMachineAm': "Yes" if clean_am else "No",
            'CleanMachinePm': "Yes" if clean_pm else "No",
            'ProductionIssues_1': issue
        })
        
        try:
            # Re-fetch latest data to avoid overwriting others
            current_df = load_data()
            new_entry_df = pd.DataFrame([new_row_dict])
            updated_df = pd.concat([current_df, new_entry_df], ignore_index=True)
            
            conn.update(spreadsheet=SHEET_URL, worksheet=TAB_NAME, data=updated_df)
            
            st.success("🎉 Data successfully saved!")
            st.balloons()
            st.rerun()
            
        except Exception as e:
            st.error(f"Failed to save: {e}")

# --- 5. DISPLAY SECTION ---
st.write("---")
st.subheader("Recent Entries (Last 10)")

if not df_main.empty:
    st.dataframe(df_main.tail(10), use_container_width=True)
else:
    st.info("The spreadsheet is currently empty.")