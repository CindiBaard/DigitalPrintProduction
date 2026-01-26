import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px # Better for comparative graphs
from streamlit_gsheets import GSheetsConnection
from datetime import timedelta, datetime
import ssl

# --- 1. CONFIGURATION ---
FORM_TITLE = "Digital Printing Production Data Entry (2026)"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1RmdsVRdN8Es6d9rAZVt8mUOLQyuz0tnHd8rkiXKVlTM/"
SHEET_NAME = "Data" 

st.set_page_config(layout="wide", page_title=FORM_TITLE)

# --- 2. DATA HELPERS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, ttl=0)
        if df is not None and not df.empty:
            df['ProductionDate'] = pd.to_datetime(df['ProductionDate'], errors='coerce')
            df['DailyProductionTotal'] = pd.to_numeric(df['DailyProductionTotal'], errors='coerce').fillna(0)
            return df.dropna(subset=['ProductionDate'])
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

df_main = load_data()

# --- 3. YEAR-TO-DATE (YTD) CALCULATIONS ---
current_year = datetime.now().year
ytd_total = 0
if not df_main.empty:
    ytd_total = df_main[df_main['ProductionDate'].dt.year == current_year]['DailyProductionTotal'].sum()

# --- 4. TOP METRICS BAR ---
st.title(FORM_TITLE)
m1, m2, m3 = st.columns(3)
m1.metric(f"Year to Date Total ({current_year})", f"{ytd_total:,.0f}")
# Add other metrics here as needed

# --- 5. COMPARATIVE GRAPHS (2024 vs 2025) ---
st.write("---")
st.subheader("📊 Production Comparison: 2024 vs 2025")

if not df_main.empty:
    # Prepare data for monthly comparison
    df_history = df_main.copy()
    df_history['Year'] = df_history['ProductionDate'].dt.year
    df_history['Month'] = df_history['ProductionDate'].dt.month_name()
    df_history['MonthNum'] = df_history['ProductionDate'].dt.month

    # Filter for 2024 and 2025
    compare_df = df_history[df_history['Year'].isin([2024, 2025])]
    
    if not compare_df.empty:
        monthly_comp = compare_df.groupby(['Year', 'Month', 'MonthNum'])['DailyProductionTotal'].sum().reset_index()
        monthly_comp = monthly_comp.sort_values('MonthNum')

        fig = px.bar(monthly_comp, x='Month', y='DailyProductionTotal', color='Year',
                     barmode='group', title="Monthly Production: 2024 vs 2025",
                     labels={'DailyProductionTotal': 'Total Production'},
                     color_discrete_map={2024: '#FFA07A', 2025: '#20B2AA'})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data found for 2024 or 2025 to generate comparison.")

# --- 6. ENTRY FORM ---
st.write("---")
with st.form("entry_form", clear_on_submit=True):
    st.subheader("New Production Entry")
    f1, f2, f3 = st.columns(3)
    p_date = f1.date_input("Date", datetime.now())
    p_jobs = f2.number_input("No of Jobs", min_value=0, step=1)
    p_prod = f3.number_input("Daily Production Total", min_value=0, step=1)
    
    submit = st.form_submit_button("Submit Data")

    if submit:
        # Create new row
        new_row = pd.DataFrame([{
            'ProductionDate': p_date.strftime('%Y-%m-%d'),
            'NoOfJobs': p_jobs,
            'DailyProductionTotal': p_prod
        }])
        
        # KEY: Combine existing data WITH new row to prevent wiping the sheet
        updated_df = pd.concat([df_main, new_row], ignore_index=True)
        
        try:
            conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, data=updated_df)
            st.success("Data Added Successfully!")
            st.rerun()
        except Exception as e:
            st.error(f"Save failed: {e}")

# --- 7. DELETE BUTTON ---
st.write("---")
st.subheader("Manage Data")
if not df_main.empty:
    st.write("Recent Records:")
    st.dataframe(df_main.tail(5), use_container_width=True)
    
    if st.button("🗑️ Delete Last Entry"):
        # Drop the last row of the current dataframe
        updated_df = df_main.iloc[:-1] 
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=SHEET_NAME, data=updated_df)
        st.warning("Last entry removed.")
        st.rerun()