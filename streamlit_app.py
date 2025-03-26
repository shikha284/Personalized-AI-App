
import json
import streamlit as st

st.title("Personalized LLaMA 3 App")
st.write("App is loading...")

with open("gmail_credentials.json", "w") as f:
    json.dump(dict(st.secrets["gmail_cred"]), f)

with open("credentials.json", "w") as f:
    json.dump(dict(st.secrets["google_service"]), f)

from google.oauth2 import service_account
from googleapiclient.discovery import build
import streamlit as st

@st.cache_resource
def get_gmail_service():
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gmail_cred"],
        scopes=["https://www.googleapis.com/auth/gmail.send"]
    )
    return build("gmail", "v1", credentials=creds)

@st.cache_resource
def get_calendar_service():
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["google_service"],
        scopes=["https://www.googleapis.com/auth/calendar"]
    )
    return build("calendar", "v3", credentials=creds)

import os
import base64
import pytz
import psycopg2
import requests
import json
import pandas as pd
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from groq import Groq

# 🔹 AI API Key for Groq (Shikha's AI)
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

# 🔹 Zoom API Credentials
ZOOM_CLIENT_ID = "kv3Bn6lRTqxqZ85vDAZVA"
ZOOM_CLIENT_SECRET = "YiNVySGuc1Gdra1t6xfTd4PcofEpDv64"
ZOOM_ACCOUNT_ID = "4YnZfrcBQ3Cm51HgqtFNjw"

# 🔹 Generate Base64 encoded credentials for Zoom
auth_string = f"{ZOOM_CLIENT_ID}:{ZOOM_CLIENT_SECRET}"
auth_base64 = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")

# ✅ Get Zoom OAuth Token
def get_zoom_access_token():
    """Retrieve a Zoom API access token."""
    auth_url = "https://zoom.us/oauth/token"
    auth_headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    auth_payload = {"grant_type": "account_credentials", "account_id": ZOOM_ACCOUNT_ID}

    response = requests.post(auth_url, headers=auth_headers, data=auth_payload)

    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        print(f"❌ Error Fetching Zoom Token: {response.json()}")
        return None

# ✅ Schedule Zoom Meeting
def schedule_zoom_meeting(topic, start_time, duration, time_zone):
    """Schedules a Zoom meeting and returns the join link."""
    access_token = get_zoom_access_token()
    if not access_token:
        return "❌ Failed to get Zoom access token."

    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    user_tz = pytz.timezone(time_zone)
    start_time_user_tz = user_tz.localize(start_time)
    start_time_utc = start_time_user_tz.astimezone(pytz.utc)
    
    zoom_formatted_time = start_time_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    meeting_data = {
        "topic": topic,
        "type": 2,
        "start_time": zoom_formatted_time,
        "duration": duration,
        "timezone": "UTC",
        "agenda": f"{topic} discussion",
        "settings": {
            "host_video": True,  
            "participant_video": True,  
            "mute_upon_entry": True,  
            "audio": "both",  
            "auto_recording": "cloud"  
        }
    }

    zoom_api_url = "https://api.zoom.us/v2/users/me/meetings"
    response = requests.post(zoom_api_url, headers=headers, json=meeting_data)

    if response.status_code == 201:
        meeting_info = response.json()
        return meeting_info["join_url"]
    else:
        return f"❌ Error Scheduling Meeting: {response.json()}"

# ✅ Add Meeting to Google Calendar
def add_meeting_to_calendar(event_name, start_time, duration, time_zone, zoom_link):
    """Adds the scheduled Zoom meeting to Google Calendar."""
    service = build("calendar", "v3", credentials=authenticate_google())

    start_datetime = start_time.isoformat()
    end_datetime = (start_time + timedelta(minutes=duration)).isoformat()

    event_body = {
        "summary": event_name,
        "location": "Online via Zoom",
        "description": f"Join the Zoom Meeting: {zoom_link}",
        "start": {"dateTime": start_datetime, "timeZone": time_zone},
        "end": {"dateTime": end_datetime, "timeZone": time_zone},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "email", "minutes": 30}, {"method": "popup", "minutes": 10}]
        }
    }

    event = service.events().insert(calendarId="primary", body=event_body).execute()
    return f"✅ Meeting added to Google Calendar: {event.get('htmlLink')}"

# ✅ AI Assistant
def ask_ai_assistant():
    print("\n✨ Welcome to **Shikha's AI Assistant!** 🚀")

    while True:
        user_question = input("\n🟢 **You:** ").lower().strip()

        if user_question in ["exit", "quit", "bye"]:
            print("🔴 **AI Assistant:** Goodbye! 👋")
            break

        if "schedule zoom" in user_question:
            print("\n📅 **Let's schedule a Zoom meeting!** 🎯")

            topic = input("🔹 Enter meeting topic: ").strip()
            date_str = input("📆 Enter meeting date (YYYY-MM-DD HH:MM AM/PM): ").strip()
            time_zone = input("🌍 Enter your time zone (e.g., America/Los_Angeles): ").strip()

            try:
                start_time = datetime.strptime(date_str, "%Y-%m-%d %I:%M %p")
            except ValueError:
                print("❌ **Invalid date format!** Use 'YYYY-MM-DD HH:MM AM/PM'.")
                continue

            if time_zone not in pytz.all_timezones:
                print("❌ **Invalid Time Zone!** Refer to `pytz.all_timezones` for valid names.")
                continue

            duration = int(input("⏳ Enter meeting duration (minutes): ").strip())
            participants = input("📧 Enter participant emails (comma-separated): ").split(",")

            zoom_link = schedule_zoom_meeting(topic, start_time, duration, time_zone)
            if "❌" in zoom_link:
                print(f"❌ Failed to schedule Zoom meeting: {zoom_link}")
                continue

            calendar_status = add_meeting_to_calendar(topic, start_time, duration, time_zone, zoom_link)
            email_subject = f"Reminder: Zoom Meeting - {topic}"
            email_body = f"Your Zoom meeting is scheduled at {date_str} ({time_zone}).\nJoin here: {zoom_link}"
            send_email_reminder(participants, email_subject, email_body)

            print(f"✅ Zoom Meeting Scheduled: {zoom_link}")
            print(calendar_status)

# ✅ Start the AI Assistant
ask_ai_assistant()

