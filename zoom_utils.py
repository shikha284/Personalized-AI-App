import os
import base64
import pytz
import requests
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import streamlit as st

# Zoom credentials from secrets
ZOOM_CLIENT_ID = st.secrets["zoom"]["client_id"]
ZOOM_CLIENT_SECRET = st.secrets["zoom"]["client_secret"]
ZOOM_ACCOUNT_ID = st.secrets["zoom"]["account_id"]

# Mailjet credentials
MAILJET_API_KEY = st.secrets["mailjet"]["api_key"]
MAILJET_SECRET_KEY = st.secrets["mailjet"]["secret_key"]

# Google Calendar credentials (service account)
from google.oauth2 import service_account
GOOGLE_CREDS = service_account.Credentials.from_service_account_info(st.secrets["google_service_account"])
calendar_service = build("calendar", "v3", credentials=GOOGLE_CREDS)

# 🔹 Zoom Token
def get_zoom_access_token():
    auth_string = f"{ZOOM_CLIENT_ID}:{ZOOM_CLIENT_SECRET}"
    auth_base64 = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
    headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "account_credentials",
        "account_id": ZOOM_ACCOUNT_ID
    }
    response = requests.post("https://zoom.us/oauth/token", headers=headers, data=data)
    return response.json().get("access_token")

# 🔹 Schedule Zoom
def schedule_zoom_meeting(topic, start_time, duration, time_zone):
    access_token = get_zoom_access_token()
    if not access_token:
        return None, "❌ Zoom access token error."
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    tz = pytz.timezone(time_zone)
    zoom_time = tz.localize(start_time).astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    meeting_data = {
        "topic": topic,
        "type": 2,
        "start_time": zoom_time,
        "duration": duration,
        "timezone": "UTC",
        "agenda": f"{topic} discussion",
        "settings": {
            "host_video": True,
            "participant_video": True,
            "mute_upon_entry": True,
            "auto_recording": "cloud"
        }
    }

    res = requests.post("https://api.zoom.us/v2/users/me/meetings", headers=headers, json=meeting_data)
    if res.status_code == 201:
        return res.json().get("join_url"), "✅ Zoom meeting scheduled!"
    else:
        return None, f"❌ Zoom scheduling failed: {res.json()}"

# 🔹 Add to Calendar
def add_to_calendar(topic, start_time, duration, time_zone, zoom_link):
    end_time = start_time + timedelta(minutes=duration)
    event = {
        "summary": topic,
        "location": "Zoom",
        "description": f"Join Zoom Meeting: {zoom_link}",
        "start": {"dateTime": start_time.isoformat(), "timeZone": time_zone},
        "end": {"dateTime": end_time.isoformat(), "timeZone": time_zone},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 10}]
        }
    }
    created_event = calendar_service.events().insert(calendarId="primary", body=event).execute()
    return created_event.get("htmlLink")

# 🔹 Mailjet Email Reminder
def send_email_reminder(subject, body, recipients):
    url = "https://api.mailjet.com/v3.1/send"
    headers = {"Content-Type": "application/json"}
    data = {
        "Messages": [
            {
                "From": {
                    "Email": "youremail@example.com",
                    "Name": "Shikha Assistant"
                },
                "To": [{"Email": email.strip(), "Name": email.strip().split("@")[0]} for email in recipients],
                "Subject": subject,
                "TextPart": body,
                "HTMLPart": f"<p>{body}</p>"
            }
        ]
    }
    response = requests.post(url, auth=(MAILJET_API_KEY, MAILJET_SECRET_KEY), headers=headers, json=data)
    return response.status_code == 200

