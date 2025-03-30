import streamlit as st
from datetime import datetime
from zoom_utils import (
    schedule_zoom_meeting,
    add_to_calendar,
    send_email_reminder,
    authenticate_google
)

st.set_page_config(page_title="Shikha's Personalized AI Assistant")

st.title("🤖 Shikha's Personalized AI Assistant")

# Step 0: Check and handle Google authorization
if not st.session_state.get("google_authenticated"):
    st.subheader("🔐 Google Authorization Required")
    auth_url, code_key = authenticate_google(interactive=True)
    st.markdown(f"[Click here to authorize Google access]({auth_url})")
    auth_code = st.text_input("Paste the authorization code here:", key=code_key)

    if auth_code:
        success = authenticate_google(interactive=True, auth_code=auth_code)
        if success:
            st.session_state.google_authenticated = True
            st.rerun()
        else:
            st.error("❌ Authorization failed. Please try again.")
    st.stop()

# Step 1: Greet and accept instruction
if "step" not in st.session_state:
    st.session_state.step = "greet"

if st.session_state.step == "greet":
    st.write("Hi there! 👋 I'm your AI Assistant. What would you like me to do today?")
    user_input = st.text_input("Your instruction:")
    if user_input:
        if "schedule" in user_input.lower() and "zoom" in user_input.lower():
            st.session_state.step = "collect_zoom_info"
        else:
            st.warning("Sorry, I can currently only help with Zoom meeting scheduling.")

# Step 2: Schedule meeting flow
if st.session_state.step == "collect_zoom_info":
    st.subheader("📅 Let's schedule your Zoom Meeting!")

    topic = st.text_input("Meeting Topic")
    date = st.date_input("Meeting Date")
    time = st.time_input("Meeting Time")
    duration = st.number_input("Duration (minutes)", min_value=15, max_value=240, value=30)
    timezone = st.selectbox("Time Zone", ["Asia/Kolkata", "America/Los_Angeles", "UTC"])
    emails = st.text_area("Participant Emails (comma-separated)")

    if st.button("🚀 Confirm & Schedule"):
        if not topic or not emails:
            st.error("Please fill in all required fields.")
        else:
            start_datetime = datetime.combine(date, time)
            zoom_link, zoom_status = schedule_zoom_meeting(topic, start_datetime, duration, timezone)

            if zoom_link:
                cal_link = add_to_calendar(topic, start_datetime, duration, timezone, zoom_link)
                email_sent = send_email_reminder(
                    subject=f"📌 Zoom Meeting: {topic}",
                    body=f"Join Zoom Meeting: {zoom_link} at {start_datetime.strftime('%Y-%m-%d %H:%M')} ({timezone})",
                    recipients=[email.strip() for email in emails.split(",")]
                )
                st.success("✅ Zoom Meeting Scheduled Successfully!")
                st.markdown(f"[🔗 Join Zoom Meeting]({zoom_link})")
                st.markdown(f"[📅 View in Calendar]({cal_link})")
                if email_sent:
                    st.success("📧 Email invitations sent via Gmail!")
                else:
                    st.warning("⚠️ Email sending failed.")
            else:
                st.error(zoom_status)

            st.session_state.step = "greet"
