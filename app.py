import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import requests
import base64
import json
from io import BytesIO

# Konfigurasi GitHub
REPO = "fajarnadril/Employee-Attendance"
BRANCH = "main"
FILE_PATH = "database/EmployeeAbsent.json"

def get_jakarta_time():
    tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz)
    return now.strftime('%d/%m/%Y'), now.strftime('%H:%M:%S')

def load_json_from_github():
    token = st.secrets["GITHUB_TOKEN"]
    headers = {"Authorization": f"token {token}"}
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        sha = response.json()["sha"]
        content = base64.b64decode(response.json()["content"]).decode()
        data = json.loads(content)
        return pd.DataFrame(data), sha
    else:
        return pd.DataFrame(columns=["Date", "EmployeeID", "ClockIn", "ClockOut", "DailyLog"]), None

def save_json_to_github(df, sha=None):
    token = st.secrets["GITHUB_TOKEN"]
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"

    content = json.dumps(df.to_dict(orient="records"), indent=2)
    encoded = base64.b64encode(content.encode()).decode()

    payload = {
        "message": f"Update attendance {datetime.now().isoformat()}",
        "content": encoded,
        "branch": BRANCH
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(url, headers=headers, data=json.dumps(payload))
    return r.status_code in [200, 201]

# ==== UI ====
st.set_page_config(page_title="Employee Attendance", layout="centered")
menu = st.sidebar.selectbox("Pilih Halaman", ["Clock In / Out", "Dashboard"])

today_date, now_time = get_jakarta_time()
df, sha = load_json_from_github()

if menu == "Clock In / Out":
    st.title("🕘 Employee Attendance")
    st.markdown(f"**Tanggal (GMT+7):** {today_date}")
    st.markdown(f"**Waktu (GMT+7):** {now_time}")
    employee_id = st.text_input("Employee ID")

    if "submit_state" not in st.session_state:
        st.session_state.submit_state = ""

    if st.button("✅ Clock In"):
        if not employee_id:
            st.warning("Isi Employee ID.")
        else:
            new_row = pd.DataFrame([{
                "Date": today_date,
                "EmployeeID": employee_id,
                "ClockIn": now_time,
                "ClockOut": None,
                "DailyLog": None
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            if save_json_to_github(df, sha):
                st.success("✅ Anda sudah Clock In hari ini.")
                st.rerun()

    if st.button("🔚 Clock Out"):
        if not employee_id:
            st.warning("Isi Employee ID.")
        else:
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
                if save_json_to_github(df, sha):
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
                if save_json_to_github(df, sha):
                    st.success("✅ Anda sudah attendance hari ini.")
                    st.session_state.submit_state = ""
                    st.rerun()

    elif st.session_state.submit_state == "manual":
        st.markdown("---")
        st.markdown("⚠️ **Anda belum Clock In! Isi di bawah ini secara manual:**")

        # Jam 00–23, Menit per 5
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
                if save_json_to_github(df, sha):
                    st.success("✅ Anda sudah attendance hari ini.")
                    st.session_state.submit_state = ""
                    st.rerun()

elif menu == "Dashboard":
    st.title("🔒 Dashboard Attendance")
    pin = st.text_input("Masukkan PIN untuk akses data:", type="password")
    if pin == "357101":
        st.success("✅ Akses diterima.")
        st.dataframe(df)

        # Download Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Attendance')
        output.seek(0)

        st.download_button(
            label="📥 Download Excel (.xlsx)",
            data=output,
            file_name="EmployeeAttendance.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("PIN diperlukan untuk mengakses Dashboard.")
