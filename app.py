
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
REPO = "fajarnadril/Employee-Attendance"
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

    # Try to get SHA
    r = requests.get(file_url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get("sha", "")
    elif r.status_code == 404:
        sha = None  # File not found, will create new
    else:
        st.error(f"GitHub error: {r.json()}")
        return

    buffer = BytesIO()
    df.to_excel(buffer, index=False)
    encoded_content = base64.b64encode(buffer.getvalue()).decode()

    data = {
        "message": "Update or create attendance file",
        "content": encoded_content,
        "branch": BRANCH,
    }
    if sha:
        data["sha"] = sha

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
    emp_status = employees.loc[employees['EmployeeID'] == emp_id, 'Status'].values[0]
    st.write(f"👤 Name: {emp_name} | 🆔 ID: {emp_id} | 📋 Status: {emp_status}")  
**🆔 ID:** {emp_id}  
**📋 Status:** {emp_status}")

    existing_today = attendance[
        (attendance['Date'] == today) &
        (attendance['EmployeeID'] == emp_id)
    ]

    already_clocked_in = not existing_today.empty
    already_clocked_out = already_clocked_in and pd.notna(existing_today.iloc[0]['ClockOut'])

    today_record = attendance[
        (attendance['Date'].astype(str) == today) &
        (attendance['EmployeeID'].astype(str) == str(emp_id))
    ]

    if today_record.empty:
        if st.button("✅ Clock In"):
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
            st.success(f"✅ Clocked In at {now}")
            st.rerun()
    else:
        clock_in_time = today_record.iloc[0]['ClockIn']
        st.info(f"🕒 Clock In Hari Ini: {clock_in_time}")

        if pd.isna(today_record.iloc[0]['ClockOut']):
            with st.form("log_form"):
                work_log = st.text_area("Work Log (max 150 chars)", max_chars=150)
                submitted = st.form_submit_button("Submit Clock Out")
                if submitted and work_log.strip():
                    idx = today_record.index
                    if not idx.empty:
                        attendance.at[idx[0], "ClockOut"] = get_current_time()
                        attendance.at[idx[0], "Log"] = work_log
                        save_attendance_data_to_github(attendance)
                        st.success("✅ Clock Out berhasil disimpan.")
                        st.rerun()
                    else:
                        st.error("⚠️ Tidak ditemukan baris Clock In yang aktif untuk hari ini.")
        else:
            st.success(f"✅ Anda sudah Clock Out hari ini: {today_record.iloc[0]['ClockOut']}")

    if already_clocked_out:
        st.info("✅ Anda telah menyelesaikan absensi hari ini.")

elif page == "Dashboard":
    st.title("🔒 Secure Dashboard")
    pin = st.text_input("Enter PIN to access dashboard", type="password")
    if pin == "357101":
        st.dataframe(attendance)
    else:
        st.warning("PIN required to access the dashboard.")
