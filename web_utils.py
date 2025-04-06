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
            df['visitDate'] = pd.to_datetime(df['visittime'].dt.date)  # Ensure datetime64[ns] for .dt accessor
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
        if "shikha" in prompt.lower():
            # Treat as internal vector DB query
            if any(kw in prompt.lower() for kw in ["visit", "url", "page", "click", "link"]):
                df_text = df[['visitDate', 'url', 'visitcount', 'cleaned_title']].astype(str).to_string(index=False)
                prompt_embed = f"Here is Shikha's web browsing data:\n\n{df_text}\n\nAnswer the question: {prompt}"
                return call_llm(prompt_embed)

            month_match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)", prompt, re.IGNORECASE)
            if month_match:
                month = datetime.strptime(month_match.group(0), "%B").month
                filtered = df[df["visitDate"].dt.month == month]
                if not filtered.empty:
                    top_url = filtered.sort_values("visitcount", ascending=False).iloc[0]["url"]
                    content = extract_text_from_url(top_url)
                    enriched = f"{prompt}\n\nTop visited site content:\n{content}"
                    return call_llm(enriched)

        # Default to Tavily for generic web search
        url_match = re.search(r"(https?://[^\s]+)", prompt)
        if url_match:
            content = extract_text_from_url(url_match.group(0))
            enriched_prompt = prompt.replace(url_match.group(0), f"\n\n{content}\n\n")
            return call_llm(enriched_prompt)

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
        filtered = df[(df['visitDate'].dt.month == month) & (df['visitDate'].dt.year == year)]
        top_sites = filtered.groupby('url')['visitcount'].sum().reset_index()
        top_sites = top_sites.sort_values(by='visitcount', ascending=False).head(top_n)
        return top_sites
    except Exception as e:
        return f"❌ Error retrieving top sites: {e}"