import os
import base64
import html2text
from googleapiclient.discovery import build
from email.message import EmailMessage
import streamlit as st
from auth_utils import authenticate_google
from eval_utils import g_eval, if_eval, halu_eval, truthful_qa_eval

try:
    from groq import Groq
except ImportError:
    st.error("❌ Groq package not found. Run `pip install groq`.")
    st.stop()

api_key = st.secrets.get("groq", {}).get("api_key", "")
if not api_key or not api_key.startswith("gsk_"):
    st.error("❌ Valid Groq API key not found in Streamlit secrets.")
    st.stop()

groq_client = Groq(api_key=api_key)

def call_llm(prompt: str) -> str:
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-specdec",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Error calling LLM: {e}"

def get_gmail_service():
    creds = authenticate_google()
    if not creds:
        raise Exception("❌ Google authentication failed for Gmail.")
    return build('gmail', 'v1', credentials=creds)

def fetch_latest_email():
    try:
        service = get_gmail_service()
        result = service.users().messages().list(userId='me', maxResults=1, q="category:primary").execute()
        messages = result.get('messages', [])
        if not messages:
            return None

        msg_id = messages[0]['id']
        msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        headers = msg['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
        body = extract_plain_text_from_msg(msg)

        return {
            'id': msg_id,
            'sender': sender,
            'subject': subject,
            'date': date,
            'body': body
        }

    except Exception as e:
        st.error(f"❌ Error fetching email: {e}")
        return None

def extract_plain_text_from_msg(msg) -> str:
    try:
        payload = msg['payload']

        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body']['data']
                    return base64.urlsafe_b64decode(data.encode("ASCII")).decode("utf-8")

            # Fallback to HTML if no plain text
            for part in payload['parts']:
                if part['mimeType'] == 'text/html':
                    html_data = part['body']['data']
                    html = base64.urlsafe_b64decode(html_data.encode("ASCII")).decode("utf-8")
                    return html2text.html2text(html)

        else:
            # Single part fallback
            body = payload.get('body', {}).get('data', '')
            if body:
                decoded = base64.urlsafe_b64decode(body.encode("ASCII")).decode("utf-8")
                return html2text.html2text(decoded)

        return "❓ No readable content found."
    except Exception as e:
        return f"❌ Error extracting content: {e}"

def summarize_email(email_body: str) -> str:
    summary = call_llm(f"Summarize the following email:\n\n{email_body}")
    g_score = g_eval(summary, reference=email_body)
    if_score = if_eval(summary, source=email_body)
    print("[G-Eval - Email Summary]", g_score)
    print("[IFEval - Email Summary]", if_score)
    return summary

def draft_reply(email: dict, user_message: str) -> str:
    prompt = (
        f"You received the following email from {email['sender']}:\n\n"
        f"{email['body']}\n\n"
        f"Draft a professional reply based on this message and your response intent:\n\n{user_message}"
    )
    reply = call_llm(prompt)

    # Evaluate reply
    input_struct = {
        "sender": email["sender"],
        "subject": email["subject"],
        "original_message": email["body"],
        "user_intent": user_message
    }
    halu_score = halu_eval(reply, input_struct)
    if_score = if_eval(reply, source=email['body'])
    truth_score = truthful_qa_eval(reply)

    print("[HALUeval - Draft Reply]", halu_score)
    print("[IFEval - Draft Reply]", if_score)
    print("[TruthfulQA - Draft Reply]", truth_score)

    return reply

def send_reply_email(reply_text: str, original_email: dict):
    try:
        service = get_gmail_service()
        msg = EmailMessage()
        msg.set_content(reply_text)
        msg['To'] = original_email['sender']
        msg['Subject'] = "Re: " + original_email['subject']
        raw_msg = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        message = {'raw': raw_msg}
        service.users().messages().send(userId="me", body=message).execute()
        return "✅ Reply sent successfully."
    except Exception as e:
        return f"❌ Failed to send email: {e}"