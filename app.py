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
    st.title("✨LOGIC Attendance")
    st.markdown("---")
    st.markdown(f"**Tanggal (GMT+7):** {today_date}")
    st.markdown(f"**Waktu (GMT+7):** {now_time}")
    emp_df["Display"] = emp_df["EmployeeID"].astype(str) + " - " + emp_df["Name"]
    st.markdown("---")
    selected = st.selectbox("Pilih Karyawan", emp_df["Display"])
    employee_id = int(selected.split(" - ")[0])

    if "submit_state" not in st.session_state:
        st.session_state.submit_state = ""
    st.markdown("---")
    if st.button("✅ Clock In"):
        # Paksa string comparison
        employee_id_str = str(employee_id)
        already_clocked_in = df[
            (df["Date"] == today_date) &
            (df["EmployeeID"].astype(str) == employee_id_str)
        ]
        if not already_clocked_in.empty:
            st.error("⚠️ Anda sudah Clock In hari ini.")
        else:
            new_row = pd.DataFrame([{
                "Date": today_date,
                "EmployeeID": employee_id,
                "ClockIn": now_time,
                "ClockOut": None,
                "DailyLog": None
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            if save_json_to_github(df, attendance_sha):
                # Reload data untuk memastikan tersimpan
                attendance_data, attendance_sha = load_json_from_github(ATTENDANCE_PATH)
                df = pd.DataFrame(attendance_data)
                st.error("✅ Anda sudah Clock In hari ini.")
                st.rerun()
            else:
                st.error("❌ Gagal menyimpan Clock In ke GitHub.")


    if st.button("🔚 Clock Out"):
        matched = df[
            (df["Date"] == today_date) &
            (df["EmployeeID"].astype(str) == str(employee_id))
        ]
        if not matched.empty:
            idx = matched.index[0]
            if pd.notna(matched.at[idx, "ClockOut"]):
                st.error("⚠️ Anda sudah Clock Out hari ini.")
            elif pd.isna(matched.at[idx, "ClockIn"]):
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
                    st.error("✅ Anda sudah attendance hari ini.")
                    st.session_state.submit_state = ""
                    st.rerun()

    elif st.session_state.submit_state == "manual":
        st.markdown("---")
        st.markdown("⚠️ **Anda belum Clock In!**")
        manual_time_input = st.time_input("Jam Clock In (Isi Manual)", key="manual_clockin")
        manual_time = manual_time_input.strftime("%H:%M:%S")
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
                    st.error("✅ Anda sudah attendance hari ini.")
                    st.session_state.submit_state = ""
                    st.rerun()

elif menu == "Dashboard":
    if "dashboard_pin_authenticated" not in st.session_state:
        st.session_state.dashboard_pin_authenticated = False

    if not st.session_state.dashboard_pin_authenticated:
        st.title("🔒 Dashboard Attendance")
        pin_input = st.text_input("Masukkan PIN untuk akses Dashboard:", type="password")
        if pin_input == "357101":
            st.error("✅ Akses diterima.")
            st.session_state.dashboard_pin_authenticated = True
            st.rerun()
        elif pin_input:
            st.error("❌ PIN salah.")

    else:
        # Seluruh kode dashboard kamu dimulai dari sini
        if "last_reload" not in st.session_state or st.session_state.last_reload != "dashboard":
            st.session_state.last_reload = "dashboard"
            st.rerun()
        st.title("📋 Dashboard Attendance")

        # =====================
        # Tambah Employee
        st.markdown("---")
        st.subheader("➕ Tambah Karyawan Baru")
        with st.form("add_employee"):
            new_id = st.text_input("EmployeeID")
            new_name = st.text_input("Nama Lengkap")
            new_dept = st.text_input("Department")
            submitted = st.form_submit_button("Tambah")

            if submitted:
                if not new_id.isdigit():
                    st.error("❌ EmployeeID harus berupa angka.")
                elif new_id in emp_df["EmployeeID"].astype(str).values:
                    st.error("❌ EmployeeID sudah ada!")
                elif new_name.strip() == "" or new_dept.strip() == "":
                    st.error("❌ Semua field harus diisi.")
                else:
                    new_row = pd.DataFrame([{
                        "EmployeeID": new_id,
                        "Name": new_name.strip().upper(),
                        "Department": new_dept.strip().upper()
                    }])
                    emp_df = pd.concat([emp_df, new_row], ignore_index=True)
                    # Save ke GitHub
                    token = st.secrets["GITHUB_TOKEN"]
                    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
                    url = f"https://api.github.com/repos/{REPO}/contents/{EMPLOYEE_PATH}"

                    encoded = base64.b64encode(json.dumps(emp_df.to_dict(orient="records"), indent=2).encode()).decode()
                    get_resp = requests.get(url, headers=headers)
                    sha_emp = get_resp.json()["sha"] if get_resp.status_code == 200 else None

                    payload = {
                        "message": f"Add employee {new_id}",
                        "content": encoded,
                        "branch": BRANCH,
                        "sha": sha_emp
                    }
                    put_resp = requests.put(url, headers=headers, data=json.dumps(payload))
                    if put_resp.status_code in [200, 201]:
                        st.error("✅ Karyawan berhasil ditambahkan.")
                        st.rerun()
                    else:
                        st.error("❌ Gagal menyimpan ke GitHub.")
                        st.code(json.dumps(put_resp.json(), indent=2))

        # =====================
        # Hapus Employee
        st.markdown("---")
        st.subheader("🗑 Hapus Karyawan")
        employee_ids = emp_df["EmployeeID"].tolist()
        emp_df["Display"] = emp_df["EmployeeID"].astype(str) + " - " + emp_df["Name"]
        selected_display = st.selectbox("Pilih Karyawan untuk dihapus", emp_df["Display"])
        selected_id = selected_display.split(" - ")[0]

        if st.button("Hapus Karyawan Ini"):
            selected_name = emp_df[emp_df["EmployeeID"].astype(str) == selected_id]["Name"].values[0]
            emp_df = emp_df[emp_df["EmployeeID"].astype(str) != selected_id]
            st.error(f"✅ Karyawan '{selected_name}' (ID: {selected_id}) telah dihapus.")
            
            # Save ke GitHub
            token = st.secrets["GITHUB_TOKEN"]
            headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
            url = f"https://api.github.com/repos/{REPO}/contents/{EMPLOYEE_PATH}"

            encoded = base64.b64encode(json.dumps(emp_df.to_dict(orient="records"), indent=2).encode()).decode()
            get_resp = requests.get(url, headers=headers)
            sha_emp = get_resp.json()["sha"] if get_resp.status_code == 200 else None

            payload = {
                "message": f"Delete employee {selected_id}",
                "content": encoded,
                "branch": BRANCH,
                "sha": sha_emp
            }
            put_resp = requests.put(url, headers=headers, data=json.dumps(payload))
            if put_resp.status_code in [200, 201]:
                st.error("✅ Karyawan berhasil dihapus.")
                st.rerun()
            else:
                st.error("❌ Gagal menyimpan ke GitHub.")
                st.code(json.dumps(put_resp.json(), indent=2))

        # =====================
        # Tampilkan EmployeeData
        st.markdown("---")
        st.subheader("📋 Employee List")
        name_filter = st.selectbox("🔎 Filter by Name", ["(All)"] + sorted(emp_df["Name"].unique()))
        dept_filter = st.selectbox("🏢 Filter by Department", ["(All)"] + sorted(emp_df["Department"].unique()))

        filtered_emp = emp_df.copy()
        if name_filter != "(All)":
            filtered_emp = filtered_emp[filtered_emp["Name"] == name_filter]
        if dept_filter != "(All)":
            filtered_emp = filtered_emp[filtered_emp["Department"] == dept_filter]

        # Hitung jumlah DailyLog per EmployeeID
        log_counts = df[df["DailyLog"].notna()].groupby("EmployeeID").size().reset_index(name="DailyLogCount")

        # Gabungkan ke filtered_emp
        filtered_emp_with_logs = pd.merge(filtered_emp, log_counts, on="EmployeeID", how="left").fillna({"DailyLogCount": 0})
        filtered_emp_with_logs["DailyLogCount"] = filtered_emp_with_logs["DailyLogCount"].astype(int)

        st.dataframe(filtered_emp_with_logs.drop(columns=["Display"]))


        st.markdown("---")
        st.subheader("🛠 Edit Attendance Data")
        with st.form("inject_form"):
            inj_date = st.date_input("Tanggal", format="DD/MM/YYYY")
            emp_df["Display"] = emp_df["EmployeeID"].astype(str) + " - " + emp_df["Name"]
            inj_emp_display = st.selectbox("Pilih Karyawan", emp_df["Display"])
            inj_emp_id = inj_emp_display.split(" - ")[0]

            col1, col2 = st.columns(2)
            with col1:
                inj_clockin = st.time_input("Jam Clock In", value=None)
            with col2:
                inj_clockout = st.time_input("Jam Clock Out", value=None)
            inj_log = st.text_area("Daily Log", max_chars=150)
            inject_submit = st.form_submit_button("Submit Inject")

            if inject_submit:
                inj_date_str = inj_date.strftime("%d/%m/%Y")
                existing_index = df[
                    (df["Date"] == inj_date_str) &
                    (df["EmployeeID"].astype(str) == inj_emp_id)
                ].index

                new_row = {
                    "Date": inj_date_str,
                    "EmployeeID": inj_emp_id,
                    "ClockIn": inj_clockin.strftime("%H:%M:%S") if inj_clockin else None,
                    "ClockOut": inj_clockout.strftime("%H:%M:%S") if inj_clockout else None,
                    "DailyLog": inj_log
                }

                if not existing_index.empty:
                    df.loc[existing_index[0]] = new_row
                else:
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

                # Simpan ke GitHub
                token = st.secrets["GITHUB_TOKEN"]
                headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
                url = f"https://api.github.com/repos/{REPO}/contents/{ATTENDANCE_PATH}"
                encoded = base64.b64encode(json.dumps(df.to_dict(orient="records"), indent=2).encode()).decode()
                get_resp = requests.get(url, headers=headers)
                sha_attn = get_resp.json()["sha"] if get_resp.status_code == 200 else None

                payload = {
                    "message": f"Inject attendance {inj_emp_id} {inj_date_str}",
                    "content": encoded,
                    "branch": BRANCH,
                    "sha": sha_attn
                }
                put_resp = requests.put(url, headers=headers, data=json.dumps(payload))
                if put_resp.status_code in [200, 201]:
                    st.error("✅ Data berhasil di-inject atau diperbarui.")
                    st.rerun()
                else:
                    st.error("❌ Gagal menyimpan ke GitHub.")
                    st.code(json.dumps(put_resp.json(), indent=2))

                

            # =====================
        # Tampilkan Log Absensi
        st.markdown("---")
        st.subheader("📅 Attendance Log")

        emp_lookup = emp_df.copy()
        emp_lookup["EmployeeID"] = emp_lookup["EmployeeID"].astype(str)

        df_display = df.copy()
        df_display["EmployeeID"] = df_display["EmployeeID"].astype(str)

        df_display = pd.merge(df_display, emp_lookup[["EmployeeID", "Name"]], on="EmployeeID", how="left")

        # Jika filter nama aktif → filter juga absensinya
        if name_filter != "(All)":
            df_display = df_display[df_display["Name"] == name_filter]
        if dept_filter != "(All)":
            allowed_ids = filtered_emp["EmployeeID"].unique()
            df_display = df_display[df_display["EmployeeID"].isin(allowed_ids)]

        df_display = df_display[["Date", "EmployeeID", "Name", "ClockIn", "ClockOut", "DailyLog"]]

        # Tombol Download
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

        st.dataframe(df_display)

