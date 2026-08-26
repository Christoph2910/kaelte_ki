import streamlit as st
from openai import OpenAI
from supabase import create_client, Client
import json

# Titel der App
st.title("❄️ Kälte-KI – Kunden-Datenbank & Projekt-Akte")

# Verbindung zu Supabase & OpenAI aus den Streamlit Secrets laden
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Fehler bei der Supabase-Verbindung (Secrets prüfen!): {e}")

try:
    openai_api_key = st.secrets["OPENAI_API_KEY"]
    client = OpenAI(api_key=openai_api_key)
    MODEL_NAME = "gpt-4o" # Oder "gpt-4o-mini", je nachdem was du nutzt
except Exception as e:
    st.error(f"Fehler bei den OpenAI Secrets: {e}")

# --- SEITENLEISTE: KUNDEN / PROJEKTE VERWALTEN ---
st.sidebar.header("📁 Kunden-Akte / Chat wählen")

# 1. Bestehende Kunden aus Supabase laden
try:
    response = supabase.table("chat_verlaeufe").select("kunde").execute()
    kunden_liste = sorted(list(set([row["kunde"] for row in response.data]))) if response.data else []
except Exception:
    kunden_liste = []

# Option zum Erstellen eines neuen Kunden
kunden_liste.insert(0, "+ Neuer Kunde / Neues Projekt")
auswahl = st.sidebar.selectbox("Wähle einen Kunden:", kunden_liste)

if auswahl == "+ Neuer Kunde / Neues Projekt":
    neuer_kunde = st.sidebar.text_input("Name des Kunden / Projekts:")
    if neuer_kunde:
        aktueller_kunde = neuer_kunde.strip()
    else:
        aktueller_kunde = "Allgemein"
else:
    aktueller_kunde = auswahl

st.sidebar.markdown(f"**Aktuelles Projekt:** `{aktueller_kunde}`")

# --- CHAT-VERLAUF LADEN ---
# Wenn wir den Kunden wechseln, laden wir die Nachrichten aus der Datenbank
if "current_kunde" not in st.session_state or st.session_state["current_kunde"] != aktueller_kunde:
    st.session_state["current_kunde"] = aktueller_kunde
    st.session_state.messages = []
    
    try:
        res = supabase.table("chat_verlaeufe").select("nachrichten").eq("kunde", aktueller_kunde).execute()
        if res.data and len(res.data) > 0:
            # Nachrichten aus JSON Format wiederherstellen
            st.session_state.messages = res.data[0]["nachrichten"]
    except Exception as e:
        print(f"Konnte Verlauf nicht laden: {e}")

# Initialisiere Nachrichten, falls leer
if "messages" not in st.session_state:
    st.session_state.messages = []

# Bisherigen Chat-Verlauf im Bildschirm anzeigen
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- NEUE EINGABE DES NUTZERS ---
if prompt := st.chat_input(f"Schreibe etwas für Kunde {aktueller_kunde}..."):
    # Nutzer-Nachricht hinzufügen
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Antwort von OpenAI generieren lassen
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
        )
        assistant_reply = response.choices[0].message.content
        
        # KI-Antwort hinzufügen
        st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
        with st.chat_message("assistant"):
            st.markdown(assistant_reply)
            
        # --- CHAT IN SUPABASE ABSPEICHERN ---
        # Prüfen ob der Kunde schon in der DB ist, ansonsten updaten/einfügen
        existing = supabase.table("chat_verlaeufe").select("id").eq("kunde", aktueller_kunde).execute()
        
        if existing.data and len(existing.data) > 0:
            # Update bestehender Eintrag
            supabase.table("chat_verlaeufe").update({"nachrichten": st.session_state.messages}).eq("kunde", aktueller_kunde).execute()
        else:
            # Neuer Eintrag
            supabase.table("chat_verlaeufe").insert({"kunde": aktueller_kunde, "nachrichten": st.session_state.messages}).execute()

    except Exception as e:
        st.error(f"Fehler bei der Anfrage an OpenAI: {e}")