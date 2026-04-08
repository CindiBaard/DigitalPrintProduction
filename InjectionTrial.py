import streamlit as st
import pandas as pd
from datetime import datetime
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Injection Trial Data Entry")

# --- DIRECTORY SETUP ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILENAME_PARQUET = os.path.join(BASE_DIR, "ProjectTracker_Combined.parquet")
SUBMISSIONS_FILE = os.path.join(BASE_DIR, "Trial_Submissions.parquet")

# --- HELPER FUNCTIONS ---

def get_project_data(pre_prod_no):
    """Searches the combined parquet file for the Pre-Prod number."""
    if not os.path.exists(FILENAME_PARQUET):
        st.error(f"Database file not found at: {FILENAME_PARQUET}")
        return None

    try:
        df_tracker = pd.read_parquet(FILENAME_PARQUET)
        col_name = "Pre-Prod No." 
        
        if col_name not in df_tracker.columns:
            st.error(f"Column '{col_name}' not found.")
            return None

        search_term = str(pre_prod_no).strip()
        df_tracker[col_name] = df_tracker[col_name].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        result = df_tracker[df_tracker[col_name] == search_term]
        return result.iloc[0].to_dict() if not result.empty else None
            
    except Exception as e:
        st.error(f"Error reading project database: {e}")
    return None

def get_next_trial_reference(pre_prod_no):
    """Calculates the next trial number (e.g., 12345_T2) by checking submission history."""
    if not os.path.exists(SUBMISSIONS_FILE):
        return f"{pre_prod_no}_T1"
    
    try:
        df_history = pd.read_parquet(SUBMISSIONS_FILE)
        # Ensure ID is treated as string for comparison
        existing_trials = df_history[df_history['Pre-Prod No.'] == str(pre_prod_no)]
        count = len(existing_trials)
        return f"{pre_prod_no}_T{count + 1}"
    except:
        return f"{pre_prod_no}_T1"

def display_trial_history(pre_prod_no):
    """Displays a summary table of previous trials for this project."""
    if os.path.exists(SUBMISSIONS_FILE):
        df = pd.read_parquet(SUBMISSIONS_FILE)
        history = df[df['Pre-Prod No.'] == str(pre_prod_no)].sort_values('Date', ascending=False)
        
        if not history.empty:
            st.info(f"Existing Trials Found: **{len(history)}**")
            # Show relevant columns for a quick overview
            st.dataframe(history[['Trial Ref', 'Date', 'Operator', 'Observations']], use_container_width=True)
        else:
            st.write("No previous trial history found for this Pre-Prod number.")

def update_tracker_status(pre_prod_no):
    """Updates the 'Injection trial requested' column to 'Submitted' in the CSV tracker."""
    csv_path = os.path.join(BASE_DIR, "ProjectTrackerPP_Cleaned_NA.csv")
    
    if not os.path.exists(csv_path):
        st.error(f"Tracker CSV not found at: {csv_path}")
        return

    try:
        # Load the CSV
        df = pd.read_csv(csv_path)
        col_id = "Pre-Prod No."
        col_status = "Injection trial requested"

        # Ensure types match for searching
        search_term = str(pre_prod_no).strip()
        df[col_id] = df[col_id].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        if search_term in df[col_id].values:
            # Update the status to 'Submitted' (or whatever status you prefer)
            df.loc[df[col_id] == search_term, col_status] = "Submitted"
            df.to_csv(csv_path, index=False)
        else:
            st.warning(f"Pre-Prod No. {search_term} not found in the CSV to update status.")
            
    except Exception as e:
        st.error(f"Error updating CSV tracker: {e}")

# --- INITIALIZE SESSION STATE ---
if 'lookup_data' not in st.session_state:
    st.session_state.lookup_data = {}

# --- HEADER & SEARCH ---
st.title("Injection Trial Data Entry")

st.subheader("Search Project Tracker")
col_s1, col_s2 = st.columns([1, 3])
with col_s1:
    search_input = st.text_input("Enter Pre-Prod No. (e.g. 11925):")
with col_s2:
    st.write("##") 
    if st.button("Pull Information"):
        if search_input:
            data = get_project_data(search_input)
            if data:
                st.session_state.lookup_data = data
                st.success(f"Project details loaded for {search_input}")
            else:
                st.warning("No project data found. You can still fill the form manually.")
                st.session_state.lookup_data = {}

st.divider()

# --- TRIAL HISTORY SECTION ---
if search_input:
    st.subheader(f"Trial Timeline: {search_input}")
    display_trial_history(search_input)
    st.divider()

# --- MAIN FORM ---
# We use the search_input as the base for the Trial Reference
if search_input:
    ld = st.session_state.lookup_data
    current_trial_ref = get_next_trial_reference(search_input)

    with st.form("injection_xlsm_form", clear_on_submit=True):
        st.subheader(f"New Trial Entry: {current_trial_ref}")
        
        # --- SECTION 1: SALES & ADMINISTRATION ---
        st.subheader("1. Sales & Administration")
        s1, s2, s3, s4 = st.columns(4)
        with s1:
            trial_date = st.date_input("Date", datetime.now())
            sales_rep = st.text_input("Sales Rep", value=ld.get('Sales Rep', ''))
        with s2:
            # Displaying the auto-generated trial reference
            job_no_display = st.text_input("Base Pre-Prod No.", value=search_input, disabled=True)
            active_ref = st.text_input("Trial Reference", value=current_trial_ref, disabled=True)
            target_to = st.text_input("Target to", value=ld.get('Target to', ''))
        with s3:
            client = st.text_input("Client", value=ld.get('Client', ''))
            trial_qty = st.number_input("Trial Quantity", step=1)
        with s4:
            operator = st.text_input("Operator")
            machine_used_to_print = st.text_input("Production Machine", value=ld.get('Machine', ''))
            machine_used = st.text_input("Trial Machine", value=ld.get('Trial Machine', ''))

        st.divider()

        # --- SECTION 2: PRODUCT SPECIFICATIONS ---
        st.subheader("2. Product Specifications")
        # Changed to 4 columns to accommodate p4
        p1, p2, p3, p4 = st.columns(4) 
        
        with p1:
            description = st.text_input("Description", value=ld.get('Project Description', ''))
            length = st.text_input("Length", value=str(ld.get('Length', '')))
            orifice = st.text_input("Orifice", value=str(ld.get('Orifice', '')))
            supplier = st.text_input("Supplier", value=str(ld.get('Supplier', '')))
        with p2:
            cap_lid_style = st.text_input("Cap_Lid Style", value=ld.get('Cap_Lid Style', ''))
            cap_lid_material = st.text_input("Cap_Lid Material", value=ld.get('Cap_Lid Material', ''))
            cap_lid_diameter = st.text_input("Cap_Lid Diameter", value=str(ld.get('Diameter', '')))
            mix = st.text_input("Mix_%", value=str(ld.get('Mix_%', '')))
        with p3:
            product_code = st.text_input("Product Code", value=ld.get('Product Code', ''))
            material = st.text_input("Material", value=ld.get('Material', ''))
            pigment = st.text_input("Pigment_MB Grade", value=ld.get('Pigment_MB Grade', ''))
            
            # Corrected variable name (using underscores instead of hyphens)
            pre_mix_perc = st.text_input(
                "If no dosing unit, what % was material pre-mixed?", 
                value=str(ld.get('if no_dosing unit, what percentage was material pre-mixed', ''))
            )
        with p4:
            # Logic to determine the default index based on existing data
            current_val = str(ld.get('Tinuvin', 'No')).strip().capitalize()
            default_index = 0 if current_val == "Yes" else 1
            
            # Using radio buttons for a "Yes/No" selection
            tinuvin = st.radio(
                "Tinuvin",
                options=["Yes", "No"],
                index=default_index,
                horizontal=False # Set to True if you want them side-by-side
            )

            # Using radio buttons for a "Yes/No" selection
            is_dosing_unit_fitted_to_machine  = st.radio(
                "Is dosing unit fitted to machine",
                options=["Yes", "No"],
                index=default_index,
                horizontal=False # Set to True if you want them side-by-side
            )


                        
            # Using radio buttons for a "Yes/No" selection
            is_dosing_unit_calibrated  = st.radio(
                "Is dosing unit calibrated",
                options=["Yes", "No"],
                index=default_index,
                horizontal=False # Set to True if you want them side-by-side
            )

        st.divider()
        
        # --- SECTION 3: DOSING UNIT SETTINGS ---
        st.subheader("3. Dosing Unit Settings")
        d1, d2, d3, d4, d5 = st.columns(5)
        with d1: colour_set = st.text_input("Colour Set Value", value=ld.get('Colour Set Value', ''))
        with d2: colour_act = st.text_input("Colour Actual", value=ld.get('Colour Actual', ''))
        with d3: colour_perc = st.text_input("Colour Percentage", value=ld.get('Colour Percentage', ''))
        with d4: shot_w = st.text_input("Shot Weight", value=ld.get('Shot Weight', ''))
        with d5:dosing_time = st.text_input("Dosing Time", value=ld.get('Dosing Time', ''))

        st.divider()

        # --- SECTION 4: MACHINE PROCESS SETTINGS ---
        st.subheader("4. Machine Process Settings")

        st.write("**Pressures, Speeds & Times**")
        pr1, pr2, pr3, pr4 = st.columns(4)
        with pr1:
            inj_p = st.number_input("Injection Pressure (bar)", step=1)
            hold_p = st.number_input("Holding Pressure (bar)", step=1)
        with pr2:
            inj_s = st.number_input("Injection Speed (mm/s)", step=1)
            back_p = st.number_input("Back Pressure (bar)", step=1)
        with pr3:
            cyc_t = st.number_input("Total Cycle Time (s)", format="%.2f")
            cool_t = st.number_input("Cooling Time (s)", format="%.2f")
        with pr4:
            dos_s = st.number_input("Dosage Stroke (mm)", step=1)
            dec_m = st.number_input("Decompression (mm)", step=1)

        st.divider()

        # --- SECTION 5: OBSERVATIONS ---
        st.subheader("5. Trial Observations")
        notes = st.text_area("Observations")

        submit_trial = st.form_submit_button("Submit Trial Entry")

        if submit_trial:
            # 1. Capture all form data into a dictionary
            # Note: All lines below are now indented properly
            new_submission = {
                "Trial Ref": current_trial_ref,
                "Pre-Prod No.": search_input,
                "Date": trial_date.strftime("%Y-%m-%d"),
                "Sales Rep": sales_rep,
                "Client": client,
                "Operator": operator,
                "Machine": machine_used,
                "Observations": notes,
                "Cycle Time": cyc_t,
                "Inj Pressure": inj_p,
                "Tinuvin": tinuvin,
                "Dosing Unit Fitted": is_dosing_unit_fitted_to_machine,
                "Dosing Calibrated": is_dosing_unit_calibrated
            }

            # 2. Append to Parquet file (Historical Submissions)
            df_new = pd.DataFrame([new_submission])
            
            if os.path.exists(SUBMISSIONS_FILE):
                df_existing = pd.read_parquet(SUBMISSIONS_FILE)
                df_final = pd.concat([df_existing, df_new], ignore_index=True)
            else:
                df_final = df_new
                
            df_final.to_parquet(SUBMISSIONS_FILE)
            
            # --- NEW STEP: UPDATE THE CSV TRACKER ---
            update_tracker_status(search_input)
            
            st.success(f"Success! {current_trial_ref} recorded and tracker updated.")
            st.session_state.lookup_data = {}
            st.rerun()
else:
    st.info("Please enter a Pre-Prod Number above to start a trial.")