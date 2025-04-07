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
    prompt = f"""Give only overall G-Eval score out of 10.
---
Summary:
{summary}

Reference:
{reference}

Respond with: G-Eval: <score>/10"""
    try:
        response = groq_eval.chat.completions.create(
            model="llama-3.3-70b-specdec",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ G-Eval failed: {e}"

# -------------------- IFEval (Score Only) -------------------- #
def if_eval(output: str, source: str) -> str:
    prompt = f"""
Rate factual consistency between the source and generated output on a scale from 1 to 5:
- 5 = Completely factually correct
- 4 = Minor factual error
- 3 = Some inconsistencies
- 2 = Multiple factual errors
- 1 = Largely incorrect

Source:
{source}

Generated Output:
{output}

Respond with: IFEval: <score>/5"""
    try:
        response = groq_eval.chat.completions.create(
            model="llama-3.3-70b-specdec",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ IFEval failed: {e}"

# -------------------- HALUeval (0/1) -------------------- #
def halu_eval(generated_text: str, input_struct: dict) -> str:
    struct_facts = "\n".join([f"{k}: {v}" for k, v in input_struct.items()])
    prompt = f"""Determine if the following output contains hallucinations.
Structured Input:
{struct_facts}

Generated Text:
{generated_text}

Respond with: HALUeval: 1 if hallucination present, else HALUeval: 0"""
    try:
        response = groq_eval.chat.completions.create(
            model="llama-3.3-70b-specdec",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ HALUeval failed: {e}"

# -------------------- TruthfulQA (Score Only) -------------------- #
def truthful_qa_eval(output: str) -> str:
    prompt = f"""Rate factual correctness of this response from 1 to 5:
- 5 = Fully accurate
- 4 = Mostly accurate
- 3 = Some inaccuracies
- 2 = Misleading or incorrect parts
- 1 = Completely false

Response:
{output}

Respond with: TruthfulQA: <score>/5"""
    try:
        response = groq_eval.chat.completions.create(
            model="llama-3.3-70b-specdec",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ TruthfulQA eval failed: {e}"

# -------------------- Q2 Eval (Structured JSON) -------------------- #
def q2_eval(summary: str, reference: str) -> str:
    prompt = f"""
You are a QA evaluator.

Evaluate this summary based on its quality compared to the reference. Provide a JSON response.

Reference:
{reference}

Summary:
{summary}

Respond with JSON:
{{
  "key_info_included": "Yes" or "No",
  "factual": "Yes" or "No",
  "score": 1-5,
  "explanation": "Brief explanation in one sentence"
}}
"""
    try:
        response = groq_eval.chat.completions.create(
            model="llama-3.3-70b-specdec",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Q2 Eval failed: {e}"