import streamlit as st
from datetime import datetime
from gmail_utils import fetch_latest_email, summarize_email, draft_reply
from zoom_utils import (
    schedule_zoom_meeting,
    send_email_reminder,
    authenticate_google,
    summarize_meetings,
    summarize_latest_meeting,
    transcripts,
    add_to_calendar
)

# ✅ Streamlit config must be first
st.set_page_config(page_title="Shikha's Personalized AI Assistant", page_icon="🤖")

# === Title & Auth ===
st.title("🤖 Shikha's Personalized AI Assistant")

if not st.session_state.get("google_authenticated"):
    st.subheader("🔐 Google Authorization Required")
    silent_auth = authenticate_google(interactive=False)
    if silent_auth:
        st.session_state.google_authenticated = True
        st.rerun()

    auth_result = authenticate_google(interactive=True)
    if isinstance(auth_result, tuple):
        auth_url, code_key = auth_result
        st.session_state.auth_url = auth_url
        st.session_state.code_key = code_key
        st.session_state.auth_phase = "prompt_code"
    else:
        st.error("⚠️ Authentication failed.")
        st.stop()

    if st.session_state.get("auth_phase") == "prompt_code":
        st.markdown(f"[Click here to authorize Google access]({st.session_state.auth_url})")
        auth_code = st.text_input("Paste the code here:", key=st.session_state.code_key)
        if auth_code:
            success = authenticate_google(interactive=True, auth_code=auth_code)
            if success:
                st.session_state.google_authenticated = True
                st.rerun()
            else:
                st.error("❌ Authorization failed. Try again.")
    st.stop()

# === Navigation ===
if "step" not in st.session_state:
    st.session_state.step = "greet"

if st.session_state.step == "greet":
    st.write("Hi there! 👋 I'm your AI Assistant. What would you like me to do today?")
    user_input = st.text_input("Your instruction:")
    if user_input:
        normalized = user_input.lower()
        if "schedule" in normalized and "zoom" in normalized:
            st.session_state.step = "collect_zoom_info"
        elif "summarize" in normalized or "email" in normalized:
            st.session_state.step = "email_assistant"
        else:
            st.warning("Try: 'schedule zoom meeting' or 'summarize email'.")

# === Zoom Scheduler ===
if st.session_state.step == "collect_zoom_info":
    st.subheader("📅 Schedule Zoom Meeting")
    topic = st.text_input("Meeting Topic")
    date = st.date_input("Date")
    time = st.time_input("Time")
    duration = st.number_input("Duration (minutes)", min_value=15, max_value=240, value=30)
    timezone = st.selectbox("Time Zone", ["Asia/Kolkata", "America/Los_Angeles", "UTC"])
    emails = st.text_area("Participant Emails (comma-separated)")

    if st.button("🚀 Schedule"):
        if topic and emails:
            start_datetime = datetime.combine(date, time)
            zoom_link, zoom_status = schedule_zoom_meeting(topic, start_datetime, duration, timezone)
            if zoom_link:
                cal_link = add_to_calendar(topic, start_datetime, duration, timezone, zoom_link)
                email_sent = send_email_reminder(
                    f"📌 Zoom Meeting: {topic}",
                    {"time": start_datetime.strftime('%Y-%m-%d %I:%M %p'), "link": zoom_link},
                    [e.strip() for e in emails.split(",")]
                )
                st.success("✅ Zoom Meeting Scheduled!")
                st.markdown(f"[🔗 Join Meeting]({zoom_link})")
                st.markdown(f"[📅 View in Calendar]({cal_link})")
                st.success("📧 Email sent!" if email_sent else "⚠️ Email failed.")
            else:
                st.error(zoom_status)
            st.session_state.step = "greet"
        else:
            st.error("Please complete all fields.")

# === Meeting Summarization ===
if st.session_state.step == "summarize_meeting":
    st.subheader("📑 Summarize & Analyze Meetings")
    view_mode = st.radio("Filter by", ["Latest", "By Date"], horizontal=True)
    filtered_df = transcripts.copy()

    if view_mode == "By Date":
        selected_date = st.date_input("Pick a Date")
        filtered_df = filtered_df[filtered_df["created_at"].dt.date == selected_date]

    if st.button("📄 Generate Summary & Sentiment"):
        if filtered_df.empty:
            st.warning("⚠️ No transcripts found for this filter.")
        else:
            summary, sentiment = summarize_meetings(filtered_df)
            st.markdown("### ✅ Summary")
            st.info(summary or "No summary generated.")
            st.markdown("### 💬 Sentiment")
            st.success(sentiment or "No sentiment detected.")

    if st.button("🔙 Go Back"):
        st.session_state.step = "greet"

# === Gmail Assistant ===
if st.session_state.step == "email_assistant":
    st.subheader("📧 Gmail AI Assistant")
    option = st.selectbox("Choose Action", ["Summarize Latest Email", "Draft Reply to Latest Email"])

    email = fetch_latest_email()
    if email:
        st.subheader("📩 Latest Email")
        st.markdown(f"**From:** {email['sender']}")
        st.markdown(f"**Subject:** {email['subject']}")
        st.markdown(f"**Date:** {email['date']}")
        st.text_area("Body", email['body'], height=200)

        st.subheader("✍️ Draft Your Reply")
        user_input = st.text_input("What do you want to say?")
    
        if user_input:
            reply = draft_reply(email, user_input)
            st.text_area("Drafted Reply", reply, height=200)

            if st.button("✅ Send Email"):
                result = send_reply_email(reply, email)
                st.success(result)

    elif option == "Draft Reply to Latest Email":
        user_message = st.text_area("What do you want to say?")
        if st.button("✍️ Draft Reply"):
            reply = draft_reply(email, user_message)
            st.subheader("💬 Suggested Reply")
            st.info(reply)

    if st.button("🔙 Return to Main Menu"):
        st.session_state.step = "greet"