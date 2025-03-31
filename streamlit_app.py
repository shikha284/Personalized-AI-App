import requests
import streamlit as st
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from zoom_utils import summarize_meetings, transcripts  # ensure you imported this
import pandas as pd
from zoom_utils import (
    schedule_zoom_meeting,
    add_to_calendar,
    send_email_reminder,
    authenticate_google,
    summarize_latest_meetings
)

st.set_page_config(page_title="Shikha's Personalized AI Assistant")
st.title("🤖 Shikha's Personalized AI Assistant")

# Step 0: Google Authorization
if not st.session_state.get("google_authenticated"):
    st.subheader("🔐 Google Authorization Required")
    silent_auth = authenticate_google(interactive=False)
    if silent_auth:
        st.session_state.google_authenticated = True
        st.rerun()

    if "auth_phase" not in st.session_state:
        auth_result = authenticate_google(interactive=True)
        if isinstance(auth_result, tuple):
            auth_url, code_key = auth_result
            st.session_state.auth_url = auth_url
            st.session_state.code_key = code_key
            st.session_state.auth_phase = "prompt_code"
        else:
            st.error("⚠️ Unexpected authentication return type.")
            st.stop()

    if st.session_state.get("auth_phase") == "prompt_code":
        st.markdown(f"[Click here to authorize Google access]({st.session_state.auth_url})")
        auth_code = st.text_input("Paste the authorization code here:", key=st.session_state.code_key)
        if auth_code:
            success = authenticate_google(interactive=True, auth_code=auth_code)
            if success:
                st.session_state.google_authenticated = True
                st.rerun()
            else:
                st.error("❌ Authorization failed. Please try again.")
    st.stop()

# Step 1: Instruction Options
if "step" not in st.session_state:
    st.session_state.step = "greet"

if st.session_state.step == "greet":
    st.write("Hi there! 👋 I'm your AI Assistant. What would you like me to do today?")
    user_input = st.text_input("Your instruction:")
    if user_input:
        user_input_lower = user_input.lower()
        if "schedule" in user_input_lower and "zoom" in user_input_lower:
            st.session_state.step = "collect_zoom_info"
        elif "summarize meeting" in user_input_lower:
            st.session_state.step = "summarize_meeting"
        else:
            st.warning("Sorry, I can currently only help with Zoom scheduling and meeting summaries.")

# Step 2: Meeting Scheduler
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
                    body={
                        "time": f"{start_datetime.strftime('%Y-%m-%d %I:%M %p')} ({timezone})",
                        "link": zoom_link
                    },
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

# Step 3: Meeting Summarization & Sentiment
if st.session_state.step == "summarize_meeting":
    st.subheader("📝 Summarize Recent Meeting")

    num = st.number_input("Number of recent meetings to summarize", min_value=1, max_value=5, value=1)
    if st.button("🔍 Summarize"):
        summary, sentiment = summarize_latest_meetings(num_meetings=num)
        if summary:
            st.markdown("### ✅ Summary:")
            st.info(summary)

            st.markdown("### 📊 Sentiment:")
            st.success(sentiment)
        else:
            st.warning("⚠️ No meeting data found or summary generation failed.")

    st.button("🔙 Go Back", on_click=lambda: st.session_state.update({"step": "greet"}))

# After meeting scheduling section
st.header("📊 Meeting Insights Dashboard")

# Filter options
view_mode = st.radio("How do you want to explore meetings?", ["Latest", "By Title", "By Date"], horizontal=True)

filtered_df = transcripts.copy()

if view_mode == "By Title":
    titles = filtered_df["title"].dropna().unique().tolist()
    selected_title = st.selectbox("Select Meeting Title", titles)
    filtered_df = filtered_df[filtered_df["title"] == selected_title]

elif view_mode == "By Date":
    selected_date = st.date_input("Select a date to filter meetings")
    filtered_df = filtered_df[filtered_df["date"].dt.date == selected_date]

# Number of meetings to summarize
num_meetings = st.slider("How many meetings to summarize?", 1, 5, 1)

if st.button("📄 Generate Meeting Summary"):
    if filtered_df.empty:
        st.warning("No meetings found for the selected filters.")
    else:
        summary = summarize_meetings(filtered_df, num_meetings=num_meetings)
        st.markdown("### 📝 Summary")
        st.markdown(summary)

        # Optionally include sentiment later here too