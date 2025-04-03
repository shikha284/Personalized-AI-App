import os
import pickle
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import streamlit as st

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
