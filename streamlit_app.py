import streamlit as st
import time
from datetime import datetime
from gmail_utils import fetch_latest_email, summarize_email, draft_reply, send_reply_email
from zoom_utils import (
    schedule_zoom_meeting,
    send_email_reminder,
    authenticate_google,
    summarize_meetings,
    summarize_latest_meeting,
    get_transcripts,
    add_to_calendar
)
from eval_utils import g_eval, if_eval, halu_eval, truthful_qa_eval, q2_eval

st.set_page_config(page_title="Shikha's Personalized AI Assistant", page_icon="🤖")
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

if "step" not in st.session_state:
    st.session_state.step = "greet"

if st.session_state.step == "greet":
    st.write("Hi there! 👋 I'm your AI Assistant. What would you like me to do today?")
    user_input = st.text_input("Your instruction:")
    if user_input:
        normalized = user_input.lower()
        if "schedule" in normalized and "zoom" in normalized:
            st.session_state.step = "collect_zoom_info"
        elif "summarize zoom" in normalized:
            st.session_state.step = "summarize_meeting"
        elif "email" in normalized or "summarize" in normalized:
            st.session_state.step = "email_assistant"
        else:
            st.warning("Try: 'schedule zoom meeting' or 'summarize email'.")

if st.session_state.step == "collect_zoom_info":
    st.subheader("🗕️ Schedule Zoom Meeting")
    topic = st.text_input("Meeting Topic")
    date = st.date_input("Date")
    time_input = st.time_input("Time")
    duration = st.number_input("Duration (minutes)", min_value=15, max_value=240, value=30)
    timezone = st.selectbox("Time Zone", ["Asia/Kolkata", "America/Los_Angeles", "UTC"])
    emails = st.text_area("Participant Emails (comma-separated)")

    if st.button("🚀 Schedule"):
        if topic and emails:
            start_datetime = datetime.combine(date, time_input)
            zoom_link, zoom_status, zoom_time = schedule_zoom_meeting(topic, start_datetime, duration, timezone)
            if zoom_link:
                cal_link, cal_time = add_to_calendar(topic, start_datetime, duration, timezone, zoom_link)
                email_sent, email_time = send_email_reminder(
                    f"📌 Zoom Meeting: {topic}",
                    {"time": start_datetime.strftime('%Y-%m-%d %I:%M %p'), "link": zoom_link},
                    [e.strip() for e in emails.split(",")]
                )
                st.success("✅ Zoom Meeting Scheduled!")
                st.markdown(f"[🔗 Join Meeting]({zoom_link})")
                st.markdown(f"[📅 View in Calendar]({cal_link})")
                st.caption(f"⏱️ Zoom API Time: {zoom_time}s | Calendar: {cal_time}s | Email: {email_time}s")
            else:
                st.error(zoom_status)
            st.session_state.step = "greet"
        else:
            st.error("Please complete all fields.")

    if st.button("🔙 Return to Main Menu"):
        st.session_state.step = "greet"

if st.session_state.step == "email_assistant":
    st.subheader("📧 Gmail AI Assistant")
    email_action = st.selectbox("Choose Action", ["Show Latest Email", "Summarize Latest Email", "Draft Reply"])
    start_time = time.time()
    email = fetch_latest_email()

    if not email:
        st.error("❌ No emails found.")
    else:
        st.markdown(f"**From:** {email['sender']}")
        st.markdown(f"**Subject:** {email['subject']}")
        st.markdown(f"**Date:** {email['date']}")
        st.text_area("Body", email['body'], height=200)

        if email_action == "Summarize Latest Email":
            summary = summarize_email(email["body"])
            st.subheader("📌 Summary")
            st.info(summary)
            with st.expander("📊 Evaluation Metrics"):
                st.markdown("**G-Eval**")
                st.code(g_eval(summary, reference=email["body"]))
                st.markdown("**IFEval**")
                st.code(if_eval(summary, source=email["body"]))
                st.markdown("**Q² Evaluation**")
                st.code(q2_eval(summary, reference=email["body"]))

        elif email_action == "Draft Reply":
            st.subheader("✉️ Drafted Reply")
            user_intent = "Please reply professionally to this inquiry."
            reply = draft_reply(email, user_intent)
            st.text_area("Reply Draft", reply, height=200)

            input_struct = {
                "sender": email["sender"],
                "subject": email["subject"],
                "original_message": email["body"],
                "user_intent": user_intent
            }

            with st.expander("📊 Evaluation Metrics"):
                st.markdown("**HALUeval**")
                st.code(halu_eval(reply, input_struct))
                st.markdown("**IFEval**")
                st.code(if_eval(reply, source=email["body"]))
                st.markdown("**TruthfulQA**")
                st.code(truthful_qa_eval(reply))

            if st.button("✅ Send Reply"):
                status = send_reply_email(reply, email)
                st.success(status)

    end_time = time.time()
    st.caption(f"⏱️ Response Time: {round(end_time - start_time, 2)} seconds")

    if st.button("🔙 Return to Main Menu"):
        st.session_state.step = "greet"

if st.session_state.step == "summarize_meeting":
    st.subheader("📁 Summarize & Analyze Meetings")
    view_mode = st.radio("Filter by", ["Latest", "By Date"], horizontal=True)
    transcripts = get_transcripts()
    filtered_df = transcripts.copy()

    if view_mode == "By Date":
        selected_date = st.date_input("Pick a Date")
        filtered_df = filtered_df[filtered_df["created_at"].dt.date == selected_date]

    if st.button("📄 Generate Summary & Sentiment"):
        if filtered_df.empty:
            st.warning("⚠️ No transcripts found for this filter.")
        else:
            summary, sentiment, response_time = summarize_meetings(filtered_df)
            st.markdown("### ✅ Summary")
            st.info(summary or "No summary generated.")
            st.markdown("### 🔈 Sentiment")
            st.success(sentiment or "No sentiment detected.")
            st.caption(f"⏱️ Response Time: {response_time} seconds")

            with st.expander("📊 Evaluation Metrics"):
                joined_text = " ".join(filtered_df["content"].tolist())
                st.markdown("**G-Eval**")
                st.code(g_eval(summary, reference=joined_text))
                st.markdown("**IFEval**")
                st.code(if_eval(summary, source=joined_text))
                st.markdown("**TruthfulQA - Sentiment**")
                st.code(truthful_qa_eval(sentiment))
                st.markdown("**Q² Evaluation**")
                st.code(q2_eval(summary, reference=joined_text))

    if st.button("🔙 Return to Main Menu"):
        st.session_state.step = "greet"