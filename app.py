import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import requests
import base64
import json
from io import BytesIO

# Configuration Constants
REPOSITORY = "fajarnadril/Employee-Attendance"
BRANCH = "main"
FILE_PATHS = {
    "attendance": "database/EmployeeAbsent.json",
    "employee": "database/EmployeeData.json"
}
TIMEZONE = 'Asia/Jakarta'
DASHBOARD_PIN = "357101"
ADMIN_PIN = "357101"  # Using the same PIN for both Dashboard and Admin access

def get_current_time():
    """Get current date and time in Jakarta timezone."""
    timezone = pytz.timezone(TIMEZONE)
    current_time = datetime.now(timezone)
    return current_time.strftime('%d/%m/%Y'), current_time.strftime('%H:%M:%S')

def fetch_github_json(filepath):
    """Fetch JSON file from GitHub repository."""
    token = st.secrets["GITHUB_TOKEN"]
    headers = {"Authorization": f"token {token}"}
    url = f"https://api.github.com/repos/{REPOSITORY}/contents/{filepath}"
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        content_sha = response.json()["sha"]
        content_data = base64.b64decode(response.json()["content"]).decode()
        return json.loads(content_data), content_sha
    else:
        return [], None

def update_github_json(filepath, data, content_sha):
    """Update JSON file in GitHub repository."""
    token = st.secrets["GITHUB_TOKEN"]
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
    url = f"https://api.github.com/repos/{REPOSITORY}/contents/{filepath}"
    
    content = json.dumps(data, indent=2)
    encoded_content = base64.b64encode(content.encode()).decode()
    
    payload = {
        "message": f"Update {filepath} {datetime.now().isoformat()}",
        "content": encoded_content,
        "branch": BRANCH,
        "sha": content_sha
    }
    
    response = requests.put(url, headers=headers, data=json.dumps(payload))
    return response.status_code in [200, 201]

# === UI Setup ===
st.set_page_config(page_title="Employee Attendance System", layout="centered")

# Load application data
current_date, current_time = get_current_time()
attendance_data, attendance_sha = fetch_github_json(FILE_PATHS["attendance"])
attendance_df = pd.DataFrame(attendance_data)
if attendance_df.empty:
    attendance_df = pd.DataFrame(columns=["Date", "EmployeeID", "ClockIn", "ClockOut", "DailyLog"])

employee_data, employee_sha = fetch_github_json(FILE_PATHS["employee"])
employee_df = pd.DataFrame(employee_data)
employee_df["DisplayName"] = employee_df["EmployeeID"].astype(str) + " - " + employee_df["Name"]

# Sidebar navigation
selected_page = st.sidebar.selectbox(
    "Select Page", 
    ["Clock In / Out", "Dashboard", "Manage User"]
)

# === Clock In/Out Page ===
if selected_page == "Clock In / Out":
    st.title("✨ LOGIC Attendance")
    st.markdown("---")
    st.markdown(f"**Date (GMT+7):** {current_date}")
    st.markdown(f"**Time (GMT+7):** {current_time}")
    st.markdown("---")
    
    selected_employee = st.selectbox("Select Employee", employee_df["DisplayName"])
    employee_id = int(selected_employee.split(" - ")[0])
    employee_id_str = str(employee_id)

    if "attendance_action_state" not in st.session_state:
        st.session_state.attendance_action_state = ""
    
    st.markdown("---")
    
    # Clock In Button
    if st.button("✅ Clock In"):
        already_clocked_in = attendance_df[
            (attendance_df["Date"] == current_date) &
            (attendance_df["EmployeeID"].astype(str) == employee_id_str)
        ]
        
        if not already_clocked_in.empty:
            st.error("⚠️ You have already clocked in today.")
        else:
            new_attendance = pd.DataFrame([{
                "Date": current_date,
                "EmployeeID": employee_id,
                "ClockIn": current_time,
                "ClockOut": None,
                "DailyLog": None
            }])
            
            updated_attendance = pd.concat([attendance_df, new_attendance], ignore_index=True)
            
            if update_github_json(FILE_PATHS["attendance"], updated_attendance.to_dict(orient="records"), attendance_sha):
                attendance_data, attendance_sha = fetch_github_json(FILE_PATHS["attendance"])
                attendance_df = pd.DataFrame(attendance_data)
                st.success("✅ Clock in successful.")
                st.rerun()
            else:
                st.error("❌ Failed to save clock in data.")

    # Clock Out Button
    if st.button("🔚 Clock Out"):
        today_attendance = attendance_df[
            (attendance_df["Date"] == current_date) &
            (attendance_df["EmployeeID"].astype(str) == employee_id_str)
        ]
        
        if not today_attendance.empty:
            idx = today_attendance.index[0]
            if pd.notna(today_attendance.at[idx, "ClockOut"]):
                st.warning("⚠️ You have already clocked out today.")
            elif pd.isna(today_attendance.at[idx, "ClockIn"]):
                st.session_state.attendance_action_state = "manual_entry"
            else:
                st.session_state.attendance_action_state = "complete_clockout"
        else:
            new_attendance = pd.DataFrame([{
                "Date": current_date,
                "EmployeeID": employee_id,
                "ClockIn": None,
                "ClockOut": current_time,
                "DailyLog": None
            }])
            
            updated_attendance = pd.concat([attendance_df, new_attendance], ignore_index=True)
            
            if update_github_json(FILE_PATHS["attendance"], updated_attendance.to_dict(orient="records"), attendance_sha):
                st.session_state.attendance_action_state = "manual_entry"
                st.rerun()

    # Handle clock out with daily log
    if st.session_state.attendance_action_state == "complete_clockout":
        st.markdown("---")
        st.markdown("📝 **Enter Daily Log for Clock Out**")
        daily_log = st.text_area("Daily Log", key="log_update", max_chars=150)
        
        if st.button("Submit Clock Out"):
            if daily_log.strip():
                today_attendance = attendance_df[
                    (attendance_df["Date"] == current_date) &
                    (attendance_df["EmployeeID"] == employee_id)
                ]
                
                if not today_attendance.empty:
                    idx = today_attendance.index[0]
                    attendance_df.at[idx, "ClockOut"] = current_time
                    attendance_df.at[idx, "DailyLog"] = daily_log
                    
                    if update_github_json(FILE_PATHS["attendance"], attendance_df.to_dict(orient="records"), attendance_sha):
                        st.success("✅ Attendance completed successfully.")
                        st.session_state.attendance_action_state = ""
                        st.rerun()
            else:
                st.error("Daily log cannot be empty.")

    # Handle manual clock in entry
    elif st.session_state.attendance_action_state == "manual_entry":
        st.markdown("---")
        st.markdown("⚠️ **Clock In record not found!**")
        manual_clock_in = st.time_input("Clock In Time (Manual Entry)", key="manual_clockin")
        manual_time = manual_clock_in.strftime("%H:%M:%S")
        daily_log = st.text_area("Daily Log", key="log_manual", max_chars=150)

        if st.button("Submit Full Attendance"):
            if daily_log.strip():
                today_attendance = attendance_df[
                    (attendance_df["Date"] == current_date) &
                    (attendance_df["EmployeeID"] == employee_id)
                ]
                
                if not today_attendance.empty:
                    idx = today_attendance.index[0]
                    attendance_df.at[idx, "ClockIn"] = manual_time
                    attendance_df.at[idx, "ClockOut"] = current_time
                    attendance_df.at[idx, "DailyLog"] = daily_log
                    
                    if update_github_json(FILE_PATHS["attendance"], attendance_df.to_dict(orient="records"), attendance_sha):
                        st.success("✅ Attendance completed successfully.")
                        st.session_state.attendance_action_state = ""
                        st.rerun()
            else:
                st.error("Daily log cannot be empty.")

# === Dashboard Page ===
elif selected_page == "Dashboard":
    if "dashboard_authenticated" not in st.session_state:
        st.session_state.dashboard_authenticated = False

    if not st.session_state.dashboard_authenticated:
        st.title("🔒 Attendance Dashboard")
        pin_input = st.text_input("Enter PIN to access Dashboard:", type="password")
        
        if pin_input == DASHBOARD_PIN:
            st.success("✅ Access granted.")
            st.session_state.dashboard_authenticated = True
            st.rerun()
        elif pin_input:
            st.error("❌ Incorrect PIN.")
    else:
        st.title("📋 Attendance Dashboard")
        
        # Attendance Record Editor
        st.markdown("---")
        st.subheader("🛠 Edit Attendance Records")
        
        with st.form("attendance_editor_form"):
            edit_date = st.date_input("Date", format="DD/MM/YYYY")
            edit_employee = st.selectbox("Select Employee", employee_df["DisplayName"])
            edit_employee_id = edit_employee.split(" - ")[0]

            col1, col2 = st.columns(2)
            with col1:
                edit_clock_in = st.time_input("Clock In Time", value=None)
            with col2:
                edit_clock_out = st.time_input("Clock Out Time", value=None)
                
            edit_daily_log = st.text_area("Daily Log", max_chars=150)

            save_button = st.form_submit_button("Save Record")
            delete_button = st.form_submit_button("Delete Record")
            st.markdown("📌 To **Delete a Record**, only fill **Date** and **Select Employee** fields")

            formatted_date = edit_date.strftime("%d/%m/%Y")

            if save_button:
                existing_record = attendance_df[
                    (attendance_df["Date"] == formatted_date) &
                    (attendance_df["EmployeeID"].astype(str) == edit_employee_id)
                ].index

                new_record = {
                    "Date": formatted_date,
                    "EmployeeID": edit_employee_id,
                    "ClockIn": edit_clock_in.strftime("%H:%M:%S") if edit_clock_in else None,
                    "ClockOut": edit_clock_out.strftime("%H:%M:%S") if edit_clock_out else None,
                    "DailyLog": edit_daily_log
                }

                if not existing_record.empty:
                    attendance_df.loc[existing_record[0]] = new_record
                else:
                    attendance_df = pd.concat([attendance_df, pd.DataFrame([new_record])], ignore_index=True)

                if update_github_json(FILE_PATHS["attendance"], attendance_df.to_dict(orient="records"), attendance_sha):
                    st.success("✅ Record successfully saved.")
                    st.rerun()
                else:
                    st.error("❌ Failed to save to GitHub.")

            elif delete_button:
                existing_record = attendance_df[
                    (attendance_df["Date"] == formatted_date) &
                    (attendance_df["EmployeeID"].astype(str) == edit_employee_id)
                ].index
                
                if not existing_record.empty:
                    attendance_df.drop(existing_record, inplace=True)
                    
                    if update_github_json(FILE_PATHS["attendance"], attendance_df.to_dict(orient="records"), attendance_sha):
                        st.success("✅ Record successfully deleted.")
                        st.rerun()
                    else:
                        st.error("❌ Failed to save to GitHub.")
                else:
                    st.warning("⚠️ Record not found.")

        # Attendance Report
        st.markdown("---")
        st.subheader("📅 Attendance Report")

        # Create employee lookup table
        employee_lookup = employee_df.copy()
        employee_lookup["EmployeeID"] = employee_lookup["EmployeeID"].astype(str)

        # Create display dataframe with employee names
        report_df = attendance_df.copy()
        report_df["EmployeeID"] = report_df["EmployeeID"].astype(str)
        report_df = pd.merge(report_df, employee_lookup[["EmployeeID", "Name"]], on="EmployeeID", how="left")

        # Report filters
        name_filter = st.selectbox("🔎 Filter by Name", ["(All)"] + sorted(employee_df["Name"].unique()))
        department_filter = st.selectbox("🏢 Filter by Department", ["(All)"] + sorted(employee_df["Department"].unique()))

        if name_filter != "(All)":
            report_df = report_df[report_df["Name"] == name_filter]
            
        if department_filter != "(All)":
            dept_employees = employee_df[employee_df["Department"] == department_filter]
            dept_employee_ids = dept_employees["EmployeeID"].astype(str).unique()
            report_df = report_df[report_df["EmployeeID"].isin(dept_employee_ids)]

        report_display_df = report_df[["Date", "EmployeeID", "Name", "ClockIn", "ClockOut", "DailyLog"]]

        # Excel download functionality
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            report_display_df.to_excel(writer, index=False, sheet_name='Attendance')
        excel_buffer.seek(0)

        st.download_button(
            label="📥 Download Excel Report (.xlsx)",
            data=excel_buffer,
            file_name="EmployeeAttendanceReport.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.dataframe(report_display_df)

# === Manage User Page ===
elif selected_page == "Manage User":
    st.title("👥 User Management")
    
    # Admin authentication
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False

    if not st.session_state.admin_authenticated:
        st.markdown("---")
        st.subheader("🔒 Admin Authentication")
        admin_pin_input = st.text_input("Enter PIN for Admin access:", type="password")
        
        if admin_pin_input == ADMIN_PIN:
            st.success("✅ Access granted.")
            st.session_state.admin_authenticated = True
            st.rerun()
        elif admin_pin_input:
            st.error("❌ Incorrect PIN.")
    else:
        st.success("✅ Logged in as Administrator")
        st.markdown("---")
        
        # Add new employee
        st.subheader("➕ Add New Employee")
        with st.form("add_employee_form"):
            new_employee_id = st.text_input("Employee ID")
            new_employee_name = st.text_input("Full Name")
            new_employee_dept = st.text_input("Department")
            add_button = st.form_submit_button("Add Employee")

            if add_button:
                if not new_employee_id.isdigit():
                    st.error("❌ Employee ID must be numeric.")
                elif new_employee_id in employee_df["EmployeeID"].astype(str).values:
                    st.error("❌ Employee ID already exists!")
                elif not new_employee_name.strip() or not new_employee_dept.strip():
                    st.error("❌ All fields must be filled.")
                else:
                    new_employee = pd.DataFrame([{
                        "EmployeeID": new_employee_id,
                        "Name": new_employee_name.strip().upper(),
                        "Department": new_employee_dept.strip().upper()
                    }])
                    
                    updated_employee_df = pd.concat([employee_df, new_employee], ignore_index=True)
                    
                    if update_github_json(FILE_PATHS["employee"], updated_employee_df.to_dict(orient="records"), employee_sha):
                        st.success("✅ Employee added successfully.")
                        st.rerun()
                    else:
                        st.error("❌ Failed to save to GitHub.")

        # Delete employee
        st.markdown("---")
        st.subheader("🗑 Remove Employee")
        employee_df["DisplayName"] = employee_df["EmployeeID"].astype(str) + " - " + employee_df["Name"]
        employee_to_delete = st.selectbox("Select Employee to Remove", employee_df["DisplayName"])
        employee_id_to_delete = employee_to_delete.split(" - ")[0]

        if st.button("Remove Selected Employee"):
            employee_name = employee_df[employee_df["EmployeeID"].astype(str) == employee_id_to_delete]["Name"].values[0]
            updated_employee_df = employee_df[employee_df["EmployeeID"].astype(str) != employee_id_to_delete]
            
            if update_github_json(FILE_PATHS["employee"], updated_employee_df.to_dict(orient="records"), employee_sha):
                st.success(f"✅ Employee '{employee_name}' (ID: {employee_id_to_delete}) has been removed.")
                st.rerun()
            else:
                st.error("❌ Failed to save to GitHub.")

        # Employee directory
        st.markdown("---")
        st.subheader("📋 Employee Directory")
        name_filter = st.selectbox("🔎 Filter by Employee Name", ["(All)"] + sorted(employee_df["Name"].unique()))
        department_filter = st.selectbox("🏢 Filter by Department", ["(All)"] + sorted(employee_df["Department"].unique()))

        filtered_employees = employee_df.copy()
        if name_filter != "(All)":
            filtered_employees = filtered_employees[filtered_employees["Name"] == name_filter]
        if department_filter != "(All)":
            filtered_employees = filtered_employees[filtered_employees["Department"] == department_filter]

        # Calculate attendance statistics
        attendance_counts = attendance_df[attendance_df["DailyLog"].notna()]\
            .groupby("EmployeeID")\
            .size()\
            .reset_index(name="AttendanceCount")

        # Ensure matching types for merging
        attendance_counts["EmployeeID"] = attendance_counts["EmployeeID"].astype(str)
        filtered_employees["EmployeeID"] = filtered_employees["EmployeeID"].astype(str)

        # Merge statistics with employee data
        employee_report = pd.merge(
            filtered_employees,
            attendance_counts,
            on="EmployeeID",
            how="left"
        ).fillna({"AttendanceCount": 0})

        employee_report["AttendanceCount"] = employee_report["AttendanceCount"].astype(int)

        st.dataframe(employee_report.drop(columns=["DisplayName"]))