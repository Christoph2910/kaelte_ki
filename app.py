import base64
import os
from dotenv import load_dotenv
from pypdf import PdfReader
import streamlit as st
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="Kälte-KI Assistant", page_icon="❄️")
st.title("❄️ Kälte-KI Assistent")

# --- SEITENLEISTE FÜR PDF-UPLOAD ---
with st.sidebar:
    st.header("📚 Fachwissen hochladen")
    uploaded_files = st.file_uploader(
        "Kälte-PDFs oder iPad-Notizen (PDF)",
        type=["pdf"],
        accept_multiple_files=True,
    )

    pdf_text_context = ""

    if uploaded_files:
        st.success(f"{len(uploaded_files)} Datei(en) geladen!")
        for file in uploaded_files:
            reader = PdfReader(file)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    pdf_text_context += extracted + "\n"

# --- SYSTEM-PROMPT MIT PDF-WISSEN KOMBINIEREN ---
base_system_prompt = (
    "Du bist ein hochspezialisierter KI-Experte für Kälte- und Klimatechnik. "
    "Antworte immer präzise, fachlich korrekt und in sauberer Fachsprache. "
    "Nutze primär das zur Verfügung gestellte Fachwissen aus den hochgeladenen"
    " Dokumenten."
)

if pdf_text_context:
    full_system_prompt = f"{base_system_prompt}\n\nHIER IST DAS HOCHGELADENE FACHWISSEN AUS DEN SKRIPTEN:\n{pdf_text_context}"
else:
    full_system_prompt = base_system_prompt

# --- CHAT-VERLAUF ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# System-Prompt immer aktualisieren
st.session_state.messages_to_send = [{"role": "system", "content": full_system_prompt}] + [
    m for m in st.session_state.messages if m["role"] != "system"
]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_input = st.chat_input("Frage zur Kältetechnik oder deinen Skripten...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # Aktualisierte Nachrichtenliste für OpenAI aufbauen
    messages_payload = [{"role": "system", "content": full_system_prompt}] + st.session_state.messages

    with st.chat_message("assistant"):
        with st.spinner("Durchsuche Unterlagen & antworte..."):
            response = client.chat.completions.create(
                model="gpt-4o",  # gpt-4o eignet sich auch perfekt für komplexe Zusammenhänge
                messages=messages_payload,
            )
            answer = response.choices[0].message.content
            st.write(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})