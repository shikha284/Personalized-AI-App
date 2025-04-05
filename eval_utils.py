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
    
def ifeval_score(output: str, source: str) -> str:
    prompt = f"""
You are evaluating whether the following AI-generated output is factually aligned with its source.

### Source Text:
{source}

### Generated Output:
{output}

Rate the factual consistency on a scale of 1 to 5:
- 5 = Completely factually correct and no hallucinations
- 4 = Minor factual inconsistency, but mostly accurate
- 3 = Some inconsistencies or unclear alignment
- 2 = Noticeable hallucinations or contradictions
- 1 = Completely misaligned or fabricated output

Respond with a JSON object like:
{{
  "score": 4,
  "rationale": "Minor mismatch in the phrasing of time, but rest is accurate."
}}
"""
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-specdec",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

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

def q2_eval(summary: str, reference: str) -> str:
    prompt = f"""
You are a quality assurance evaluator.
Evaluate this summary using Q² metric.
### Reference (gold):
{reference}

### Summary (generated):
{summary}

Answer the following:
1. Does the summary include all key info from reference? (Yes/No)
2. Are there any inaccuracies or fabricated info? (Yes/No)
3. Rate overall quality from 1 (poor) to 5 (excellent).
4. Explain the score in 2-3 lines.

Respond only in JSON:
{{"key_info_included": "Yes", "factual": "Yes", "score": 4, "explanation": "Covers most key points and is mostly accurate."}}
"""
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-specdec",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()
