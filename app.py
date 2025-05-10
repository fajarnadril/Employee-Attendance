
import streamlit as st
import pandas as pd
from datetime import datetime, date
import pytz
import os
import requests
import base64
import json
from io import BytesIO

# GitHub configuration
REPO = "fajarbinus/employee-attendance"
BRANCH = "main"
EMPLOYEE_FILE_PATH = "database/EmployeeData.xlsx"
ABSENT_FILE_PATH = "database/EmployeeAbsent.xlsx"

# Timezone
def get_current_time():
    tz = pytz.timezone('Asia/Jakarta')
    return datetime.now(tz).strftime('%H:%M:%S')

# Load employee data
def load_employee_data():
    df = pd.read_excel(EMPLOYEE_FILE_PATH)
    return df[df['Status'] == 'Active']

# Load attendance data
def load_attendance_data():
    try:
        df = pd.read_excel(ABSENT_FILE_PATH)
        if df.empty or not all(col in df.columns for col in ["Date", "EmployeeID", "ClockIn", "ClockOut", "Log"]):
            raise ValueError("Invalid structure")
        return df
    except:
        return pd.DataFrame(columns=["Date", "EmployeeID", "ClockIn", "ClockOut", "Log"])

# Save attendance to GitHub
def save_attendance_data_to_github(df):
    token = st.secrets["GITHUB_TOKEN"]
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    file_url = f"https://api.github.com/repos/{REPO}/contents/{ABSENT_FILE_PATH}"

    get_resp = requests.get(file_url, headers=headers)
    sha = get_resp.json().get("sha", "")

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
        st.success("✅ Data saved to GitHub.")
    else:
        st.error(f"❌ Failed to save to GitHub: {response.json()}")

# Streamlit app
st.set_page_config(page_title="Employee Attendance", layout="wide")
page = st.sidebar.selectbox("Go to", ["Attendance", "Dashboard"])

employees = load_employee_data()
attendance = load_attendance_data()
today = date.today().strftime('%d/%m/%Y')

if page == "Attendance":
    st.title("🕒 Attendance Page")
    emp_id = st.selectbox("Select Employee ID", employees['EmployeeID'])
    emp_name = employees.loc[employees['EmployeeID'] == emp_id, 'Name'].values[0]
    st.write(f"👤 Employee: {emp_name} ({emp_id})")

    # Check existing record
    existing_today = attendance[
        (attendance['Date'] == today) &
        (attendance['EmployeeID'] == emp_id)
    ]

    already_clocked_in = not existing_today.empty
    already_clocked_out = already_clocked_in and pd.notna(existing_today.iloc[0]['ClockOut'])

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Clock In", disabled=already_clocked_in):
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
        if st.button("🔚 Clock Out"):
            if not already_clocked_in:
                st.warning("⚠️ Anda belum Clock In hari ini.")
            elif already_clocked_out:
                st.info("✅ Anda sudah Clock Out hari ini.")
            else:
                with st.form("log_form"):
                    work_log = st.text_area("Work Log (max 150 chars)", max_chars=150)
                    submitted = st.form_submit_button("Submit")
                    if submitted and work_log.strip():
                        idx = existing_today.index[0]
                        attendance.at[idx, "ClockOut"] = get_current_time()
                        attendance.at[idx, "Log"] = work_log
                        save_attendance_data_to_github(attendance)
                        st.rerun()

elif page == "Dashboard":
    st.title("🔒 Secure Dashboard")
    pin = st.text_input("Enter PIN to access dashboard", type="password")
    if pin == "357101":
        st.dataframe(attendance)
    else:
        st.warning("PIN required to access the dashboard.")
