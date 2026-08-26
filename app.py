import streamlit as st
from openai import OpenAI
from supabase import create_client, Client
import json
import pypdf
import io

# Titel der App
st.title("❄️ Kälte-KI – Kunden-Akte & Dokumenten-Wissen")

# Verbindung zu Supabase & OpenAI laden
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Fehler bei der Supabase-Verbindung (Secrets prüfen!): {e}")

try:
    openai_api_key = st.secrets["OPENAI_API_KEY"]
    client = OpenAI(api_key=openai_api_key)
    MODEL_NAME = "gpt-4o"
except Exception as e:
    st.error(f"Fehler bei den OpenAI Secrets: {e}")

# --- SEITENLEISTE: KUNDEN & DOKUMENTE ---
st.sidebar.header("📁 Kunden-Akte / Chat")

# 1. Kunden aus Supabase laden
try:
    response = supabase.table("chat_verlaeufe").select("kunde").execute()
    kunden_liste = sorted(list(set([row["kunde"] for row in response.data]))) if response.data else []
except Exception:
    kunden_liste = []

kunden_liste.insert(0, "+ Neuer Kunde / Neues Projekt")
auswahl = st.sidebar.selectbox("Wähle einen Kunden:", kunden_liste)

if auswahl == "+ Neuer Kunde / Neues Projekt":
    neuer_kunde = st.sidebar.text_input("Name des Kunden / Projekts:")
    aktueller_kunde = neuer_kunde.strip() if neuer_kunde else "Allgemein"
else:
    aktueller_kunde = auswahl

st.sidebar.markdown(f"**Aktuelles Projekt:** `{aktueller_kunde}`")

st.sidebar.markdown("---")
st.sidebar.header("📂 Dokumente hochladen")
st.sidebar.markdown("Lade PDFs oder Textdateien für diesen Kunden hoch, damit die KI daraus lernen kann.")

uploaded_file = st.sidebar.file_uploader("Datei hochladen (PDF, TXT)", type=["pdf", "txt"])

if uploaded_file is not None:
    file_content = ""
    # Text aus PDF extrahieren
    if uploaded_file.type == "application/pdf":
        try:
            reader = pypdf.PdfReader(uploaded_file)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    file_content += text + "\n"
        except Exception as e:
            st.sidebar.error(f"Fehler beim Lesen der PDF: {e}")
    else:
        # Normale Textdatei
        file_content = uploaded_file.getvalue().decode("utf-8", errors="ignore")

    if file_content:
        if st.sidebar.button("💾 Dokument in Datenbank speichern"):
            try:
                # In Supabase speichern (Tabelle 'dokumente' nutzen wir dafür)
                data = {
                    "name": uploaded_file.name,
                    "inhalt": file_content,
                    "erstellt_am": "now()"
                }
                # Wir speichern es ab (wir können den Kunden-Namen auch im Dateinamen oder in einer Spalte hinterlegen)
                supabase.table("dokumente").insert({
                    "name": f"[{aktueller_kunde}] {uploaded_file.name}",
                    "inhalt": file_content
                }).execute()
                st.sidebar.success(f"Erfolgreich gelernt: {uploaded_file.name}!")
            except Exception as e:
                st.sidebar.error(f"Fehler beim Speichern in Supabase: {e}")

# --- CHAT-VERLAUF LADEN ---
if "current_kunde" not in st.session_state or st.session_state["current_kunde"] != aktueller_kunde:
    st.session_state["current_kunde"] = aktueller_kunde
    st.session_state.messages = []
    
    try:
        res = supabase.table("chat_verlaeufe").select("nachrichten").eq("kunde", aktueller_kunde).execute()
        if res.data and len(res.data) > 0:
            st.session_state.messages = res.data[0]["nachrichten"]
    except Exception as e:
        print(f"Konnte Verlauf nicht laden: {e}")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Chat-Verlauf anzeigen
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- NEUE EINGABE DES NUTZERS ---
if prompt := st.chat_input(f"Frage an die Kälte-KI für {aktueller_kunde}..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Relevantes Wissen aus hochgeladenen Dokumenten abrufen
    kontext_wissen = ""
    try:
        # Wir holen alle Dokumente aus der DB, die zum Kunden passen oder allgemein sind
        docs_res = supabase.table("dokumente").select("name, inhalt").execute()
        if docs_res.data:
            for doc in docs_res.data:
                # Prüfen ob das Dokument den Kunden im Namen hat oder allgemein ist
                if aktueller_kunde.lower() in doc["name"].lower() or "allgemein" in doc["name"].lower():
                    kontext_wissen += f"\n--- Dokument: {doc['name']} ---\n{doc['inhalt'][:3000]}\n" # Kürzen zur Sicherheit
    except Exception as e:
        print(f"Fehler beim Laden des Dokumenten-Wissens: {e}")

    # System-Prompt zusammenbauen, damit die KI das Wissen nutzt
    system_prompt = {
        "role": "system", 
        "content": (
            "Du bist ein professioneller Experte für Kälte- und Klimatechnik. "
            "Nutze die folgenden hochgeladenen Dokumente/Wissensdatenbank-Auszüge, um die Fragen des Nutzers präzise zu beantworten:\n"
            f"{kontext_wissen}"
        )
    }

    # Nachrichten für die API vorbereiten (System-Prompt + Verlauf)
    api_messages = [system_prompt] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]

    # Antwort von OpenAI generieren lassen
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=api_messages
        )
        assistant_reply = response.choices[0].message.content
        
        st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
        with st.chat_message("assistant"):
            st.markdown(assistant_reply)
            
        # Chat in Supabase abspeichern
        existing = supabase.table("chat_verlaeufe").select("id").eq("kunde", aktueller_kunde).execute()
        if existing.data and len(existing.data) > 0:
            supabase.table("chat_verlaeufe").update({"nachrichten": st.session_state.messages}).eq("kunde", aktueller_kunde).execute()
        else:
            supabase.table("chat_verlaeufe").insert({"kunde": aktueller_kunde, "nachrichten": st.session_state.messages}).execute()

    except Exception as e:
        st.error(f"Fehler bei der Anfrage an OpenAI: {e}")