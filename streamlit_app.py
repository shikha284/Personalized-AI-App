import requests
import streamlit as st
from datetime import datetime
from zoom_utils import (
    schedule_zoom_meeting,
    send_email_reminder,
    authenticate_google,
    summarize_meetings,
    transcripts,
    add_to_calendar
)

st.set_page_config(page_title="Shikha's Personalized AI Assistant")
st.title("🤖 Shikha's Personalized AI Assistant")

# 🔐 Google Auth
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

# 🧠 Intent
if "step" not in st.session_state:
    st.session_state.step = "greet"

if st.session_state.step == "greet":
    st.write("Hi there! 👋 I'm your AI Assistant. What would you like me to do today?")
    user_input = st.text_input("Your instruction:")
    if user_input:
        normalized = user_input.lower().strip()
        if "schedule" in normalized and "zoom" in normalized:
            st.session_state.step = "collect_zoom_info"
        elif "summarize" in normalized or "meeting" in normalized:
            st.session_state.step = "summarize_meeting"
        else:
            st.warning("Try: 'schedule zoom meeting' or 'summarize recent meeting'.")

# 📅 Zoom Meeting Scheduler
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
            start_dt = datetime.combine(date, time)
            zoom_link, zoom_status = schedule_zoom_meeting(topic, start_dt, duration, timezone)
            if zoom_link:
                cal_link = add_to_calendar(topic, start_dt, duration, timezone, zoom_link)
                email_sent = send_email_reminder(
                    subject=f"📌 Zoom Meeting: {topic}",
                    body={"time": f"{start_dt.strftime('%Y-%m-%d %I:%M %p')} ({timezone})", "link": zoom_link},
                    recipients=[e.strip() for e in emails.split(",")]
                )

                st.success("✅ Zoom Meeting Scheduled Successfully!")
                st.markdown(f"[🔗 Join Zoom Meeting]({zoom_link})")
                st.markdown(f"[📅 View in Calendar]({cal_link})")
                st.success("📧 Email invitations sent!" if email_sent else "⚠️ Email sending failed.")
            else:
                st.error(zoom_status)
            st.session_state.step = "greet"

# 📊 Summarize & Analyze Meetings
if st.session_state.step == "summarize_meeting":
    st.subheader("📑 Summarize & Analyze Meetings")

    view_mode = st.radio("Filter by", ["Latest", "By Title", "By Date"], horizontal=True)
    filtered_df = transcripts.copy()

    if view_mode == "By Title":
        titles = filtered_df["title"].dropna().unique().tolist()
        selected_title = st.selectbox("Select Title", titles)
        filtered_df = filtered_df[filtered_df["title"] == selected_title]

    elif view_mode == "By Date":
        selected_date = st.date_input("Pick a Date")
        filtered_df = filtered_df[filtered_df["created_at"].dt.date == selected_date]

    elif view_mode == "Latest":
        filtered_df = filtered_df.sort_values(by="created_at", ascending=False).head(1)

    if st.button("🧾 Generate Summary & Sentiment"):
        if filtered_df.empty:
            st.warning("⚠️ No transcripts found for this filter.")
        else:
            summary = summarize_meetings(filtered_df, num_meetings=1)
            content = " ".join(filtered_df["content"].tolist())[:4000]
            sentiment = summarize_latest_meetings(content_override=content)[1]

            st.markdown("### ✅ Summary")
            st.info(summary)
            st.markdown("### 💬 Sentiment")
            st.success(sentiment if sentiment else "No sentiment returned.")

    if st.button("🔙 Go Back"):
        st.session_state.step = "greet"
