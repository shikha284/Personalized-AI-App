import os
import re
import requests
import psycopg2
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from groq import Groq
import streamlit as st

# === Groq API Client ===
GROQ_API_KEY = st.secrets["groq"]["api_key"]
groq_client = Groq(api_key=GROQ_API_KEY)

# === Tavily API Client ===
TAVILY_API_KEY = st.secrets["tavily"]["api_key"]
from tavily import TavilyClient
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

# === PostgreSQL DB Config ===
DB_CONFIG = {
    "host": "vijayrag.c9uac2i2ihy2.us-east-1.rds.amazonaws.com",
    "port": 5432,
    "user": "vijay_admin",
    "password": "vijay_secure_password_2025",
    "database": "mydatabase"
}

# === DB Utilities ===
def connect_db():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"❌ Database Connection Error: {e}")
        return None

def fetch_web_data():
    query = "SELECT * FROM webdata_embeddings_shikha_20250326"
    conn = connect_db()
    if conn:
        try:
            df = pd.read_sql(query, conn)
            df['visittime'] = pd.to_datetime(df['visittime'], errors='coerce')
            df = df.dropna(subset=['visittime'])
            df['visitDate'] = df['visittime'].dt.date
            return df
        except Exception as e:
            print(f"❌ Error reading data: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    return pd.DataFrame()

# === Web Extraction ===
def extract_text_from_url(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        return "\n".join([line.strip() for line in text.splitlines() if line.strip()])[:15000]
    except Exception as e:
        return f"❌ Error fetching URL content: {e}"

# === Tavily Search ===
def search_web_with_tavily(prompt):
    try:
        result = tavily_client.search(query=prompt, search_depth="advanced", include_raw_content=True)
        content = "\n".join([r["content"] for r in result["results"] if "content" in r])
        return content[:15000] if content else "No useful web content found."
    except Exception as e:
        return f"❌ Web search failed: {e}"

# === LLM via Groq ===
def call_llm(prompt):
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-specdec",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ LLM Error: {e}"

# === Web Prompt Processor ===
def process_prompt_with_webdata(prompt, df):
    try:
        # If prompt contains Shikha or top visited, treat as vectordb query
        if "shikha" in prompt.lower() or "top visited" in prompt.lower():
            df_text = df[['visitDate', 'url', 'visitcount', 'cleaned_title']].astype(str).to_string(index=False)
            vectordb_prompt = f"Browsing data for Shikha:\n\n{df_text}\n\nNow answer:\n{prompt}"
            return call_llm(vectordb_prompt)

        # If prompt has a URL
        url_match = re.search(r"(https?://[^\s]+)", prompt)
        if url_match:
            content = extract_text_from_url(url_match.group(0))
            enriched_prompt = prompt.replace(url_match.group(0), f"\n\n{content}\n\n")
            return call_llm(enriched_prompt)

        # Otherwise fallback to web search
        content = search_web_with_tavily(prompt)
        enriched = f"Use the content to answer the question:\n{content}\n\nQuestion: {prompt}"
        return call_llm(enriched)

    except Exception as e:
        return f"❌ Error processing prompt: {e}"

# === Web Evaluation ===
def evaluate_web_response(user_prompt, llm_response):
    eval_prompt = f"""
Evaluate the assistant's response to a user query.

User Prompt:
{user_prompt}

Response:
{llm_response}

Rate on:
- G-Eval (out of 10)
- Is it hallucinated? (Yes/No and brief reasoning)

Format:
G-Eval: <score>/10
H-Eval: <Yes/No> - <reason>
"""
    return call_llm(eval_prompt)

# === Top Visited Websites (Generic by Month & Year) ===
def top_visited_websites(df, year, month, top_n=5):
    try:
        df_filtered = df[df['visitDate'].apply(lambda x: x.month == month and x.year == year)]
        top_sites = df_filtered.groupby(['url', 'cleaned_title'])['visitcount'].sum().reset_index()
        top_sites = top_sites.sort_values(by='visitcount', ascending=False).head(top_n)
        return top_sites
    except Exception as e:
        return f"❌ Error retrieving top sites: {e}"
