# eval_utils.py
import streamlit as st
from groq import Groq

# Setup Groq client
api_key = st.secrets.get("groq", {}).get("api_key", "")
if not api_key or not api_key.startswith("gsk_"):
    st.error("❌ Valid Groq API key not found in Streamlit secrets.")
    st.stop()

groq_eval = Groq(api_key=api_key)

# -------------------- G-Eval -------------------- #
def g_eval(summary: str, reference: str) -> str:
    prompt = f"""Evaluate the following summary using G-Eval dimensions (coverage, coherence, fluency, relevance):
---
Summary:
{summary}

Reference:
{reference}

Respond with structured score and justification for each metric."""
    try:
        response = groq_eval.chat.completions.create(
            model="llama-3.3-70b-specdec",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ G-Eval failed: {e}"

# -------------------- IFEval -------------------- #
def if_eval(output: str, source: str) -> str:
    prompt = f"""Evaluate if the following output contains any hallucinations:
---
Source:
{source}

Generated Output:
{output}

Return analysis explaining factual alignment and any detected hallucinations."""
    try:
        response = groq_eval.chat.completions.create(
            model="llama-3.3-70b-specdec",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ IFEval failed: {e}"

# -------------------- HALUeval (Structured → Text) -------------------- #
def halu_eval(generated_text: str, input_struct: dict) -> str:
    struct_facts = "\n".join([f"{k}: {v}" for k, v in input_struct.items()])
    prompt = f"""Check if the following generated content aligns with the structured input.
---
Structured Input:
{struct_facts}

Generated Text:
{generated_text}

Return a factual consistency judgment and highlight any hallucinated claims."""
    try:
        response = groq_eval.chat.completions.create(
            model="llama-3.3-70b-specdec",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ HALUeval failed: {e}"

# -------------------- TruthfulQA Style -------------------- #
def truthful_qa_eval(output: str) -> str:
    prompt = f"""Evaluate the factual correctness of this response using a TruthfulQA-style standard:
---
Response:
{output}

Return whether the response is factually accurate and explain any errors or misleading info."""
    try:
        response = groq_eval.chat.completions.create(
            model="llama-3.3-70b-specdec",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ TruthfulQA eval failed: {e}"

