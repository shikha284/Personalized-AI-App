import os, base64, pickle, pytz, requests, psycopg2
import pandas as pd
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from groq import Groq
import streamlit as st

ZOOM_CLIENT_ID = st.secrets["zoom"]["client_id"]
ZOOM_CLIENT_SECRET = st.secrets["zoom"]["client_secret"]
ZOOM_ACCOUNT_ID = st.secrets["zoom"]["account_id"]
GROQ_API_KEY = st.secrets["groq"]["api_key"]
groq_client = Groq(api_key=GROQ_API_KEY)

DB_CONFIG = {
    "host": "vijayrag.c9uac2i2ihy2.us-east-1.rds.amazonaws.com",
    "port": 5432,
    "user": "vijay_admin",
    "password": "vijay_secure_password_2025",
    "database": "mydatabase"
}

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
    if interactive and os.path.exists("token.pkl"):
        os.remove("token.pkl")
    creds = None
    if os.path.exists("token.pkl"):
        with open("token.pkl", "rb") as token:
            creds = pickle.load(token)
        if creds and creds.valid:
            return True if interactive else creds
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open("token.pkl", "wb") as token:
                pickle.dump(creds, token)
            return creds
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=[
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.readonly"
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
    start = time.time()
    creds = authenticate_google()
    if not creds:
        return "❌ Google authentication failed", 0
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
    return created_event.get("htmlLink"), round(time.time() - start, 2)

def send_email_reminder(subject, body, recipients):
    start = time.time()
    creds = authenticate_google()
    if not creds:
        return False, 0
    service = build("gmail", "v1", credentials=creds)
    for email in recipients:
        html_body = f"""
        <html><body>
        <p>Hi there,</p>
        <p>You are invited to the following Zoom meeting:</p>
        <p><strong>📌 Topic:</strong> {subject.replace("📌 Zoom Meeting: ", "")}<br>
        <strong>🕒 Time:</strong> {body.get("time")}<br>
        <strong>🔗 Join Zoom Meeting:</strong> <a href="{body.get("link")}">{body.get("link")}</a></p>
        <p>Please join on time.</p>
        <p>Regards,<br>Shikha</p></body></html>
        """
        msg = MIMEText(html_body, "html")
        msg["to"] = email
        msg["from"] = "me"
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        message = {"raw": raw}
        service.users().messages().send(userId="me", body=message).execute()
    return True, round(time.time() - start, 2)

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
    start = time.time()
    access_token = get_zoom_access_token()
    if not access_token:
        return None, "❌ Zoom access token error.", 0
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
    duration_sec = round(time.time() - start, 2)
    if res.status_code == 201:
        return res.json().get("join_url"), "✅ Zoom meeting scheduled!", duration_sec
    else:
        return None, f"❌ Zoom scheduling failed: {res.json()}", duration_sec

def connect_to_db():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print("❌ DB Error:", e)
        return None

@st.cache_data
def fetch_transcripts():
    conn = connect_to_db()
    if not conn:
        return pd.DataFrame()
    df = pd.read_sql("SELECT * FROM meeting_embeddings_shikha_20250401_new_6 WHERE category <> 'chats';", conn)
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    return df

def get_transcripts():
    return fetch_transcripts()

def summarize_meetings(df):
    if df.empty:
        return "⚠️ No transcript data to summarize.", None, 0
    start = time.time()
    content = " ".join(df.sort_values(by="created_at", ascending=False)["content"].tolist())[:4000]
    try:
        summary = groq_client.chat.completions.create(
            model="llama-3.3-70b-specdec",
            messages=[{"role": "user", "content": f"Summarize this meeting transcript: {content}"}]
        ).choices[0].message.content

        sentiment = groq_client.chat.completions.create(
            model="llama-3.3-70b-specdec",
            messages=[{"role": "user", "content": f"Analyze the sentiment of this meeting transcript:

{content}"}]
        ).choices[0].message.content

        return summary.strip(), sentiment.strip(), round(time.time() - start, 2)

    except Exception as e:
        print("❌ Error in summarizing/sentiment:", e)
        return "❌ Failed to generate summary.", "❌ Failed to analyze sentiment.", round(time.time() - start, 2)

def summarize_latest_meeting():
    df = fetch_transcripts()
    if df.empty:
        return None, None, 0
    return summarize_meetings(df.head(1))