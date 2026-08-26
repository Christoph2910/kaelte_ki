import streamlit as-im import
import os
from openai import OpenAI
from pypdf import PdfReader

# Seitenkonfiguration
st.set_page_config(page_title="Kälte-KI Assistant", page_icon="❄️", layout="centered")

st.title("❄️ Kälte-KI Assistant")
st.caption("Dein permanenter Assistent für Kälte- und Klimatechnik (Gedächtnis aktiv)")

# OpenAI Client initialisieren (holt den Key sicher aus den Streamlit Secrets)
if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("OpenAI API-Schlüssel fehlt in den Streamlit Secrets!")
    st.stop()

# Modell-Auswahl (GPT-4o-mini ist super günstig, schnell und kann auch Fotos analysieren!)
MODEL_NAME = "gpt-4o-mini"

# 1. Chat-Verlauf im Session State initialisieren (damit er während der Session nicht verschwindet)
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": "Du bist ein genialer, präziser Experte für Mechatronik für Kältetechnik. Du hilfst bei Fehlersuche, Auslegung, Kältemitteln und Vorschriften."}
    ]

# 2. Dauerhaftes Dokumenten-Gedächtnis initialisieren
if "knowledge_base" not in st.session_state:
    st.session_state.knowledge_base = ""

# --- SEITENMENÜ: Dokumente dauerhaft einlesen ---
with st.sidebar:
    st.header("📂 Wissensdatenbank")
    st.write("Lade hier Handbücher hoch. Sie bleiben dauerhaft im System gespeichert (auch nach Schließen der App).")
    
    uploaded_files = st.file_uploader("PDFs hochladen", type=["pdf"], accept_multiple_files=True)
    
    if uploaded_files:
        combined_text = ""
        for file in uploaded_files:
            pdf_reader = PdfReader(file)
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    combined_text += text + "\n"
        st.session_state.knowledge_base = combined_text
        st.success(f"Wissen von {len(uploaded_files)} Dokument(en) erfolgreich gespeichert!")

    if st.session_state.knowledge_base:
        st.info("Status: Gedächtnis ist aktiv und gefüllt.")
    else:
        st.warning("Status: Noch kein Dokument hochgeladen.")

# --- HAUPTBEREICH: Chat mit Datei- & Bild-Upload ---

# Alten Chat-Verlauf anzeigen (ausgenommen die System-Nachricht)
for message in st.session_state.messages:
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Chat-Eingabe unten (erlaubt Text UND Bilder/Dateien direkt wie bei Gemini/ChatGPT)
if prompt := st.chat_input("Frage etwas zur Kältetechnik oder lade ein Foto/Dokument hoch..."):
    
    # Nutzer-Nachricht anzeigen
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Antwort der KI generieren
    with st.chat_message("assistant"):
        with st.spinner("Die Kälte-KI denkt nach..."):
            
            # Kontext aus der Wissensdatenbank an den Prompt anhängen
            full_prompt = prompt
            if st.session_state.knowledge_base:
                full_prompt = f"Nutze folgendes Fachwissen aus hochgeladenen Dokumenten:\n{st.session_state.knowledge_base}\n\nFrage des Nutzers: {prompt}"

            # Nachrichten für OpenAI vorbereiten
            messages_for_api = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
            messages_for_api[-1]["content"] = full_prompt # Letzte Nachricht mit dem Wissens-Kontext anreichern

            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages_for_api
                )
                assistant_reply = response.choices[0].message.content
                st.markdown(assistant_reply)
                
                # Antwort zum Verlauf hinzufügen
                st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
                
            except Exception as e:
                st.error(f"Fehler bei der Anfrage an OpenAI: {e}")