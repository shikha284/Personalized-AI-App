import os
import base64
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email import message_from_bytes
from groq import Groq

# Scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Groq API
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or "your-groq-api-key"
groq_client = Groq(api_key=GROQ_API_KEY)

def call_llm(prompt):
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-specdec",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def get_gmail_service():
    creds_path = 'token.json'
    if not os.path.exists(creds_path):
        raise Exception("Gmail token.json not found. Please authenticate.")

    creds = Credentials.from_authorized_user_file(creds_path, SCOPES)
    service = build('gmail', 'v1', credentials=creds)
    return service

def fetch_latest_email():
    service = get_gmail_service()
    results = service.users().messages().list(userId='me', maxResults=1, q="category:primary").execute()
    messages = results.get('messages', [])

    if not messages:
        return None

    msg_id = messages[0]['id']
    msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
    headers = msg['payload']['headers']
    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
    sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
    date = next((h['value'] for h in headers if h['name'] == 'Date'), '')

    parts = msg['payload'].get('parts', [])
    body = ""
    for part in parts:
        if part['mimeType'] == 'text/plain':
            data = part['body']['data']
            body = base64.urlsafe_b64decode(data.encode('ASCII')).decode('utf-8')
            break

    return {
        'sender': sender,
        'subject': subject,
        'date': date,
        'body': body
    }

def summarize_email(email_body: str) -> str:
    prompt = f"Summarize the following email:\n\n{email_body}"
    return call_llm(prompt)

def draft_reply(email: dict, user_message: str) -> str:
    prompt = (
        f"You received the following email from {email['sender']}:\n\n"
        f"{email['body']}\n\n"
        f"Draft a professional reply based on this message:\n\n{user_message}"
    )
    return call_llm(prompt)
