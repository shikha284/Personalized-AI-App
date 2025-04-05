import os
import pickle
from datetime import datetime, timedelta
import pytz
import pandas as pd
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from dateutil import parser
import streamlit as st
import psycopg2

SCOPES = ['https://www.googleapis.com/auth/calendar']

DB_CONFIG = {
    "host": "vijayrag.c9uac2i2ihy2.us-east-1.rds.amazonaws.com",
    "port": 5432,
    "user": "vijay_admin",
    "password": "vijay_secure_password_2025",
    "database": "mydatabase"
}

def load_credentials():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'calendar_credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds

def get_calendar_service():
    creds = load_credentials()
    service = build('calendar', 'v3', credentials=creds)
    return service

def connect_to_db():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print("❌ DB Error:", e)
        return None

def fetch_task_embeddings():
    conn = connect_to_db()
    if not conn:
        return pd.DataFrame()
    df = pd.read_sql("SELECT * FROM tasks_embeddings_shikha_20250326;", conn)
    df['due_datetime'] = pd.to_datetime(df['due_date'] + ' ' + df['due_time'])
    return df

def list_events_today(service):
    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    events = service.events().list(
        calendarId='primary',
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return events.get('items', [])

def find_free_slot_today(service, duration_minutes=60):
    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(tz)
    start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    end = now.replace(hour=18, minute=0, second=0, microsecond=0)
    busy = [(parser.parse(e['start']['dateTime']), parser.parse(e['end']['dateTime'])) for e in list_events_today(service)]
    current = start
    while current + timedelta(minutes=duration_minutes) <= end:
        slot_end = current + timedelta(minutes=duration_minutes)
        if not any(bs <= current < be or bs < slot_end <= be for bs, be in busy):
            return current, slot_end
        current += timedelta(minutes=15)
    return None, None

def schedule_doctor_appointment(service):
    start, end = find_free_slot_today(service)
    if not start:
        return None, None, "⚠️ No free slot available today."
    event = {
        'summary': 'Doctor Appointment',
        'start': {'dateTime': start.isoformat(), 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end.isoformat(), 'timeZone': 'Asia/Kolkata'}
    }
    created = service.events().insert(calendarId='primary', body=event).execute()
    return start, end, f"✅ Appointment scheduled from {start.strftime('%I:%M %p')} to {end.strftime('%I:%M %p')}"

def delete_last_task_today():
    df = fetch_task_embeddings()
    today = datetime.now().date()
    today_tasks = df[df['due_datetime'].dt.date == today]
    if today_tasks.empty:
        return "⚠️ No task found for today."
    last_task_id = today_tasks.sort_values(by='due_datetime').iloc[-1]['id']
    conn = connect_to_db()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM tasks_embeddings_shikha_20250326 WHERE id = {int(last_task_id)};")
    conn.commit()
    return f"🗑️ Task ID {int(last_task_id)} deleted."

def show_tasks_by_month(month: str):
    df = fetch_task_embeddings()
    month_filtered = df[df['due_datetime'].dt.strftime('%Y-%m') == month]
    if month_filtered.empty:
        return "❌ No tasks found for that month."
    calendar_view = month_filtered[['due_datetime', 'title', 'task_type']].sort_values(by='due_datetime')
    return calendar_view

