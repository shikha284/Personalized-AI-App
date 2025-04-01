import re
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from groq import Groq
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup

# Google & Groq credentials
GROQ_API_KEY = st.secrets["groq"]["api_key"]
CLIENT_CONFIG = {
    "web": {
        "client_id": st.secrets["gmail_oauth"]["client_id"],
        "client_secret": st.secrets["gmail_oauth"]["client_secret"],
        "redirect_uris": [st.secrets["gmail_oauth"]["redirect_uri"]],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token"
    }
}
groq_client = Groq(api_key=GROQ_API_KEY)

# --- Auth & Service ---
def authenticate_gmail():
    if os.path.exists("token_gmail.pkl"):
        with open("token_gmail.pkl", "rb") as token:
            creds = pickle.load(token)
        if creds and creds.valid:
            return creds
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open("token_gmail.pkl", "wb") as token:
                pickle.dump(creds, token)
            return creds

    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=[
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send"
    ], redirect_uri=CLIENT_CONFIG["web"]["redirect_uris"][0])
    
    auth_url, _ = flow.authorization_url(prompt="consent")
    st.markdown(f"[Click here to authorize Gmail access]({auth_url})")
    auth_code = st.text_input("Paste Gmail auth code here:")
    if auth_code:
        flow.fetch_token(code=auth_code)
        creds = flow.credentials
        with open("token_gmail.pkl", "wb") as token:
            pickle.dump(creds, token)
        return creds
    return None

def get_gmail_service():
    creds = authenticate_gmail()
    if creds:
        return build("gmail", "v1", credentials=creds)
    return None

def clean_html(content):
    if not content:
        return "No content"
    soup = BeautifulSoup(content, "html.parser")
    text = soup.get_text()
    text = re.sub(r'\n+', '\n', text.strip())
    return text

def fetch_latest_email():
    service = get_gmail_service()
    if not service:
        return None

    results = service.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=1).execute()
    if not results.get("messages"):
        return None

    msg_id = results["messages"][0]["id"]
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    payload = msg["payload"]
    headers = {h["name"]: h["value"] for h in payload["headers"]}
    parts = payload.get("parts", [])
    body = parts[0]["body"]["data"] if parts else payload.get("body", {}).get("data", "")

    if body:
        decoded = base64.urlsafe_b64decode(body).decode("utf-8")
        cleaned = clean_html(decoded)
        return {
            "sender": headers.get("From", ""),
            "to": headers.get("To", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
            "body": cleaned
        }
    return None

def summarize_email(email_content):
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-specdec",
        messages=[{"role": "user", "content": f"Summarize this email: {email_content}"}]
    )
    return response.choices[0].message.content

def draft_reply(email, user_message):
    full_context = f"Reply to this email:

From: {email['sender']}
Subject: {email['subject']}
Date: {email['date']}

Body:
{email['body']}

User wants to say:
{user_message}"
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-specdec",
        messages=[{"role": "user", "content": full_context}]
    )
    return response.choices[0].message.content
