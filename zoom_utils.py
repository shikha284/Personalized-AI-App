import os
import base64
import pickle
import pytz
import requests
import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from groq import Groq  # ✅ LLaMA 3.3 Integration

# ✅ Groq API Setup
client = Groq(api_key=st.secrets["groq"]["api_key"])

# ✅ PostgreSQL Vector DB Configuration
DB_CONFIG = {
    "host": "vijayrag.c9uac2i2ihy2.us-east-1.rds.amazonaws.com",
    "port": 5432,
    "user": "vijay_admin",
    "password": "vijay_secure_password_2025",
    "database": "mydatabase"
}

# ✅ Google OAuth2 configuration
CLIENT_CONFIG = {
    "web": {
        "client_id": st.secrets["gmail_oauth"]["client_id"],
        "client_secret": st.secrets["gmail_oauth"]["client_secret"],
        "redirect_uris": [st.secrets["gmail_oauth"]["redirect_uri"]],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token"
    }
}

# ---------- 🔐 Google Auth ----------
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

# ---------- ✅ DB Connection & Meeting Summary ----------
def connect_to_db():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print("❌ DB Connection Error:", e)
        return None

def fetch_recent_meetings(n=2):
    conn = connect_to_db()
    if not conn:
        return None
    df = pd.read_sql("SELECT * FROM embeddings_shikha_20250324 WHERE category='meetings' ORDER BY date DESC LIMIT %s", conn, params=(n,))
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    conn.close()
    return df

def summarize_meetings(df):
    combined_text = " ".join(df['content'].tolist())[:4000]  # truncate for model input
    completion = client.chat.completions.create(
        model="llama-3.3-70b-specdec",
        messages=[{"role": "user", "content": f"Summarize this meeting transcript: {combined_text}"}]
    )
    return completion.choices[0].message.content

# ---------- 📅 Calendar + Gmail ----------
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

def send_email_reminder(subject, body_dict, recipients):
    creds = authenticate_google()
    if not creds:
        return False

    service = build("gmail", "v1", credentials=creds)

    html_body = f"""
    <html>
    <body>
        <p>Hi there,</p>
        <p>You are invited to the following Zoom meeting:</p>
        <p><strong>📌 Topic:</strong> {subject.replace("📌 Zoom Meeting: ", "")}<br>
        <strong>🕒 Time:</strong> {body_dict.get("time")}<br>
        <strong>🔗 Join Zoom Meeting:</strong> <a href="{body_dict.get("link")}">{body_dict.get("link")}</a></p>
        <p>Please join on time.</p>
        <p>Regards,<br>Shikha</p>
    </body>
    </html>
    """

    for email in recipients:
        msg = MIMEText(html_body, "html")
        msg["to"] = email
        msg["from"] = "me"
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()

    return True

# ---------- 🔗 Zoom ----------
def get_zoom_access_token():
    auth_string = f"{ZOOM_CLIENT_ID}:{ZOOM_CLIENT_SECRET}"
    auth_base64 = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
    headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"grant_type": "account_credentials", "account_id": ZOOM_ACCOUNT_ID}
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
