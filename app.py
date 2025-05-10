import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import requests
import base64
import json
from io import BytesIO

# GitHub Repo dan File Path
REPO = "fajarnadril/Employee-Attendance"
BRANCH = "main"
ATTENDANCE_PATH = "database/EmployeeAbsent.json"
EMPLOYEE_PATH = "database/EmployeeData.json"

def get_jakarta_time():
    tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz)
    return now.strftime('%d/%m/%Y'), now.strftime('%H:%M:%S')

def load_json_from_github(filepath):
    token = st.secrets["GITHUB_TOKEN"]
    headers = {"Authorization": f"token {token}"}
    url = f"https://api.github.com/repos/{REPO}/contents/{filepath}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json()["sha"]
        content = base64.b64decode(r.json()["content"]).decode()
        return json.loads(content), sha
    else:
        return [], None

def save_json_to_github(df, sha):
    token = st.secrets["GITHUB_TOKEN"]
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
    url = f"https://api.github.com/repos/{REPO}/contents/{ATTENDANCE_PATH}"
    content = json.dumps(df.to_dict(orient="records"), indent=2)
    encoded = base64.b64encode(content.encode()).decode()
    payload = {
        "message": f"Update attendance {datetime.now().isoformat()}",
        "content": encoded,
        "branch": BRANCH,
        "sha": sha
    }
    r = requests.put(url, headers=headers, data=json.dumps(payload))
    return r.status_code in [200, 201]

# === UI ===
st.set_page_config(page_title="Employee Attendance", layout="centered")
menu = st.sidebar.selectbox("Pilih Halaman", ["Clock In / Out", "Dashboard"])

today_date, now_time = get_jakarta_time()

attendance_data, attendance_sha = load_json_from_github(ATTENDANCE_PATH)
df = pd.DataFrame(attendance_data)
if df.empty:
    df = pd.DataFrame(columns=["Date", "EmployeeID", "ClockIn", "ClockOut", "DailyLog"])

employee_data, _ = load_json_from_github(EMPLOYEE_PATH)
emp_df = pd.DataFrame(employee_data)


if menu == "Clock In / Out":
    st.title("🕘 Employee Attendance")
    st.markdown(f"**Tanggal (GMT+7):** {today_date}")
    st.markdown(f"**Waktu (GMT+7):** {now_time}")

    emp_df["Display"] = emp_df["EmployeeID"].astype(str) + " - " + emp_df["Name"]
    selected = st.selectbox("Pilih Karyawan", emp_df["Display"])
    employee_id = int(selected.split(" - ")[0])

    if "submit_state" not in st.session_state:
        st.session_state.submit_state = ""

    if st.button("✅ Clock In"):
        new_row = pd.DataFrame([{
            "Date": today_date,
            "EmployeeID": employee_id,
            "ClockIn": now_time,
            "ClockOut": None,
            "DailyLog": None
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        if save_json_to_github(df, attendance_sha):
            st.success("✅ Anda sudah Clock In hari ini.")
            st.rerun()

    if st.button("🔚 Clock Out"):
        matched = df[
            (df["Date"] == today_date) &
            (df["EmployeeID"] == employee_id)
        ]
        if not matched.empty:
            idx = matched.index[0]
            if pd.isna(matched.at[idx, "ClockIn"]):
                st.session_state.submit_state = "manual"
            else:
                st.session_state.submit_state = "update"
        else:
            new_row = pd.DataFrame([{
                "Date": today_date,
                "EmployeeID": employee_id,
                "ClockIn": None,
                "ClockOut": now_time,
                "DailyLog": None
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            if save_json_to_github(df, attendance_sha):
                st.session_state.submit_state = "manual"
                st.rerun()

    if st.session_state.submit_state == "update":
        st.markdown("---")
        st.markdown("📝 **Isi Daily Log untuk Clock Out**")
        daily_log = st.text_area("Daily Log", key="log_update", max_chars=150)
        if st.button("Submit Clock Out"):
            matched = df[
                (df["Date"] == today_date) &
                (df["EmployeeID"] == employee_id)
            ]
            if not matched.empty and daily_log.strip():
                idx = matched.index[0]
                df.at[idx, "ClockOut"] = now_time
                df.at[idx, "DailyLog"] = daily_log
                if save_json_to_github(df, attendance_sha):
                    st.success("✅ Anda sudah attendance hari ini.")
                    st.session_state.submit_state = ""
                    st.rerun()

    elif st.session_state.submit_state == "manual":
        st.markdown("---")
        st.markdown("⚠️ **Anda belum Clock In! Isi di bawah ini secara manual:**")

        hours = [f"{h:02d}" for h in range(0, 24)]
        minutes = [f"{m:02d}" for m in range(0, 60, 5)]
        col1, col2 = st.columns(2)
        with col1:
            selected_hour = st.selectbox("Jam", hours, key="manual_hour")
        with col2:
            selected_minute = st.selectbox("Menit", minutes, key="manual_minute")

        manual_time = f"{selected_hour}:{selected_minute}"
        daily_log = st.text_area("Daily Log", key="log_manual", max_chars=150)

        if st.button("Submit Attendance"):
            matched = df[
                (df["Date"] == today_date) &
                (df["EmployeeID"] == employee_id)
            ]
            if not matched.empty and daily_log.strip():
                idx = matched.index[0]
                df.at[idx, "ClockIn"] = manual_time
                df.at[idx, "ClockOut"] = now_time
                df.at[idx, "DailyLog"] = daily_log
                if save_json_to_github(df, attendance_sha):
                    st.success("✅ Anda sudah attendance hari ini.")
                    st.session_state.submit_state = ""
                    st.rerun()

elif menu == "Dashboard":
    if "last_reload" not in st.session_state or st.session_state.last_reload != "dashboard":
        st.session_state.last_reload = "dashboard"
        st.rerun()
    st.title("🔒 Dashboard Attendance")
    st.success("✅ Akses diterima.")

        # Merge Name dari EmployeeData
    emp_lookup = pd.DataFrame(employee_data)[["EmployeeID", "Name"]]
    df_display = pd.merge(df, emp_lookup, on="EmployeeID", how="left")
    df_display = df_display[["Date", "EmployeeID", "Name", "ClockIn", "ClockOut", "DailyLog"]]

    st.dataframe(df_display)

        # Download Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_display.to_excel(writer, index=False, sheet_name='Attendance')
    output.seek(0)

    st.download_button(
        label="📥 Download Excel (.xlsx)",
        data=output,
        file_name="EmployeeAttendance.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )