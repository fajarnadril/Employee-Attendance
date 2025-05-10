
import streamlit as st
import pandas as pd
from datetime import datetime, date
import os

# Paths
EMPLOYEE_FILE = 'database/EmployeeData.xlsx'
ABSENT_FILE = 'database/EmployeeAbsent.xlsx'

# Helper
def load_employee_data():
    df = pd.read_excel(EMPLOYEE_FILE)
    return df[df['Status'] == 'Active']  # Filter only active employees

def load_attendance_data():
    if os.path.exists(ABSENT_FILE):
        return pd.read_excel(ABSENT_FILE)
    else:
        return pd.DataFrame(columns=["Date", "EmployeeID", "ClockIn", "ClockOut", "Log"])

def save_attendance_data(df):
    df.to_excel(ABSENT_FILE, index=False)

# --- Streamlit App ---
st.set_page_config(page_title="Employee Attendance", layout="wide")

# Sidebar Navigation
page = st.sidebar.selectbox("Go to", ["Attendance", "Dashboard"])

# Load Data
employees = load_employee_data()
attendance = load_attendance_data()
today = date.today().strftime('%d/%m/%Y')

if page == "Attendance":
    st.title("🕒 Attendance Page")
    emp_id = st.selectbox("Select Employee ID", employees['EmployeeID'])
    emp_name = employees.loc[employees['EmployeeID'] == emp_id, 'Name'].values[0]

    # Filter today's attendance
    today_record = attendance[(attendance['Date'] == today) & (attendance['EmployeeID'] == emp_id)]

    clock_in_disabled = False
    clock_out_disabled = True
    already_clocked_out = False

    if not today_record.empty:
        if pd.notna(today_record.iloc[0]['ClockIn']):
            clock_out_disabled = False
        if pd.notna(today_record.iloc[0]['ClockOut']):
            clock_in_disabled = True
            clock_out_disabled = True
            already_clocked_out = True

    st.write(f"👤 Employee: {emp_name} ({emp_id})")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Clock In", disabled=clock_in_disabled):
            now = datetime.now().strftime('%H:%M:%S')
            attendance = attendance.append({
                "Date": today,
                "EmployeeID": emp_id,
                "ClockIn": now,
                "ClockOut": None,
                "Log": None
            }, ignore_index=True)
            save_attendance_data(attendance)
            st.success(f"Clocked in at {now}")
            st.experimental_rerun()

    with col2:
        if st.button("🔚 Clock Out", disabled=clock_out_disabled):
            with st.form("log_form"):
                work_log = st.text_area("Work Log (max 150 chars)", max_chars=150)
                submitted = st.form_submit_button("Submit")
                if submitted:
                    if work_log.strip() == "":
                        st.warning("Work log is required.")
                    else:
                        idx = today_record.index[0]
                        attendance.at[idx, "ClockOut"] = datetime.now().strftime('%H:%M:%S')
                        attendance.at[idx, "Log"] = work_log
                        save_attendance_data(attendance)
                        st.success("Clocked out successfully.")
                        st.experimental_rerun()

    if already_clocked_out:
        st.info("✅ You have completed your attendance for today.")

elif page == "Dashboard":
    st.title("📊 Dashboard Page")

    st.dataframe(attendance)

    with st.expander("➕ Inject Data"):
        with st.form("inject_form"):
            new_date = st.date_input("Date", date.today()).strftime('%d/%m/%Y')
            new_emp = st.selectbox("Employee ID", employees['EmployeeID'])
            new_in = st.text_input("Clock In Time (HH:MM:SS)")
            new_out = st.text_input("Clock Out Time (HH:MM:SS)")
            new_log = st.text_area("Log (max 150 chars)", max_chars=150)

            submit = st.form_submit_button("Submit")

            if submit:
                attendance = attendance.append({
                    "Date": new_date,
                    "EmployeeID": new_emp,
                    "ClockIn": new_in,
                    "ClockOut": new_out,
                    "Log": new_log
                }, ignore_index=True)
                save_attendance_data(attendance)
                st.success("Record injected successfully.")
                st.experimental_rerun()
