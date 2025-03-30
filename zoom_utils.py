import os
import base64
import pytz
import pickle
import streamlit as st
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from email.mime.text import MIMEText

# Zoom credentials
ZOOM_CLIENT_ID = st.secrets["zoom"]["client_id"]
ZOOM_CLIENT_SECRET = st.secrets["zoom"]["client_secret"]
ZOOM_ACCOUNT_ID = st.secrets["zoom"]["account_id"]

# Google OAuth2 configuration
CLIENT_CONFIG = {
    "web": {
        "client_id": st.secrets["gmail_oauth"]["client_id"],
        "client_secret": st.secrets["gmail_oauth"]["client_secret"],
        "redirect_uris": [st.secrets["gmail_oauth"]["redirect_uri"]],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token"
    }
}

def authenticate_google(interactive=False, auth_code=None):
    if os.path.exists("token.pkl"):
        with open("token.pkl", "rb") as token:
            creds = pickle.load(token)
        if creds and creds.valid:
            return True if interactive else creds
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open("token.pkl", "wb") as token:
                pickle.dump(creds, token)
            return True if interactive else creds

    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=[
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/gmail.send"
        ],
        redirect_uri=CLIENT_CONFIG["web"]["redirect_uris"][0]
    )

    if interactive and auth_code is None:
        auth_url, _ = flow.authorization_url(prompt="consent")
        return auth_url, "auth_code_input"
    elif interactive and auth_code:
        try:
            flow.fetch_token(code=auth_code)
            creds = flow.credentials
            with open("token.pkl", "wb") as token:
                pickle.dump(creds, token)
            return True
        except Exception as e:
            print("❌ Token fetch failed:", e)
            return False
    return None

def add_to_calendar(topic, start_time, duration, time_zone, zoom_link):
    creds = authenticate_google()
    if not creds:
        return "❌ Google authentication failed"

    service = build("calendar", "v3", credentials=creds)
    end_time = start_time + timedelta(minutes=duration)
    event = {
        "summary": topic,
        "location": "Zoom",
        "description": f"Join Zoom Meeting: {zoom_link}",
        "start": {"dateTime": start_time.isoformat(), "timeZone": time_zone},
        "end": {"dateTime": end_time.isoformat(), "timeZone": time_zone},
        "reminders": {"useDefault": True}
    }
    created_event = service.events().insert(calendarId="primary", body=event).execute()
    return created_event.get("htmlLink")

def send_email_reminder(subject, body, recipients):
    creds = authenticate_google()
    if not creds:
        return False

    service = build("gmail", "v1", credentials=creds)

    for email in recipients:
        msg = MIMEText(body)
        msg["to"] = email
        msg["from"] = "me"
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        message = {"raw": raw}
        service.users().messages().send(userId="me", body=message).execute()

    return True

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
