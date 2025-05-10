
import streamlit as st
import pandas as pd
from datetime import datetime, date
import pytz
import os
import requests
import base64
import json
from io import BytesIO

# Konfigurasi GitHub
REPO = "fajarbinus/employee-attendance"
BRANCH = "main"
EMPLOYEE_FILE_PATH = "database/EmployeeData.xlsx"
ABSENT_FILE_PATH = "database/EmployeeAbsent.xlsx"

# Helper untuk waktu
def get_current_time():
    tz = pytz.timezone('Asia/Jakarta')
    return datetime.now(tz).strftime('%H:%M:%S')

# Load employee data (local read-only)
def load_employee_data():
    df = pd.read_excel(EMPLOYEE_FILE_PATH)
    return df[df['Status'] == 'Active']

# Load attendance data (via local read)
def load_attendance_data():
    try:
        df = pd.read_excel(ABSENT_FILE_PATH)
        if df.empty or not all(col in df.columns for col in ["Date", "EmployeeID", "ClockIn", "ClockOut", "Log"]):
            raise ValueError("Invalid structure")
        return df
    except:
        return pd.DataFrame(columns=["Date", "EmployeeID", "ClockIn", "ClockOut", "Log"])

# Save to GitHub
def save_attendance_data_to_github(df):
    token = st.secrets["GITHUB_TOKEN"]
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    file_url = f"https://api.github.com/repos/{REPO}/contents/{ABSENT_FILE_PATH}"

    # Get SHA
    get_resp = requests.get(file_url, headers=headers)
    sha = get_resp.json().get("sha", "")

    # Encode file
    buffer = BytesIO()
    df.to_excel(buffer, index=False)
    encoded_content = base64.b64encode(buffer.getvalue()).decode()

    data = {
        "message": "Update attendance data",
        "content": encoded_content,
        "branch": BRANCH,
        "sha": sha
    }

    response = requests.put(file_url, headers=headers, data=json.dumps(data))
    if response.status_code in [200, 201]:
        st.success("✅ Data berhasil disimpan ke GitHub.")
    else:
        st.error(f"❌ Gagal simpan ke GitHub: {response.json()}")

# App utama
st.set_page_config(page_title="Employee Attendance", layout="wide")
page = st.sidebar.selectbox("Go to", ["Attendance", "Dashboard"])

employees = load_employee_data()
attendance = load_attendance_data()
today = date.today().strftime('%d/%m/%Y')

if page == "Attendance":
    st.title("🕒 Attendance Page")
    emp_id = st.selectbox("Select Employee ID", employees['EmployeeID'])
    emp_name = employees.loc[employees['EmployeeID'] == emp_id, 'Name'].values[0]
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
            now = get_current_time()
            new_row = pd.DataFrame([{
                "Date": today,
                "EmployeeID": emp_id,
                "ClockIn": now,
                "ClockOut": None,
                "Log": None
            }])
            attendance = pd.concat([attendance, new_row], ignore_index=True)
            save_attendance_data_to_github(attendance)
            st.rerun()

    with col2:
        if st.button("🔚 Clock Out", disabled=clock_out_disabled):
            with st.form("log_form"):
                work_log = st.text_area("Work Log (max 150 chars)", max_chars=150)
                submitted = st.form_submit_button("Submit")
                if submitted and work_log.strip():
                    idx = attendance[
                        (attendance['Date'] == today) &
                        (attendance['EmployeeID'] == emp_id) &
                        (attendance['ClockOut'].isna())
                    ].index
                    if not idx.empty:
                        attendance.at[idx[0], "ClockOut"] = get_current_time()
                        attendance.at[idx[0], "Log"] = work_log
                        save_attendance_data_to_github(attendance)
                        st.rerun()
                    else:
                        st.error("No matching Clock In record found.")

    if already_clocked_out:
        st.info("✅ You have completed your attendance for today.")

elif page == "Dashboard":
    st.title("🔒 Secure Dashboard")
    pin = st.text_input("Enter PIN to access dashboard", type="password")
    if pin == "357101":
        st.dataframe(attendance)
    else:
        st.warning("PIN required to access the dashboard.")
