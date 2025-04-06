import os
import re
import requests
import psycopg2
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from groq import Groq
import streamlit as st
import time

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
            df['visitDate'] = pd.to_datetime(df['visittime'].dt.date)
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
        start = time.time()
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-specdec",
            messages=[{"role": "user", "content": prompt}]
        )
        end = time.time()
        return response.choices[0].message.content.strip(), round(end - start, 2)
    except Exception as e:
        return f"❌ LLM Error: {e}", 0

# === Top Visited Websites (Generic by Month & Year) ===
def top_visited_websites(df, year, month, top_n=5):
    try:
        filtered = df[(df['visitDate'].dt.month == month) & (df['visitDate'].dt.year == year)]
        filtered['visitcount'] = pd.to_numeric(filtered['visitcount'], errors='coerce').fillna(0).astype(int)
        top_sites = filtered.groupby('url')['visitcount'].sum().reset_index()
        top_sites = top_sites.sort_values(by='visitcount', ascending=False).head(top_n)
        return top_sites
    except Exception as e:
        return f"❌ Error retrieving top sites: {e}"

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
    return call_llm(eval_prompt)[0]

# === Prompt processor with routing ===
def process_prompt_with_webdata(prompt, df):
    try:
        if "shikha" in prompt.lower():
            return process_prompt_with_df(prompt, df)

        url_match = re.search(r"(https?://[^\s]+)", prompt)
        if url_match:
            content = extract_text_from_url(url_match.group(0))
            enriched_prompt = prompt.replace(url_match.group(0), f"\n\n{content}\n\n")
            return call_llm(enriched_prompt)[0]

        content = search_web_with_tavily(prompt)
        enriched = f"Use the content to answer the question:\n{content}\n\nQuestion: {prompt}"
        return call_llm(enriched)[0]

    except Exception as e:
        return f"❌ Error processing prompt: {e}"

# === Vector DB Handler for Shikha ===
def process_prompt_with_df(prompt, df):
    try:
        url_match = re.search(r"(https?://[^\s]+)", prompt)
        if url_match:
            url = url_match.group(0)
            content = extract_text_from_url(url)
            enriched_prompt = prompt.replace(url, f"\n\n{content}\n\n")
            return call_llm(enriched_prompt)[0]

        month_match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)", prompt, re.IGNORECASE)
        if month_match:
            try:
                df["visitDate"] = pd.to_datetime(df["visitDate"])
                month_number = datetime.strptime(month_match.group(0), "%B").month
                filtered = df[df["visitDate"].dt.month == month_number]
                if not filtered.empty:
                    top_url = filtered.sort_values("visitcount", ascending=False)["url"].iloc[0]
                    content = extract_text_from_url(top_url)
                    prompt_with_url = f"{prompt}\n\nTop visited page content:\n{content}\n\n"
                    return call_llm(prompt_with_url)[0]
            except Exception as e:
                print(f"⚠️ Month parsing error: {e}")

        if any(word in prompt.lower() for word in ["visit", "url", "title", "page", "click", "website", "link"]):
            df_text = df[["visitDate", "url", "visitcount", "cleaned_title"]].astype(str).to_string(index=False)
            full_prompt = f"You are a smart assistant. Here is some web visit data:\n\n{df_text}\n\nNow answer:\n{prompt}"
            return call_llm(full_prompt)[0]

        content = search_web_with_tavily(prompt)
        final_prompt = f"Based on this web search result, answer the query:\n\n{content}\n\nQuestion: {prompt}"
        return call_llm(final_prompt)[0]

    except Exception as e:
        return f"❌ Error in Shikha's prompt handling: {e}"