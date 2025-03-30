import json
import streamlit as st
from datetime import datetime
from zoom_utils import schedule_zoom_meeting, add_to_calendar, send_email_reminder

# 🔐 Save secrets to files if needed (useful for legacy Google APIs)
with open("gmail_credentials.json", "w") as f:
    json.dump(dict(st.secrets["gmail_cred"]), f)

with open("credentials.json", "w") as f:
    json.dump(dict(st.secrets["google_service_account"]), f)

# 🌟 UI
st.title("📅 Zoom Meeting Scheduler + AI Assistant")
st.subheader("Schedule a new meeting")

topic = st.text_input("Meeting Topic")
date = st.date_input("Select Date")
time = st.time_input("Select Time")
duration = st.number_input("Duration (minutes)", min_value=15, max_value=240, value=30)
timezone = st.selectbox("Time Zone", ["Asia/Kolkata", "America/Los_Angeles", "UTC"])
emails = st.text_area("Participant Emails (comma-separated)")

if st.button("📆 Schedule Zoom Meeting"):
    if not topic or not emails:
        st.error("Please fill in all the fields.")
    else:
        start_datetime = datetime.combine(date, time)
        zoom_link, zoom_status = schedule_zoom_meeting(topic, start_datetime, duration, timezone)

        if zoom_link:
            cal_link = add_to_calendar(topic, start_datetime, duration, timezone, zoom_link)
            email_sent = send_email_reminder(
                f"📌 Zoom Meeting: {topic}",
                f"Join Zoom Meeting: {zoom_link} at {start_datetime.strftime('%Y-%m-%d %H:%M')} ({timezone})",
                recipients=emails.split(",")
            )
            st.success("✅ Zoom Meeting Scheduled Successfully!")
            st.markdown(f"[📅 View on Google Calendar]({cal_link})")
            if email_sent:
                st.success("📧 Email Invitations Sent Successfully!")
            else:
                st.warning("⚠️ Email Sending Failed via Mailjet.")
        else:
            st.error(zoom_status)
