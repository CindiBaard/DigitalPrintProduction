import streamlit as st
import pandas as pd
import plotly.express as px  # This is the correct way to import Plotly
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# --- 1. CONFIG & PAGE SETUP ---
# These must be at the very top to prevent the "MustBeFirst" error
FORM_TITLE = "Digital Printing Production Data Entry (2026)"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1RmdsVRdN8Es6d9rAZVt8mUOLQyuz0tnHd8rkiXKVlTM/"
SHEET_NAME = "Data" 

st.set_page_config(layout="wide", page_title=FORM_TITLE)

# --- 2. OPTIONAL LIBRARIES (Safety Check) ---
try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# --- 3. DATA LOADING ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, ttl=0)
        if df is not None and not df.empty:
            df['ProductionDate'] = pd.to_datetime(df['ProductionDate'], errors='coerce')
            for col in ['DailyProductionTotal', 'NoOfJobs']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df.dropna(subset=['ProductionDate'])
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return pd.DataFrame()

df_main = load_data()

# --- 4. YTD CALCULATIONS ---
current_year = datetime.now().year
ytd_total = 0
if not df_main.empty:
    ytd_total = df_main[df_main['ProductionDate'].dt.year == current_year]['DailyProductionTotal'].sum()

# --- 5. TOP METRICS & COMPARISON GRAPH ---
st.title(FORM_TITLE)
st.metric(f"📈 {current_year} Year-to-Date Production Total", f"{ytd_total:,.0f}")

st.write("---")
st.subheader("📊 Monthly Comparison: 2024 vs 2025")

if not df_main.empty and PLOTLY_AVAILABLE:
    df_chart = df_main.copy()
    df_chart['Year'] = df_chart['ProductionDate'].dt.year
    df_chart['Month'] = df_chart['ProductionDate'].dt.strftime('%b')
    df_chart['MonthNum'] = df_chart['ProductionDate'].dt.month

    compare_df = df_chart[df_chart['Year'].isin([2024, 2025])]
    
    if not compare_df.empty:
        monthly_data = compare_df.groupby(['Year', 'Month', 'MonthNum'])['DailyProductionTotal'].sum().reset_index()
        monthly_data = monthly_data.sort_values('MonthNum')

        fig = px.bar(monthly_data, x='Month', y='DailyProductionTotal', color='Year',
                     barmode='group', 
                     color_discrete_map={2024: '#636EFA', 2025: '#EF553B'},
                     labels={'DailyProductionTotal': 'Production Volume'})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data found for 2024 or 2025 in the 'ProductionDate' column.")
elif not PLOTLY_AVAILABLE:
    st.warning("Graphing module (Plotly) not installed. Please check requirements.txt.")

# --- 6. ENTRY FORM ---
st.write("---")
with st.form("entry_form", clear_on_submit=True):
    st.subheader("📝 New Daily Entry")
    col1, col2, col3 = st.columns(3)
    entry_date = col1.date_input("Production Date", datetime.now())
    entry_jobs = col2.number_input("Number of Jobs", min_value=0)
    entry_prod = col3.number_input("Production Total", min_value=0)
    
    submitted = st.form_submit_button("Add Record to Sheets")

if submitted:
    new_entry = pd.DataFrame([{
        'ProductionDate': entry_date.strftime('%Y-%m-%d'),
        'NoOfJobs': entry_jobs,
        'DailyProductionTotal': entry_prod
    }])
    
    # Logic: Append new entry to the end of the existing dataframe
    final_df = pd.concat([df_main, new_entry], ignore_index=True)
    
    try:
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, data=final_df)
        st.success("Record Saved!")
        st.rerun()
    except Exception as e:
        st.error(f"Failed to save: {e}")

# --- 7. DELETE & RECENT VIEW ---
st.write("---")
st.subheader("📋 Recent Entries & Management")
if not df_main.empty:
    st.dataframe(df_main.sort_values('ProductionDate', ascending=False).head(10), use_container_width=True)
    
    if st.button("🗑️ Delete Last Entry"):
        # Logic: Remove the last row and update the whole sheet
        final_df = df_main.iloc[:-1]
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, data=final_df)
        st.warning("Last row deleted from Google Sheets.")
        st.rerun()