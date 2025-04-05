import os
import pickle
from datetime import datetime, timedelta
import pytz
import pandas as pd
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from dateutil import parser
import streamlit as st
import psycopg2
from auth_utils import authenticate_google

SCOPES = ['https://www.googleapis.com/auth/calendar']

DB_CONFIG = {
    "host": "vijayrag.c9uac2i2ihy2.us-east-1.rds.amazonaws.com",
    "port": 5432,
    "user": "vijay_admin",
    "password": "vijay_secure_password_2025",
    "database": "mydatabase"
}

def get_calendar_service():
    creds = authenticate_google()
    if not creds:
        raise RuntimeError("❌ Google authentication failed.")
    return build('calendar', 'v3', credentials=creds)

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

def get_task_df():
    df = fetch_task_embeddings()
    return df[['id', 'title', 'task_type', 'due_date', 'due_time', 'due_datetime']].sort_values(by='due_datetime')

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

def suggest_task_slot_today(title: str, duration_minutes: int = 30):
    service = get_calendar_service()
    start, end = find_free_slot_today(service, duration_minutes)
    if not start:
        return "⚠️ No available slot for scheduling."

    confirm = st.radio("Would you like to schedule this appointment?", ["Yes", "No"], horizontal=True)
    if confirm == "Yes":
        event = {
            'summary': title,
            'start': {'dateTime': start.isoformat(), 'timeZone': 'Asia/Kolkata'},
            'end': {'dateTime': end.isoformat(), 'timeZone': 'Asia/Kolkata'}
        }
        service.events().insert(calendarId='primary', body=event).execute()
        return f"✅ '{title}' scheduled at {start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}"
    else:
        return f"🕐 Suggested time for '{title}' is {start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')} (Not Scheduled)"

def schedule_doctor_appointment():
    service = get_calendar_service()
    start, end = find_free_slot_today(service)
    if not start:
        return None, None, "⚠️ No free slot available today."

    confirm = st.radio("Would you like to schedule the doctor appointment?", ["Yes", "No"], horizontal=True)
    if confirm == "Yes":
        event = {
            'summary': 'Doctor Appointment',
            'start': {'dateTime': start.isoformat(), 'timeZone': 'Asia/Kolkata'},
            'end': {'dateTime': end.isoformat(), 'timeZone': 'Asia/Kolkata'}
        }
        created = service.events().insert(calendarId='primary', body=event).execute()
        return start, end, f"✅ Appointment scheduled from {start.strftime('%I:%M %p')} to {end.strftime('%I:%M %p')}"
    else:
        return start, end, f"🕐 Suggested doctor appointment slot: {start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')} (Not Scheduled)"

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

def delete_tasks_by_date(target_date):
    df = fetch_task_embeddings()
    delete_targets = df[df['due_datetime'].dt.date == target_date.date()]
    if delete_targets.empty:
        return "❌ No tasks found for the specified date."
    conn = connect_to_db()
    cur = conn.cursor()
    ids = delete_targets['id'].tolist()
    cur.execute(f"DELETE FROM tasks_embeddings_shikha_20250326 WHERE id = ANY(%s);", (ids,))
    conn.commit()
    return f"🗑️ Deleted {len(ids)} tasks scheduled on {target_date.strftime('%Y-%m-%d')}"

def show_tasks_by_month(month: str):
    df = fetch_task_embeddings()
    month_filtered = df[df['due_datetime'].dt.strftime('%Y-%m') == month]
    if month_filtered.empty:
        return "❌ No tasks found for that month."
    calendar_view = month_filtered[['due_datetime', 'title', 'task_type']].sort_values(by='due_datetime')
    return calendar_view