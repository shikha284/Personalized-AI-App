import os
import base64
import pytz
import requests
import streamlit as st
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

# Zoom credentials
ZOOM_CLIENT_ID = st.secrets["zoom"]["client_id"]
ZOOM_CLIENT_SECRET = st.secrets["zoom"]["client_secret"]
ZOOM_ACCOUNT_ID = st.secrets["zoom"]["account_id"]

# Gmail + Calendar client OAuth credentials
CLIENT_CONFIG = {
    "web": dict(st.secrets["gmail_cred"])
}

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

# 🔹 Google OAuth Flow
def authenticate_google():
    flow = Flow.from_client_config(
        client_config=CLIENT_CONFIG,
        scopes=["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/gmail.send"],
        redirect_uri=CLIENT_CONFIG["web"]["redirect_uris"][0]
    )

    if "credentials" not in st.session_state:
        auth_url, _ = flow.authorization_url(prompt="consent")
        st.markdown(f"[Click here to authorize Google Access]({auth_url})")
        st.stop()

    creds = Credentials(**st.session_state.credentials)
    return creds

# 🔹 Schedule Zoom Meeting
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

# 🔹 Add to Google Calendar
def add_to_calendar(topic, start_time, duration, time_zone, zoom_link):
    creds = authenticate_google()
    calendar_service = build("calendar", "v3", credentials=creds)

    end_time = start_time + timedelta(minutes=duration)
    event = {
        "summary": topic,
        "location": "Zoom",
        "description": f"Join Zoom Meeting: {zoom_link}",
        "start": {"dateTime": start_time.isoformat(), "timeZone": time_zone},
        "end": {"dateTime": end_time.isoformat(), "timeZone": time_zone},
        "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 10}]}
    }

    created_event = calendar_service.events().insert(calendarId="primary", body=event).execute()
    return created_event.get("htmlLink")

# 🔹 Send Email using Gmail API
def send_email_reminder(subject, body, recipients):
    creds = authenticate_google()
    service = build("gmail", "v1", credentials=creds)

    from email.mime.text import MIMEText
    import base64

    message = MIMEText(body)
    message["to"] = ", ".join(recipients)
    message["from"] = creds._client_id
    message["subject"] = subject

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    try:
        service.users().messages().send(userId="me", body={"raw": raw_message}).execute()
        return True
    except Exception as e:
        st.error(f"❌ Gmail API Error: {e}")
        return False
