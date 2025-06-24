# app.py

import streamlit as st
import json
import requests
from gtts import gTTS
import tempfile
import base64

# Load data files
@st.cache_data
def load_data():
    files = {
        "abbreviations": json.load(open("abbreviations.json", encoding="utf-8")),
        "admission": json.load(open("Admission.json", encoding="utf-8")),
        "dataset": json.load(open("dataset.json", encoding="utf-8")),
        "functionaries": json.load(open("functionaries.json", encoding="utf-8")),
        "contacts": json.load(open("important_contacts.json", encoding="utf-8")),
        "policy": json.load(open("policy_chunks.json", encoding="utf-8")),
    }
    return files

data = load_data()
API_KEY = "YOUR_GEMINI_API_KEY"  # Replace this

def search_all_chunks(query):
    query_lower = query.lower()
    matches = []
    for name, content in data.items():
        if isinstance(content, list):
            for item in content:
                if any(query_lower in str(val).lower() for val in item.values()):
                    matches.append({"content": json.dumps(item), "source": name})
        elif isinstance(content, dict):
            for key, val in content.items():
                if query_lower in key.lower() or query_lower in str(val).lower():
                    matches.append({"content": json.dumps({key: val}), "source": name})
    return matches

def get_answer_from_gemini(query, context_chunks):
    if not context_chunks:
        return "Sorry, no relevant information found."
    
    context_text = "\n\n".join(chunk["content"] for chunk in context_chunks[:3])
    prompt = f"""Answer this using the following context:

{context_text}

Question: {query}

Answer:"""

    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}",
        headers={"Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}]}
    )
    try:
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"Error: {e}"

def text_to_audio(text):
    tts = gTTS(text=text)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        tts.save(fp.name)
        return fp.name

def get_audio_html(mp3_path):
    with open(mp3_path, "rb") as f:
        data = f.read()
        b64 = base64.b64encode(data).decode()
        return f"""
            <audio controls autoplay>
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
        """

# Streamlit UI
st.set_page_config(page_title="MRU Voice Chatbot", page_icon="🎙️", layout="centered")
st.title("🎙️ Manav Rachna Voice/Text Chatbot")
st.markdown("Ask any question related to MRU admissions, faculty, contacts, or policies.")

query = st.text_input("Type your question here:")

if st.button("Ask"):
    if query:
        chunks = search_all_chunks(query)
        answer = get_answer_from_gemini(query, chunks)
        st.markdown(f"**Answer:** {answer}")
        mp3_path = text_to_audio(answer)
        st.markdown(get_audio_html(mp3_path), unsafe_allow_html=True)
    else:
        st.warning("Please type something to ask.")

