
import json
import streamlit as st

with open("gmail_credentials.json", "w") as f:
    json.dump(dict(st.secrets["gmail_cred"]), f)

with open("credentials.json", "w") as f:
    json.dump(dict(st.secrets["google_service"]), f)


st.title("Personalized LLaMA 3 App")
st.write("App is loading...")

import streamlit as st
from datetime import datetime
from zoom_utils import schedule_zoom_meeting, add_to_calendar, send_email_reminder

st.title("📅 Zoom Meeting Scheduler + AI Assistant")

st.subheader("Step 1: Meeting Details")
topic = st.text_input("Meeting Topic")
date = st.date_input("Date")
time = st.time_input("Time")
duration = st.number_input("Duration (minutes)", min_value=15, max_value=240, value=30)
timezone = st.selectbox("Time Zone", ["Asia/Kolkata", "America/Los_Angeles", "UTC"])
emails = st.text_area("Participant Emails (comma-separated)")

if st.button("Schedule Meeting"):
    if not topic or not emails:
        st.error("Please fill all fields.")
    else:
        start_datetime = datetime.combine(date, time)
        zoom_link, zoom_status = schedule_zoom_meeting(topic, start_datetime, duration, timezone)

        if zoom_link:
            cal_link = add_to_calendar(topic, start_datetime, duration, timezone, zoom_link)
            email_sent = send_email_reminder(
                f"Zoom Meeting: {topic}",
                f"Join here: {zoom_link} at {start_datetime.strftime('%Y-%m-%d %H:%M')} ({timezone})",
                recipients=emails.split(",")
            )
            st.success("✅ Zoom Meeting Scheduled")
            st.markdown(f"[📅 Calendar Event Link]({cal_link})")
            if email_sent:
                st.success("📧 Email invitations sent!")
            else:
                st.warning("⚠️ Email sending failed.")
        else:
            st.error(zoom_status)
